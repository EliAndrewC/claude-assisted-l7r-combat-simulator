"""Build progressions for the Kuni Witch Hunter school."""

from __future__ import annotations

from l7r.builders import Progression


class KuniWitchHunterProgression(Progression):
    """Standard Kuni Witch Hunter progression.

    Ring ordering rationale:
    - Earth first (school ring; drives wound checks and serious wound
      tolerance, which is core to the tanky playstyle).
    - Fire next (attack rolls; damage also benefits from Fire).
    - Void (initiative, VPs, survivability).
    - Water (wound checks get extra dice from SA already).
    - Air last (not a parry-focused school).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("fire", 3), ("void", 3), ("water", 3), ("air", 3),
        ("knacks", 4),  # R4T: earth 3→4
        ("earth", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("fire", 4), ("void", 4), ("water", 4), ("air", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("earth", 6),
        ("fire", 5), ("void", 5), ("water", 5), ("air", 5),
    ]
