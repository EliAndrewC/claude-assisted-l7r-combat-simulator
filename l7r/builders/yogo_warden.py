"""Build progressions for the Yogo Warden school."""

from __future__ import annotations

from l7r.builders import Progression


class YogoWardenProgression(Progression):
    """Standard Yogo Warden progression.

    Yogo Warden is an Earth-based tank: gains VPs from taking serious
    wounds (SA), heals light wounds when spending VPs (R3T), and gets
    extra wound check bonuses from VP spending (R4T).

    Ring ordering rationale:
    - Water first (wound checks — survivability is the whole strategy;
      R1T boosts wound checks and R2T gives a free raise on them).
    - Fire next (attack rolls and damage dice — once VPs are built up
      from tanking, the Warden needs to deal damage).
    - Void (initiative and VP ceiling; higher Void means more base VPs
      before the SA starts generating extras).
    - Air last (not parry-focused; the Warden tanks hits rather than
      avoiding them, since taking serious wounds generates VPs).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("water", 3), ("fire", 3), ("void", 3), ("air", 3),
        ("knacks", 4),  # R4T: earth 3→4
        ("earth", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("water", 4), ("fire", 4), ("void", 4), ("air", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("earth", 6),
        ("water", 5), ("fire", 5), ("void", 5), ("air", 5),
    ]
