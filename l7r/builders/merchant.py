"""Build progressions for the Merchant school."""

from __future__ import annotations

from l7r.builders import Progression


class MerchantProgression(Progression):
    """Standard Merchant progression.

    Ring ordering rationale:
    - Water first (school ring; drives wound checks which is the
      primary survival mechanic for this school).
    - Fire next (attack rolls).
    - Void (initiative, VPs, survivability).
    - Earth (serious wound buffer).
    - Air last (not parry-focused).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("fire", 3), ("void", 3), ("earth", 3), ("air", 3),
        ("knacks", 4),  # R4T: water 3→4
        ("attack", 3),
        ("parry", 4),
        ("fire", 4), ("void", 4), ("earth", 4), ("air", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("water", 5), ("water", 6),
        ("fire", 5), ("void", 5), ("earth", 5), ("air", 5),
    ]
