"""Build progressions for the Shosuro Actor school."""

from __future__ import annotations

from l7r.builders import Progression


class ShosuroActorProgression(Progression):
    """Standard Shosuro Actor progression.

    Ring ordering rationale:
    - Air first (school ring; drives parry dice pool).
    - Fire next (attack and damage dice pools).
    - Void (initiative, VPs, survivability).
    - Earth (serious wound buffer).
    - Water last (wound checks; SA already provides extra rolled dice).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("fire", 3), ("void", 3), ("earth", 3), ("water", 3),
        ("knacks", 4),  # R4T: air 3→4
        ("air", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("fire", 4), ("void", 4), ("earth", 4), ("water", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("air", 6),
        ("fire", 5), ("void", 5), ("earth", 5), ("water", 5),
    ]
