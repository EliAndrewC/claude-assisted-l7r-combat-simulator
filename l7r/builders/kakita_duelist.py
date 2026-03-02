"""Build progressions for the Kakita Bushi school."""

from __future__ import annotations

from l7r.builders import Progression


class KakitaDuelistProgression(Progression):
    """Standard Kakita Bushi progression.

    Kakita is an iaijutsu-focused duelist who acts first (10s on
    initiative become phase 0) and gains bonuses when acting before
    the enemy.  hold_one_action is False — every action is spent
    offensively.  Despite this, sw_parry_threshold=3 means the school
    parries aggressively when taking serious wounds.

    Ring ordering rationale:
    - Air first (drives initiative and parry TN; sw_parry_threshold=3
      means Kakita parries aggressively despite hold_one_action=False,
      so Air provides both offensive timing and defensive value).
    - Water next (wound checks and survivability; staying alive to
      exploit the timing advantage is critical).
    - Void (initiative, VPs; helps sustain the early-action advantage
      that R3T bonuses depend on).
    - Earth last (wound buffer; lowest priority since Air and Water
      cover the defensive needs more directly).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("air", 3), ("water", 3), ("void", 3), ("earth", 3),
        ("knacks", 4),  # R4T: fire 3→4
        ("fire", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("air", 4), ("water", 4), ("void", 4), ("earth", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("fire", 6),
        ("air", 5), ("water", 5), ("void", 5), ("earth", 5),
    ]
