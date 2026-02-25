"""Build progressions for the Brotherhood of Shinsei school."""

from __future__ import annotations

from l7r.builders import Progression


class BrotherhoodOfShinseiProgression(Progression):
    """Standard Brotherhood of Shinsei progression.

    Brotherhood is a monk martial arts school: enhanced unarmed damage
    (SA), shared disc bonuses each round (R3T), and compensates for
    failed parry damage reduction (R4T).

    Ring ordering rationale:
    - Fire first (attack rolls and damage dice — the monk is a
      fighter first, and SA's +1k1 on damage makes Fire even more
      valuable for raw damage output).
    - Earth next (survivability; monks don't wear armor, so higher
      Earth compensates with more serious wound tolerance).
    - Void (initiative and VPs; acting early and having VPs for
      attack rolls matters).
    - Air last (not primarily parry-focused; R3T disc bonuses
      provide sufficient defense via wound check boosts).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("fire", 3), ("earth", 3), ("void", 3), ("air", 3),
        ("knacks", 4),  # R4T: water 3→4
        ("attack", 3),
        ("parry", 4),
        ("fire", 4), ("earth", 4), ("void", 4), ("air", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("water", 5), ("water", 6),
        ("fire", 5), ("earth", 5), ("void", 5), ("air", 5),
    ]
