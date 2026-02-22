"""
Character build progressions for the L7R combat simulator.

A Progression defines how XP is spent when building a character of a given
school.  Each school can have multiple progressions (e.g. a standard build
vs a duelist-focused build), keeping build strategy separate from the core
combat classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from l7r.combatant import Combatant

RINGS = ("air", "earth", "fire", "water", "void")
SKILL_MAX = 5


class Progression:
    """Base class for character build progressions.

    Subclasses set ``school_class`` and ``steps`` as class attributes.
    The :func:`build` function walks ``steps`` and spends XP accordingly.

    Attributes:
        school_class: The school this progression is for.
        steps: Sequential list of (category, target_level) pairs that the
            builder processes in order, spending XP for each raise until
            the budget runs out.

    Step categories:
        ("knacks", N)      — Raise all school_knacks to level N (max 5).
                             When N reaches 4, apply r4t_ring_boost for free.
        ("air", N)         — Raise Air ring to N (ring costs).
        ("earth", N)       — Raise Earth ring to N.
        ("fire", N)        — Raise Fire ring to N.
        ("water", N)       — Raise Water ring to N.
        ("void", N)        — Raise Void ring to N.
                             School ring costs 5 fewer XP at 4+ (if 4th Dan).
                             Max 6 for school ring, 5 for others.
                             Skips if already at or above N.
        ("attack", N)      — Raise attack skill to N (basic skill costs, max 5).
        ("parry", N)       — Raise parry skill to N (basic skill costs, max 5).
    """

    school_class: type[Combatant]
    steps: list[tuple[str, int]] = []


# -----------------------------------------------------------
# XP cost helpers
# -----------------------------------------------------------


def _ring_cost(new_value: int, *, discount: bool) -> int:
    """XP cost to raise a ring by one point to *new_value*.

    Base cost is ``5 × new_value``.  After reaching 4th Dan, the school
    ring gets a 5 XP discount on each raise.
    """
    cost = 5 * new_value
    if discount:
        cost -= 5
    return cost


def _basic_skill_cost(new_value: int) -> int:
    """XP cost to raise a basic skill (attack / parry) by one point.

    2 XP for ranks 1–2, 3 XP for ranks 3–5.
    """
    return 2 if new_value <= 2 else 3


def _advanced_skill_cost(new_value: int) -> int:
    """XP cost to raise an advanced skill (school knack) by one point.

    4 XP for ranks 1–2, ``2 × new_value`` for ranks 3–5.
    """
    return 4 if new_value <= 2 else 2 * new_value


# -----------------------------------------------------------
# Builder
# -----------------------------------------------------------


def build(
    progression: type[Progression],
    xp: int = 150,
    earned_xp: int = 0,
    non_combat_pct: float = 0.2,
) -> Combatant:
    """Build a character from a progression class and XP budget.

    Args:
        progression: A :class:`Progression` subclass whose ``steps`` and
            ``school_class`` define the build order and school.
        xp: Base creation XP (default 150).
        earned_xp: Additional earned XP from adventures.
        non_combat_pct: Fraction of total XP reserved for non-combat
            skills (subtracted from the combat budget).

    Returns:
        An instance of the progression's school class with stats derived
        from walking the progression steps until the budget runs out.
    """
    school = progression.school_class
    budget = round((xp + earned_xp) * (1 - non_combat_pct))

    # --- starting values (from rules: 01-character_creation.md) ---
    rings: dict[str, int] = {r: 2 for r in RINGS}
    if school.school_ring:
        rings[school.school_ring] = 3

    knacks: dict[str, int] = {k: 1 for k in school.school_knacks}
    skills: dict[str, int] = {"attack": 0, "parry": 0}

    r4t_reached = False

    # --- walk progression steps ---
    for category, target in progression.steps:
        if budget <= 0:
            break

        if category == "knacks":
            for knack in school.school_knacks:
                cap = min(target, SKILL_MAX)
                while knacks[knack] < cap:
                    cost = _advanced_skill_cost(knacks[knack] + 1)
                    if cost > budget:
                        break
                    budget -= cost
                    knacks[knack] += 1

            # R4T: free ring boost when all knacks reach 4
            if not r4t_reached and min(knacks.values()) >= 4:
                r4t_reached = True
                if school.r4t_ring_boost:
                    rings[school.r4t_ring_boost] += 1

        elif category in RINGS:
            ring_max = 6 if category == school.school_ring else 5
            discount = category == school.school_ring and r4t_reached
            cap = min(target, ring_max)
            while rings[category] < cap:
                cost = _ring_cost(rings[category] + 1, discount=discount)
                if cost > budget:
                    break
                budget -= cost
                rings[category] += 1

        elif category in ("attack", "parry"):
            cap = min(target, SKILL_MAX)
            while skills[category] < cap:
                cost = _basic_skill_cost(skills[category] + 1)
                if cost > budget:
                    break
                budget -= cost
                skills[category] += 1

    # --- assemble kwargs and instantiate ---
    kwargs: dict[str, int] = {}
    kwargs.update(rings)
    kwargs.update(skills)
    kwargs.update(knacks)
    kwargs["xp"] = xp + earned_xp

    return school(**kwargs)
