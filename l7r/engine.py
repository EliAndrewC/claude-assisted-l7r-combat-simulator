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

from l7r.types import RollType

if TYPE_CHECKING:
    from l7r.combatant import Combatant
    from l7r.formations import Formation


class Engine:
    """Runs a combat encounter from start to finish.

    Owns the phase clock, the combat log, and resolves the attack/parry/
    damage sequence. Delegates tactical decisions to each Combatant's heuristic
    methods and formation bookkeeping to the Formation object.
    """

    def __init__(self, formation: Formation) -> None:
        self.formation = formation
        self.combatants = formation.combatants
        self.messages: list[str] = []
        """Per-combat log of all messages produced during this fight."""

    def log(self, message: str) -> None:
        """Append a message to the combat log and print it."""
        self.messages.append(message)
        print(message)

    @property
    def finished(self) -> bool:
        """Combat ends when one side has no living combatants."""
        return self.formation.one_side_finished

    def fight(self) -> None:
        """Run the full combat: pre-fight triggers, then rounds until one
        side is eliminated."""
        for c in self.combatants:
            c.engine = self
            c.triggers("pre_fight")

        while not self.finished:
            self.round()

    def parry(self, defender: Combatant, attacker: Combatant) -> tuple[bool, bool]:
        """Give the defender (and their allies) a chance to parry.

        Returns (succeeded, attempted): succeeded means the parry blocked
        the hit; attempted means someone tried even if they failed. This
        distinction matters because a failed parry still negates the
        attacker's bonus damage dice from exceeding the TN.
        """
        if defender.will_parry():
            return defender.make_parry(), True

        for def_ally in defender.adjacent:
            if attacker in def_ally.attackable and def_ally.will_parry_for(defender, attacker):
                return def_ally.make_parry_for(defender, attacker), True

        return False, False

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
        self.log(f"Phase #{self.phase}: {attacker.name} {knack} vs {defender.name}")

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
            return

        attacker.attack_knack = knack
        defender.enemy = attacker
        attacker.enemy = defender
        attacker.triggers("pre_attack")
        defender.triggers("pre_defense")

        if not defender.will_predeclare():
            for def_ally in defender.adjacent:
                if attacker in def_ally.attackable and def_ally.will_predeclare_for(defender, attacker):
                    break

        if attacker.make_attack():
            succeeded, attempted = self.parry(defender, attacker)
            attacker.was_parried = attempted
            if not succeeded:
                light, serious = attacker.deal_damage(defender.tn, extra_damage=not attempted)
                defender.wound_check(light, serious)
        else:
            attacker.was_parried = False
            for d in [defender] + defender.adjacent:
                if d.predeclare_bonus:
                    d.make_parry()
                    d.triggers("successful_parry")

        attacker.triggers("post_attack")
        if not defender.dead:
            defender.triggers("post_defense")

    def round(self) -> None:
        """Execute one full combat round: initiative, phases 0-10, cleanup.

        Each phase loops until no one takes an action (multiple combatants
        can act in the same phase). Dead combatants are removed between
        phases to keep the action list clean.
        """
        for c in self.combatants:
            c.triggers("pre_round")
            c.initiative()
        self.combatants.sort(key=lambda c: c.init_order)

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
