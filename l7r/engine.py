"""
Combat engine: orchestrates rounds, phases, and the attack/parry sequence.

The engine drives the main simulation loop. Each round, all combatants roll
initiative (producing action dice), and then the engine steps through phases
0-10. In each phase, combatants with ready actions choose what to do (attack,
double attack, feint, lunge, etc.), and the engine resolves the full sequence:
counterattacks, pre-declares, attack rolls, parry attempts, damage, and
wound checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from l7r.records import ActionRecord, AttackRecord, CombatRecord, DuelRecord, DuelRoundRecord, ParryRecord, RoundRecord
from l7r.renderers import TextRenderer
from l7r.types import RollType

if TYPE_CHECKING:
    from l7r.combatant import Combatant
    from l7r.formations import Formation


class Engine:
    """Runs a combat encounter from start to finish.

    Owns the phase clock, the combat record, and resolves the attack/parry/
    damage sequence. Delegates tactical decisions to each Combatant's heuristic
    methods and formation bookkeeping to the Formation object.
    """

    def __init__(self, formation: Formation, renderer: TextRenderer | None = None) -> None:
        self.formation = formation
        self.combatants = formation.combatants
        self.combat_record = CombatRecord()
        self._action_stack: list[ActionRecord] = []
        self.renderer = renderer or TextRenderer()

    @property
    def finished(self) -> bool:
        """Combat ends when one side has no living combatants."""
        return self.formation.one_side_finished

    def fight(self, *, duel: bool = False) -> None:
        """Run the full combat: pre-fight triggers, optional duel, then
        rounds until one side is eliminated.

        Args:
            duel: If True, run an iaijutsu duel between the two lead
                combatants before normal melee begins.
        """
        for c in self.combatants:
            c.engine = self
            c.triggers("pre_fight")

        if duel:
            self.duel()

        while not self.finished:
            self.round()

        if any(c for c in self.formation.side_a if not c.dead):
            self.combat_record.winner = "side_a"
        else:
            self.combat_record.winner = "side_b"

    def duel(self) -> None:
        """Run an iaijutsu duel between the lead combatants of each side.

        The duel proceeds in rounds:
        1. Contested iaijutsu roll (no reroll 10s) to determine who decides
           first.
        2. Each duelist decides to focus (TN +5) or strike.
        3. If both focus, loop back with raised TNs.
        4. If at least one strikes, resolve: strikers roll iaijutsu, hits
           deal duel damage, wound checks use no reroll / no VPs.
        5. If at least one hit, the duel ends.
        6. If all miss, resheathe: winner of contested roll gets +1 free
           raise, TNs reset, loop back.
        7. Restore normal TNs after the duel.
        """
        assert len(self.formation.side_a) == len(self.formation.side_b) == 1, "Duel requires exactly 1 combatant per side"

        a, b = self.formation.side_a[0], self.formation.side_b[0]

        a.triggers("pre_duel")
        b.triggers("pre_duel")

        duel_record = DuelRecord(a_name=a.name, b_name=b.name)
        self.combat_record.duel = duel_record

        # Save original TNs for restoration
        a_base_tn = a.tn
        b_base_tn = b.tn

        # Set duel TNs
        a.tn = a.xp // 10
        b.tn = b.xp // 10

        a_free_raises = b_free_raises = round_num = 0

        while not a.dead and not b.dead:
            round_num += 1
            finished, a_contested, b_contested = self._duel_round(a, b, a_free_raises, b_free_raises, round_num)
            if finished:
                break

            # Both missed — resheathe
            if duel_record.rounds:
                duel_record.rounds[-1].resheathe = True
            # The contested roll winner gets +1 free raise
            if a_contested >= b_contested:
                a_free_raises += 1
            if b_contested >= a_contested:
                b_free_raises += 1

            # Reset TNs to base duel TNs
            a.tn = a.xp // 10
            b.tn = b.xp // 10

        # Restore normal TNs
        a.tn = a_base_tn
        b.tn = b_base_tn

        a.triggers("post_duel")
        b.triggers("post_duel")

    def _iaijutsu_dice(self, c: Combatant) -> tuple[int, int]:
        """Return the iaijutsu dice pool (rolled, kept) for a combatant."""
        roll, keep = c.extra_dice["iaijutsu"]
        roll += c.fire + getattr(c, "iaijutsu", 0)
        keep += c.fire
        return roll, keep

    def _duel_round(self, a: Combatant, b: Combatant, a_free_raises: int, b_free_raises: int, round_num: int) -> tuple[bool, int, int]:
        """Execute one duel round.

        Returns (finished, a_contested, b_contested):
        - finished: True if the duel is over (hit landed or someone died)
        - a_contested, b_contested: the contested roll totals, used for
          resheathe free raise assignment when both miss
        """
        round_rec = DuelRoundRecord(
            round_num=round_num,
            a_name=a.name,
            b_name=b.name,
        )
        self.combat_record.duel.rounds.append(round_rec)

        # Contested iaijutsu roll (no reroll 10s)
        a_contested = a.xky(*self._iaijutsu_dice(a), False, "iaijutsu") + a.always["iaijutsu"]
        round_rec.contested_a = getattr(a, "last_dice_roll", None)
        b_contested = b.xky(*self._iaijutsu_dice(b), False, "iaijutsu") + b.always["iaijutsu"]
        round_rec.contested_b = getattr(b, "last_dice_roll", None)

        # Winner decides first, but both decide
        if a_contested >= b_contested:
            first, second = a, b
            first_fr, second_fr = a_free_raises, b_free_raises
        else:
            first, second = b, a
            first_fr, second_fr = b_free_raises, a_free_raises

        first_strikes = first.duel_should_strike(second, first.tn, second.tn, first_fr, round_num,)
        second_strikes = second.duel_should_strike(first, second.tn, first.tn, second_fr, round_num,)

        round_rec.a_strikes = first_strikes if first is a else second_strikes
        round_rec.b_strikes = second_strikes if first is a else first_strikes

        # If both focus, raise TNs and loop
        if not first_strikes and not second_strikes:
            a.tn += 5
            b.tn += 5
            return False, a_contested, b_contested

        # At least one strikes — resolve
        # Focusers don't attack but get +5 TN (already raised above if both focused,
        # but here only the focuser gets the raise)
        if not first_strikes:
            first.tn += 5

        if not second_strikes:
            second.tn += 5

        any_hit = False

        # Resolve strikes — first striker acts first (contested roll winner)
        strikers = []
        if first_strikes:
            strikers.append((first, second))
        if second_strikes:
            strikers.append((second, first))

        for striker, target in strikers:
            fr = a_free_raises if striker is a else b_free_raises
            # Roll iaijutsu (no reroll 10s)
            striker.attack_knack = "iaijutsu"
            striker.enemy = target
            target.enemy = striker
            roll, keep = self._iaijutsu_dice(striker)
            striker.attack_roll = striker.xky(roll, keep, False, "iaijutsu") + striker.always["iaijutsu"]

            if striker.attack_roll >= target.tn:
                any_hit = True
                striker.triggers("successful_attack")
                dmg_rec = striker.deal_duel_damage(target.tn, fr)
                round_rec.damage.append(dmg_rec)
                wc_rec = target.wound_check(dmg_rec.light, dmg_rec.serious, reroll=False, spend_vps=False)
                if wc_rec:
                    round_rec.wound_checks.append(wc_rec)

        return any_hit, a_contested, b_contested

    def parry(self, defender: Combatant, attacker: Combatant) -> tuple[bool, bool, ParryRecord | None]:
        """Give the defender (and their allies) a chance to parry.

        Returns (succeeded, attempted, record): succeeded means the parry
        blocked the hit; attempted means someone tried even if they failed.
        This distinction matters because a failed parry still negates the
        attacker's bonus damage dice from exceeding the TN.
        """
        if defender.will_parry():
            rec = defender.make_parry()
            return rec.success, True, rec

        for def_ally in defender.adjacent:
            if attacker in def_ally.attackable and def_ally.will_parry_for(defender, attacker):
                rec = def_ally.make_parry_for(defender, attacker)
                return rec.success, True, rec

        return False, False, None

    def attack(self, knack: RollType, attacker: Combatant, defender: Combatant) -> None:
        """Resolve a single attack, including the full counterattack /
        predeclare / attack roll / parry / damage / wound check sequence.

        This is the heart of the combat engine. The flow is:
        1. Check for counterattacks (defender or allies may strike first)
        2. Give defender a chance to pre-declare a parry (+5 bonus)
        3. Attacker rolls to hit
        4. If hit: defender may attempt to parry, then damage and wounds
        5. If miss: anyone who pre-declared gets a free parry trigger
        """
        # Push a sentinel on the action stack so nested attacks can see their parent.
        parent_record = AttackRecord(
            attacker=attacker.name, defender=defender.name,
            knack=knack, phase=getattr(self, "phase", 0), vps_spent=0,
        )
        self._action_stack.append(parent_record)

        # Before the attack resolves, the defender (or allies) may
        # counterattack. Counterattacking an ally raises the attacker's
        # TN to reflect the distraction.
        if defender.will_counterattack(attacker):
            self.attack("counterattack", defender, attacker)
        elif knack != "counterattack":
            attacker.tn += 5 * attacker.parry
            for def_ally in list(attacker.attackable):
                if (
                    not attacker.dead
                    and def_ally in defender.adjacent
                    and attacker in def_ally.attackable
                    and def_ally.will_counterattack_for(defender, attacker)
                ):
                    self.attack("counterattack", def_ally, attacker)
            attacker.tn -= 5 * attacker.parry

        if attacker.dead:
            self._action_stack.pop()
            return

        attacker.attack_knack = knack
        defender.enemy = attacker
        attacker.enemy = defender
        attacker.triggers("pre_attack")
        defender.triggers("pre_defense")

        was_forced = defender.forced_parry
        if defender.forced_parry:
            defender.forced_parry = False
            if defender.actions:
                defender.actions.pop(0)
                defender.predeclare_bonus = 0

        if not was_forced and not defender.will_predeclare():
            for def_ally in defender.adjacent:
                if attacker in def_ally.attackable and def_ally.will_predeclare_for(defender, attacker):
                    break

        attack_rec = attacker.make_attack()
        if attack_rec.hit:
            if not attacker.dead and defender.will_react_to_attack(attacker):
                self.attack("counterattack", defender, attacker)
            if attacker.dead:
                attacker.triggers("post_attack")
                defender.triggers("post_defense")
                self._action_stack.pop()
                return

            succeeded, attempted, parry_rec = self.parry(defender, attacker)
            attacker.was_parried = attempted
            if parry_rec:
                attack_rec.children.append(parry_rec)
            if not succeeded:
                dmg_rec = attacker.deal_damage(defender.tn, extra_damage=not attempted)
                attack_rec.children.append(dmg_rec)
                wc_rec = defender.wound_check(dmg_rec.light, dmg_rec.serious)
                if wc_rec:
                    attack_rec.children.append(wc_rec)
        else:
            attacker.was_parried = False
            for d in [defender] + defender.adjacent:
                if d.predeclare_bonus or (d is defender and was_forced):
                    d.make_parry()
                    d.triggers("successful_parry")

        attacker.triggers("post_attack")
        if not defender.dead:
            defender.triggers("post_defense")

        # Pop the sentinel and collect the real attack record
        self._action_stack.pop()
        # Transfer nested counterattack children from the sentinel
        attack_rec.children.extend(parent_record.children)

        if self._action_stack:
            # Nested counterattack — add as child of parent
            self._action_stack[-1].children.append(attack_rec)
        elif hasattr(self, "phase") and self.combat_record.rounds:
            # Top-level action — add to phase list
            current_round = self.combat_record.rounds[-1]
            if self.phase < len(current_round.phases):
                current_round.phases[self.phase].append(attack_rec)

    def round(self) -> None:
        """Execute one full combat round: initiative, phases 0-10, cleanup.

        Each phase loops until no one takes an action (multiple combatants
        can act in the same phase). Dead combatants are removed between
        phases to keep the action list clean.
        """
        round_num = len(self.combat_record.rounds) + 1
        round_rec = RoundRecord(round_num=round_num)
        self.combat_record.rounds.append(round_rec)

        for c in self.combatants:
            c.triggers("pre_round")
            init_rec = c.initiative()
            if init_rec:
                round_rec.initiatives.append(init_rec)
        self.combatants.sort(key=lambda c: c.init_order)

        # Pre-allocate phase action lists
        round_rec.phases = [[] for _ in range(11)]

        for phase in range(11):
            self.phase = phase
            for c in self.combatants:
                c.phase = phase

            action_taken = True
            while action_taken:
                action_taken = False
                for attacker in self.combatants:
                    if not attacker.dead:
                        action = attacker.choose_action()
                        if action:
                            action_taken = True
                            knack, defender = action
                            self.attack(knack, attacker, defender)
                            for combatant in [attacker, defender]:
                                if combatant.dead:
                                    combatant.triggers("death")
                                    self.formation.death(combatant)
                            if self.finished:
                                return

            self.combatants = [c for c in self.combatants if not c.dead]

        for c in self.combatants:
            c.triggers("post_round")
