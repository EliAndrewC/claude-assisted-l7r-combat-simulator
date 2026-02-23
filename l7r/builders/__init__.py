"""
Character build progressions for the L7R combat simulator.

A Progression defines how XP is spent when building a character of a given
school.  Each school can have multiple progressions (e.g. a standard build
vs a duelist-focused build), keeping build strategy separate from the core
combat classes.
"""

from __future__ import annotations

import importlib
import re
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
        steps: Sequential list of ``(name, target)`` tuples.  Each entry
            names a stat to raise and the value it should reach.  The
            builder tracks current values (rings start at 2, school ring
            at 3, knacks at 1, skills at 1) and validates that every
            target is exactly ``current + 1`` before applying costs.

    Step types:
        ("knacks", N)  — Raise each school knack to N (from N−1).
                         If all knacks reach 4, apply r4t_ring_boost for
                         free.
        ("air", N)     — Raise Air ring to N (max 5, or 6 if school ring).
        ("earth", N)   — Raise Earth ring to N.
        ("fire", N)    — Raise Fire ring to N.
        ("water", N)   — Raise Water ring to N.
        ("void", N)    — Raise Void ring to N.
                         School ring costs 5 fewer XP after 4th Dan.
        ("attack", N)  — Raise attack skill to N (advanced skill costs, max 5).
        ("parry", N)   — Raise parry skill to N (advanced skill costs, max 5).
    """

    school_class: type[Combatant] | None = None
    steps: list[tuple[str, int]] = []


# -----------------------------------------------------------
# School class resolution
# -----------------------------------------------------------


def _resolve_school_class(progression: type[Progression]) -> type[Combatant]:
    """Return the school class for a progression.

    If ``school_class`` is set explicitly, return it.  Otherwise
    derive the school name by stripping the ``Progression`` suffix
    from the class name, convert to snake_case for the module path,
    and import the CamelCase class from that module.
    """
    if progression.school_class is not None:
        return progression.school_class
    class_name = progression.__name__.removesuffix("Progression")
    module_name = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", class_name).lower()
    mod = importlib.import_module(f"l7r.schools.{module_name}")
    return getattr(mod, class_name)


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
# Validation
# -----------------------------------------------------------


def _validate_progression(progression: type[Progression]) -> None:
    """Dry-run a progression to verify every step target is correct.

    Simulates the full progression with infinite XP, checking that each
    ``(name, target)`` step has ``target == current_value + 1``.  Raises
    :class:`ValueError` if any step is inconsistent.
    """
    school = _resolve_school_class(progression)

    rings: dict[str, int] = {r: 2 for r in RINGS}
    if school.school_ring:
        rings[school.school_ring] = 3

    knacks: dict[str, int] = {k: 1 for k in school.school_knacks}
    skills: dict[str, int] = {"attack": 1, "parry": 1}
    r4t_reached = False

    for step_name, target in progression.steps:
        if step_name == "knacks":
            if target > SKILL_MAX:
                raise ValueError(
                    f"knack target {target} exceeds max {SKILL_MAX}"
                )
            for knack in school.school_knacks:
                if knacks[knack] != target - 1:
                    raise ValueError(
                        f"knack '{knack}' is at {knacks[knack]}, "
                        f"expected {target - 1} before raising to {target}"
                    )
            for knack in school.school_knacks:
                knacks[knack] = target

            if not r4t_reached and min(knacks.values()) >= 4:
                r4t_reached = True
                if school.r4t_ring_boost:
                    rings[school.r4t_ring_boost] += 1

        elif step_name in RINGS:
            ring_max = 6 if step_name == school.school_ring else 5
            if target > ring_max:
                raise ValueError(
                    f"ring '{step_name}' target {target} exceeds "
                    f"max {ring_max}"
                )
            if rings[step_name] != target - 1:
                raise ValueError(
                    f"ring '{step_name}' is at {rings[step_name]}, "
                    f"expected {target - 1} before raising to {target}"
                )
            rings[step_name] = target

        elif step_name in ("attack", "parry"):
            if target > SKILL_MAX:
                raise ValueError(
                    f"skill '{step_name}' target {target} exceeds "
                    f"max {SKILL_MAX}"
                )
            if skills[step_name] != target - 1:
                raise ValueError(
                    f"skill '{step_name}' is at {skills[step_name]}, "
                    f"expected {target - 1} before raising to {target}"
                )
            skills[step_name] = target

        else:
            raise ValueError(f"unknown step name: {step_name!r}")


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
    _validate_progression(progression)

    school = _resolve_school_class(progression)
    budget = round((xp + earned_xp) * (1 - non_combat_pct))

    # --- starting values (from rules: 01-character_creation.md) ---
    rings: dict[str, int] = {r: 2 for r in RINGS}
    if school.school_ring:
        rings[school.school_ring] = 3

    knacks: dict[str, int] = {k: 1 for k in school.school_knacks}
    skills: dict[str, int] = {"attack": 1, "parry": 1}

    r4t_reached = False

    # --- walk progression steps ---
    for step_name, target in progression.steps:
        if budget <= 0:
            break

        if step_name == "knacks":
            for knack in school.school_knacks:
                current = knacks[knack]
                if current != target - 1:
                    continue
                cost = _advanced_skill_cost(target)
                if cost <= budget:
                    budget -= cost
                    knacks[knack] = target

            # R4T: free ring boost when all knacks reach 4
            if not r4t_reached and min(knacks.values()) >= 4:
                r4t_reached = True
                if school.r4t_ring_boost:
                    rings[school.r4t_ring_boost] += 1

        elif step_name in RINGS:
            current = rings[step_name]
            if current != target - 1:
                continue
            discount = step_name == school.school_ring and r4t_reached
            cost = _ring_cost(target, discount=discount)
            if cost <= budget:
                budget -= cost
                rings[step_name] = target

        elif step_name in ("attack", "parry"):
            current = skills[step_name]
            if current != target - 1:
                continue
            cost = _advanced_skill_cost(target)
            if cost <= budget:
                budget -= cost
                skills[step_name] = target

    # --- assemble kwargs and instantiate ---
    kwargs: dict[str, int] = {}
    kwargs.update(rings)
    kwargs.update(skills)
    kwargs.update(knacks)
    kwargs["xp"] = xp + earned_xp

    return school(**kwargs)
