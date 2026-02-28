"""
Dice rolling primitives for the XkY system.

All rolls in this game use the "roll X, keep Y" (XkY) notation: roll X
ten-sided dice, keep the Y highest, and sum them. Dice that show a 10 may
"explode" — they are rerolled and the new result is added to the 10, which
can chain indefinitely. Crippled characters don't reroll 10s on skill rolls.

When a dice pool exceeds 10 rolled or 10 kept, overflow is converted:
rolled dice above 10 become extra kept dice, and kept dice above 10 become
a flat +2 bonus per extra die.
"""

from random import randrange

from l7r.data import prob
from l7r.records import DiceRoll, DieResult


def avg(reroll: bool, roll: int, keep: int) -> float:
    """
    Since we only record averages up to 10k10, if someone asks for the average
    of something higher than that, we need to estimate a value.  Since anything
    above 10k10 just rolls 10k10 and gets a bonus of 2 times the number of extra
    rolled and kept dice, and we know 10k10 is ~61, we return that estimate.
    """
    return prob[reroll][roll, keep] or (61 + 2 * (roll + keep - 20))


def d10(reroll: bool = True) -> int:
    """Roll a single d10, optionally exploding on 10s.

    When reroll is True, a 10 "explodes": we keep rolling and adding until
    the die shows something other than 10. This means a single die can
    produce arbitrarily high values (10, 20, 30...), making even small
    dice pools capable of extreme results.
    """
    total = die = randrange(1, 11)
    while reroll and die == 10:
        die = randrange(1, 11)
        total += die
    return total


def actual_xky(roll: int, keep: int) -> tuple[int, int, int]:
    """Cap a dice pool at 10k10 per the overflow rules.

    Rolled dice above 10 are converted to extra kept dice (e.g. 12k4
    becomes 10k6). Kept dice above 10 are converted to a flat +2 bonus
    per extra die (e.g. 10k12 becomes 10k10+4). This is needed because
    our probability tables only go up to 10k10.
    """
    bonus = 0
    if roll > 10:
        keep += roll - 10
        roll = 10
    if keep > 10:
        bonus = keep - 10
        keep = 10

    return roll, keep, bonus


def xky(roll: int, keep: int, reroll: bool = True) -> int:
    """Roll X dice, keep the Y highest, sum them. The core dice mechanic.

    Applies overflow rules via actual_xky first, then rolls individual d10s,
    sorts them, keeps the highest, and adds any overflow bonus.
    """
    roll, keep, bonus = actual_xky(roll, keep)
    return bonus + sum(sorted(d10(reroll) for i in range(roll))[-keep:])


def d10_detailed(reroll: bool = True) -> DieResult:
    """Roll a single d10, returning full detail as a DieResult.

    Same logic as d10() but captures whether the die exploded.
    The ``kept`` field defaults to True; callers (xky_detailed)
    update it based on pool selection.
    """
    total = die = randrange(1, 11)
    exploded = False
    while reroll and die == 10:
        exploded = True
        die = randrange(1, 11)
        total += die
    return DieResult(face=total, kept=True, exploded=exploded)


def xky_detailed(roll: int, keep: int, reroll: bool = True) -> DiceRoll:
    """Roll XkY returning individual dice detail as a DiceRoll.

    Same logic as xky() but returns a DiceRoll with per-die information
    including which dice were kept and which exploded.
    """
    roll, keep, bonus = actual_xky(roll, keep)
    dice = sorted(
        [d10_detailed(reroll) for _ in range(roll)],
        key=lambda d: d.face,
    )
    for d in dice:
        d.kept = False
    for d in dice[-keep:]:
        d.kept = True
    total = bonus + sum(d.face for d in dice if d.kept)
    return DiceRoll(
        roll=roll, keep=keep, reroll=reroll,
        dice=dice, overflow_bonus=bonus, total=total,
    )
