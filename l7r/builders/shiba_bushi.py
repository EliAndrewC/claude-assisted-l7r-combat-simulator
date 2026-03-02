"""Build progressions for the Shiba Bushi school."""

from __future__ import annotations

from l7r.builders import Progression


class ShibaBushiProgression(Progression):
    """Standard Shiba Bushi progression.

    Shiba is a protective bodyguard school: parries for self and allies
    at reduced cost (1 action interrupt instead of 2), and parries for
    others with no penalty.  R3T turns every parry attempt into damage,
    and R5T debuffs the enemy's TN after a successful parry.

    Ring ordering rationale:
    - Air first (school ring; drives parry rolls and TN — the core
      mechanic.  Higher Air means better parries, which means more
      R3T damage and R5T debuffs).
    - Water next (wound checks; R1T and R4T both boost wound checks,
      and staying alive to keep parrying is critical).
    - Void (initiative and VPs; helps act early and sustain parrying
      through VP spending).
    - Fire (attack rolls and damage; secondary since most damage
      comes from R3T parry damage rather than direct attacks).
    - Earth last (wound buffer; Air and Water provide more defensive
      value for this school).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("water", 3), ("void", 3), ("fire", 3), ("earth", 3),
        ("knacks", 4),  # R4T: air 3→4
        ("air", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("water", 4), ("void", 4), ("fire", 4), ("earth", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("air", 6),
        ("water", 5), ("void", 5), ("fire", 5), ("earth", 5),
    ]
