"""Build progressions for the Ikoma Bard school."""

from __future__ import annotations

from l7r.builders import Progression


class IkomaBardProgression(Progression):
    """Standard Ikoma Bard progression.

    Ring ordering rationale:
    - Fire first (school ring; drives attack and damage dice pools).
    - Void next (initiative, VPs, survivability).
    - Earth (serious wound buffer — Bard takes hits while forcing
      parries on enemies).
    - Air (parry defense).
    - Water last (wound checks; not primary defense mechanism).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("void", 3), ("earth", 3), ("air", 3), ("water", 3),
        ("knacks", 4),  # R4T: fire 3→4
        ("fire", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("void", 4), ("earth", 4), ("air", 4), ("water", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("fire", 6),
        ("void", 5), ("earth", 5), ("air", 5), ("water", 5),
    ]
