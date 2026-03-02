"""Build progressions for the Ide Diplomat school."""

from __future__ import annotations

from l7r.builders import Progression


class IdeDiplomatProgression(Progression):
    """Standard Ide Diplomat progression.

    Ring ordering rationale:
    - Water first (school ring; drives wound checks).
    - Fire next (attack rolls; feints use Fire + skill).
    - Void (initiative, VPs — VPs are core to R3T negation).
    - Air (parry defense; Diplomat can debuff enemy TNs).
    - Earth last (relies on VP spending and TN reduction for survival).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("fire", 3), ("void", 3), ("air", 3), ("earth", 3),
        ("knacks", 4),  # R4T: water 3→4
        ("water", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("fire", 4), ("void", 4), ("air", 4), ("earth", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("water", 6),
        ("fire", 5), ("void", 5), ("air", 5), ("earth", 5),
    ]
