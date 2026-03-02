"""Build progressions for the Isawa Ishi school."""

from __future__ import annotations

from l7r.builders import Progression


class IsawaIshiProgression(Progression):
    """Standard Isawa Ishi progression.

    Isawa Ishi is a Void-based support school: large VP pool (highest
    ring + rank), prevents enemies from spending VPs (R4T), and can
    negate enemy school abilities entirely (R5T).

    Ring ordering rationale:
    - Fire first (attack rolls and damage dice — despite being
      a support school, the Isawa Ishi still needs to deal damage
      in 1v1 combat where R3T support is unavailable).
    - Water next (wound checks; with a limited VP-per-roll cap from
      the SA, Water-based survivability is important).
    - Earth (serious wound buffer; R4T's VP denial makes enemies
      less effective, but the Isawa still needs to survive hits).
    - Air last (VPs are spent on attacks more than parries; the
      large VP pool makes offense the priority).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("fire", 3), ("water", 3), ("earth", 3), ("air", 3),
        ("knacks", 4),  # R4T: void 3→4
        ("void", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("fire", 4), ("water", 4), ("earth", 4), ("air", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("void", 6),
        ("fire", 5), ("water", 5), ("earth", 5), ("air", 5),
    ]
