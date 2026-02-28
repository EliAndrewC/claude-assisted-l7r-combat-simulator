from __future__ import annotations

from l7r.combatant import Combatant
from l7r.dice import d10, actual_xky
from l7r.records import DiceRoll, DieResult
from l7r.types import RollType


class ShosuroActor(Combatant):
    """Shosuro Actor school (Scorpion clan). Extra dice from acting skill.

    Strategy: Air-based versatile fighter. The acting skill (equal to
    school rank) provides extra rolled dice on attack, parry, and wound
    check. At high rank, adds the lowest dice to the roll total.

    Special ability: Extra rolled dice equal to school rank on attack,
    parry, and wound check rolls (representing acting/deception skill
    enhancing combat through unpredictability).
    School ring: Air.
    School knacks: athletics, discern honor, pontificate.

    Key techniques:
    - R1T: Extra rolled die on attack, wound check.
    - R2T: Free raise (+5) on sincerity (non-combat; pontificate as
      closest combat-relevant knack).
    - R3T: 10 shared free raises on attack + wound check.
    - R4T: +1 Air (free). Stipend bonus (non-combat, skipped).
    - R5T: After any roll, add lowest 3 of ALL rolled dice to result.
      Some dice may be counted twice (e.g. 3k3 doubles the roll).
    """

    school_knacks: list[RollType] = ["athletics", "discern_honor", "pontificate"]
    r1t_rolls: list[RollType] = ["attack", "wound_check"]
    r2t_rolls: RollType = "pontificate"
    school_ring = "air"
    r4t_ring_boost = "air"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        # SA: Extra rolled dice = rank on attack, parry, wound_check (for simplicity, we assume acting skill is equal to school rank)
        for roll_type in ["attack", "parry", "wound_check"]:
            self.extra_dice[roll_type][0] += self.rank

        if self.rank >= 3:
            raises = [5] * 10
            for roll_type in ["attack", "wound_check"]:
                self.multi[roll_type].append(raises)

    def xky(self, roll: int, keep: int, reroll: bool, roll_type: RollType) -> int:
        """R5T: After rolling, add lowest 3 of ALL rolled dice to result.

        "Add your lowest three dice to the result. (Some dice may be
        counted twice.)"  The lowest 3 are chosen from the full pool,
        so kept dice can be counted twice.  E.g. 4k3 rolling
        [9,6,5,2] keeps [9,6,5]=20, adds [2,5,6]=13, total=33.
        If rolling 3k3, all dice are doubled.
        """
        if self.rank < 5:
            return Combatant.xky(self, roll, keep, reroll, roll_type)

        roll, keep, bonus = actual_xky(roll, keep)
        dice = sorted([d10(reroll) for _ in range(roll)])

        # Keep the top 'keep' dice as normal
        kept_total = sum(dice[-keep:]) if keep else 0

        # Add the lowest 3 of ALL rolled dice (may overlap with kept)
        lowest_3 = dice[:min(3, len(dice))]
        extra = sum(lowest_3)

        total = bonus + kept_total + extra

        # Build DiceRoll record
        die_results = []
        for i, face in enumerate(dice):
            die_results.append(DieResult(
                face=face,
                kept=i >= len(dice) - keep,
                exploded=face > 10,
            ))
        self.last_dice_roll = DiceRoll(
            roll=roll, keep=keep, reroll=reroll,
            dice=die_results, overflow_bonus=bonus, total=total,
        )
        return total
