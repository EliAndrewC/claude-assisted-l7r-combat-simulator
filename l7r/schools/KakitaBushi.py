from __future__ import annotations

from l7r.combatant import Combatant
from l7r.dice import d10
from l7r.types import RollType


class KakitaBushi(Combatant):
    """Kakita Bushi school (Crane clan). An iaijutsu-focused duelist.

    Strategy: Act first (10s on initiative become phase 0), land iaijutsu
    strikes for bonus damage, and exploit timing advantages when acting
    before the opponent.

    Special ability: (Not explicitly coded as a separate trigger here.)
    School ring: Air.
    School knacks: double attack, iaijutsu, lunge.

    Key techniques:
    - R1T: Extra rolled die on attack, double attack, iaijutsu.
    - R2T: Free raise (+5) on iaijutsu.
    - R3T: Bonus to all rolls when acting before the enemy's next action.
    - R4T: +5 flat damage on successful iaijutsu hits.
    - R5T: Free iaijutsu duel at the start of each round (before initiative).

    Never holds actions because fast action is the school's core identity.
    Custom initiative turns 10s into 0s (acts in phase 0, before everyone).
    """

    hold_one_action: bool = False
    school_knacks: list[RollType] = ["double_attack", "iaijutsu", "lunge"]
    r1t_rolls: list[RollType] = ["attack", "double_attack", "iaijutsu"]
    r2t_rolls: RollType = "iaijutsu"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        self.events["successful_attack"].append(self.r4t_trigger)
        self.events["pre_round"].append(self.r5t_trigger)

    def r4t_trigger(self, enemy: Combatant) -> None:
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

    def initiative(self) -> None:
        """Custom initiative: 10s become 0s (act in phase 0, before everyone
        else). This is the core of the Kakita's speed advantage."""
        roll, keep = self.init_dice
        dice = [d10(False) for i in range(roll)]
        self.actions = [(0 if die == 10 else die) for die in dice][:keep]
        self.init_order = self.actions[:]
        self.log(f"initiative: {self.actions}", indent=0)

    def r3t_bonus(self) -> int:
        """R3T: Gain a bonus when acting before the enemy's next action.
        The earlier we act relative to the enemy, the bigger the bonus.
        Returns 0 if the enemy acts in the same or earlier phase."""
        bonus = 0
        next = self.enemy.actions[0] if self.enemy.actions else 11
        if self.phase < next:
            bonus += self.attack * (self.phase - next)
        return bonus

    def max_bonus(self, roll_type: RollType) -> int:
        return Combatant.max_bonus(self, roll_type) + self.r3t_bonus()

    def disc_bonus(self, roll_type: RollType, needed: int) -> int:
        bonus = self.r3t_bonus()
        return bonus + Combatant.disc_bonus(roll_type, needed - bonus)

    def choose_action(self) -> tuple[RollType, Combatant] | None:
        pass  # TODO
