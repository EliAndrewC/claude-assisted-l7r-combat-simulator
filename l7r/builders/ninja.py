"""Build progression for the Ninja profession."""

from __future__ import annotations

from l7r.builders import ProfessionalProgression


class NinjaProgression(ProfessionalProgression):
    """Standard Ninja progression.

    Ninja are covert fighters who raise their own TN to gain bonus
    damage, lower action dice for faster attacks, and debuff enemy
    damage rolls. Their ability order prioritises offensive pressure
    (difficult_attack, fast_attacks) before layering in defences.
    """

    ability_order = [
        "ninja_difficult_attack",
        "ninja_fast_attacks",
        "ninja_wc_bump",
        "ninja_attack_bonus",
        "ninja_difficult_attack",
        "ninja_damage_bump",
        "ninja_sincerity",
        "ninja_stealth_unseen",
        "ninja_stealth_unnoticed",
        "ninja_damage_roll",
        "ninja_better_tn",
        "ninja_fast_attacks",
        "ninja_wc_bump",
        "ninja_attack_bonus",
        "ninja_damage_bump",
        "ninja_sincerity",
        "ninja_stealth_unseen",
        "ninja_stealth_unnoticed",
        "ninja_damage_roll",
        "ninja_better_tn",
    ]

    steps = [
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("water", 3), ("void", 3), ("fire", 3), ("earth", 3), ("air", 3),
        ("attack", 3),
        ("parry", 4),
        ("water", 4), ("void", 4), ("fire", 4), ("earth", 4), ("air", 4),
        ("attack", 4),
        ("parry", 5),
        ("water", 5), ("void", 5), ("fire", 5), ("earth", 5), ("air", 5),
        ("attack", 5),
    ]
