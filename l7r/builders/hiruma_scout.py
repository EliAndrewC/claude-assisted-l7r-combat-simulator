"""Build progressions for the Hiruma Scout school."""

from __future__ import annotations

from l7r.builders import Progression


class HirumaScoutProgression(Progression):
    """Standard Hiruma Scout progression.

    Hiruma is an Air-based parry school: gains attack bonuses from
    parrying (R3T), acts earlier with lowered initiative (R4T), and
    debuffs enemy damage at rank 5. Adjacent allies benefit from +5 TN.

    Ring ordering rationale:
    - Fire first (drives attack and damage dice — after parrying
      triggers R3T bonuses, high Fire maximizes the resulting attacks).
    - Void next (initiative; combined with R4T's -2 to all action dice,
      higher Void means more and earlier actions for parrying).
    - Water (wound checks; scouts need to survive hits that get through
      their parry to benefit from R3T and R5T).
    - Earth last (serious wound buffer; Air and parrying are the primary
      defense, so Earth is less critical).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("fire", 3), ("void", 3), ("water", 3), ("earth", 3),
        ("knacks", 4),  # R4T: air 3→4
        ("air", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("fire", 4), ("void", 4), ("water", 4), ("earth", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("air", 6),
        ("fire", 5), ("void", 5), ("water", 5), ("earth", 5),
    ]
