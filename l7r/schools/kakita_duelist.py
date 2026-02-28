from __future__ import annotations

import random

from l7r.combatant import Combatant
from l7r.dice import d10
from l7r.records import DieResult, InitiativeRecord
from l7r.types import RollType


class KakitaDuelist(Combatant):
    """Kakita Bushi school (Crane clan). An iaijutsu-focused duelist.

    Strategy: Act first (10s on initiative become phase 0), land iaijutsu
    strikes for bonus damage, and exploit timing advantages when acting
    before the opponent.

    Special ability: (Not explicitly coded as a separate trigger here.)
    School ring: Fire.
    School knacks: double attack, iaijutsu, lunge.

    Key techniques:
    - R1T: Extra rolled die on double attack, iaijutsu, initiative.
    - R2T: Free raise (+5) on iaijutsu.
    - R3T: Bonus to all rolls when acting before the enemy's next action.
    - R4T: +5 flat damage on successful iaijutsu hits.
    - R5T: Free iaijutsu duel at the start of each round (before initiative).

    Never holds actions because fast action is the school's core identity.
    Custom initiative turns 10s into 0s (acts in phase 0, before everyone).
    """

    hold_one_action = False
    school_knacks: list[RollType] = ["double_attack", "iaijutsu", "lunge"]
    r1t_rolls: list[RollType] = ["double_attack", "iaijutsu", "initiative"]
    r2t_rolls: RollType = "iaijutsu"
    school_ring = "fire"
    r4t_ring_boost = "fire"
    sw_parry_threshold = 3

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        self.events["successful_attack"].append(self.r4t_trigger)
        self.events["pre_round"].append(self.r5t_trigger)

    def r4t_trigger(self) -> None:
        """R4T: +5 flat damage bonus on successful iaijutsu attacks."""
        if self.rank >= 4 and self.attack_knack == "iaijutsu":
            self.auto_once["damage"] += 5

    def r5t_trigger(self) -> None:
        """R5T: At the start of each round, make a free contested iaijutsu
        roll against a target. If we win, deal damage with bonus dice
        based on how much we exceeded the opponent's roll."""
        if self.rank == 5:
            target = self.att_target()
            knack = "iaijutsu" if target.iaijutsu else "attack"
            bonus = 5 + 5 * (self.iaijutsu - getattr(target, knack)) + (0 if target.iaijutsu else 5)
            roll, keep = self.att_dice("iaijutsu")
            our_total = self.xky(roll, keep, not self.crippled, "iaijutsu") + bonus

            roll, keep = target.att_dice(knack)
            enemy_total = target.xky(roll, keep) + target.always[knack]

            roll, keep = self.damage_dice
            roll += (our_total - enemy_total) // 5
            damage = self.xky(roll, keep, True, "damage") + 5
            target.wound_check(damage)

    def initiative(self) -> InitiativeRecord:
        """Custom initiative: 10s become 0s (act in phase 0, before everyone
        else). This is the core of the Kakita's speed advantage."""
        roll, keep = self.init_dice
        dice = [d10(False) for i in range(roll)]
        self.actions = [(0 if die == 10 else die) for die in dice][:keep]
        self.init_order = self.actions[:]

        die_results = [
            DieResult(face=v, kept=i < keep, exploded=False)
            for i, v in enumerate(dice)
        ]
        return InitiativeRecord(combatant=self.name, dice=die_results, kept=self.actions[:])

    def r3t_bonus(self) -> int:
        """R3T: Gain a bonus when acting before the enemy's next action.
        The earlier we act relative to the enemy, the bigger the bonus.
        Returns 0 if the enemy acts in the same or earlier phase."""
        if not hasattr(self, "enemy"):
            return 0
        bonus = 0
        next = self.enemy.actions[0] if self.enemy.actions else 11
        if self.phase < next:
            bonus += self.attack * (next - self.phase)
        return bonus

    def _r3t_bonus_vs(self, enemy: Combatant) -> int:
        """R3T bonus if we were attacking this specific enemy."""
        if self.rank < 3:
            return 0
        next_action = enemy.actions[0] if enemy.actions else 11
        if self.phase < next_action:
            return self.attack * (next_action - self.phase)
        return 0

    def att_target(self, knack: RollType = "attack") -> Combatant:
        """Choose target using effective TN that accounts for R3T timing bonus.

        Enemies whose next action is far away are effectively easier to hit
        because the R3T bonus applies, so we factor that into target selection.
        """
        min_tn = min(e.tn - self._r3t_bonus_vs(e) for e in self.attackable)
        targets = [
            e for e in self.attackable
            if knack != "double_attack" or e.tn - self._r3t_bonus_vs(e) == min_tn
        ]
        return random.choice(
            sum(
                [
                    [e] * (1 + e.serious + (30 - e.tn + self._r3t_bonus_vs(e)) // 5
                           + len(e.init_order) - len(e.actions))
                    for e in targets
                ],
                [],
            )
        )

    def max_bonus(self, roll_type: RollType) -> int:
        return Combatant.max_bonus(self, roll_type) + self.r3t_bonus()

    def disc_bonus(self, roll_type: RollType, needed: int) -> int:
        bonus = self.r3t_bonus()
        return bonus + Combatant.disc_bonus(self, roll_type, needed - bonus)

    def choose_action(self) -> tuple[RollType, Combatant] | None:
        if not self.actions or self.actions[0] > self.phase:
            # No current-phase action. Consider interrupt iaijutsu.
            if len(self.actions) >= 2:
                target = max(self.attackable,
                             key=lambda e: self.projected_damage(e, True))
                damage = self.projected_damage(target, True)
                if damage >= 2:  # >= 2 anticipated serious wounds
                    self.actions[-2:] = []
                    return "iaijutsu", target
            return None

        self.actions.pop(0)

        # Phase 0 actions always use iaijutsu
        if self.phase == 0:
            return "iaijutsu", self.att_target("iaijutsu")

        # Prefer regular attack over double attack if double would need VPs
        if self.double_attack:
            tn = min(e.tn - self._r3t_bonus_vs(e) for e in self.attackable)
            datt_prob = self.att_prob("double_attack", tn + 20)
            att_prob = self.att_prob("attack", tn)
            if (att_prob - datt_prob <= self.datt_threshold
                    and datt_prob >= self.vp_fail_threshold):
                return "double_attack", self.att_target("double_attack")

        return "attack", self.att_target("attack")
