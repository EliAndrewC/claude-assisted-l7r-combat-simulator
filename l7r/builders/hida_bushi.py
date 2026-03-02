"""Build progressions for the Hida Bushi school."""

from __future__ import annotations

from l7r.builders import Progression


class HidaBushiProgression(Progression):
    """Standard Hida Bushi progression.

    Hida is a tough counterattack school: cheap interrupt counterattacks,
    reroll dice on attacks (R3T), and can absorb light wounds by taking
    voluntary serious wounds (R4T).

    Ring ordering rationale:
    - Fire first (counterattack and attack rolls use Fire + skill;
      R3T rerolls make high Fire even more effective since more dice
      means better reroll results).
    - Earth next (serious wound buffer is critical for R4T, which
      trades 2 serious wounds to zero light wounds; higher Earth
      means more room to use this ability).
    - Void (initiative and VPs; Hida wants to act to counterattack).
    - Air last (the school is offense-focused, not parry-focused;
      counterattacks substitute for parrying).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("fire", 3), ("earth", 3), ("void", 3), ("air", 3),
        ("knacks", 4),  # R4T: water 3→4
        ("water", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("fire", 4), ("earth", 4), ("void", 4), ("air", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("water", 6),
        ("fire", 5), ("earth", 5), ("void", 5), ("air", 5),
    ]
