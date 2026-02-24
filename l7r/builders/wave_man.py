"""Build progression for the Wave Man profession."""

from __future__ import annotations

from l7r.builders import ProfessionalProgression


class WaveManProgression(ProfessionalProgression):
    """Standard Wave Man progression.

    Wave men are non-samurai fighters who rely on durability, damage
    compensation, and turning near-misses into hits. Their ability
    order prioritises survivability (near_miss, wc_bonus) before
    pushing damage output (damage_round_up, damage_compensator).
    """

    ability_order = [
        "wave_man_near_miss",
        "wave_man_wc_bonus",
        "wave_man_damage_round_up",
        "wave_man_near_miss",
        "wave_man_crippled_reroll",
        "wave_man_wound_reduction",
        "wave_man_wound_reduction",
        "wave_man_damage_round_up",
        "wave_man_init_bonus",
        "wave_man_wc_bonus",
        "wave_man_damage_compensator",
        "wave_man_difficult_parry",
        "wave_man_parry_bypass",
        "wave_man_tougher_wounds",
        "wave_man_init_bonus",
        "wave_man_crippled_reroll",
        "wave_man_damage_compensator",
        "wave_man_difficult_parry",
        "wave_man_parry_bypass",
        "wave_man_tougher_wounds",
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
