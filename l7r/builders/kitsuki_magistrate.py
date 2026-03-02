"""Build progressions for the Kitsuki Magistrate school."""

from __future__ import annotations

from l7r.builders import Progression


class KitsukiMagistrateProgression(Progression):
    """Standard Kitsuki Magistrate progression.

    Kitsuki is an investigator/debuffer.  R3T generates shared disc
    bonuses for attack and wound-check rolls.  R5T reduces enemy rings.

    Ring ordering rationale:
    - Water first (school ring; also drives wound checks, which R1T
      boosts with an extra rolled die).
    - Fire next (attack rolls; R3T disc bonuses scale with attack
      skill, so landing attacks matters).
    - Void (initiative, VPs, and survivability).
    - Earth (serious wound buffer; Kitsuki is not a front-line
      fighter, so staying alive to keep debuffing is key).
    - Air last (Kitsuki relies on debuffs and wound checks rather
      than parry defence).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("fire", 3), ("void", 3), ("earth", 3), ("air", 3),
        ("knacks", 4),  # R4T: water 3→4
        ("water", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("fire", 4), ("void", 4), ("earth", 4), ("air", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("water", 6),
        ("fire", 5), ("void", 5), ("earth", 5), ("air", 5),
    ]
