"""Build progressions for the Doji Artisan school."""

from __future__ import annotations

from l7r.builders import Progression


class DojiArtisanProgression(Progression):
    """Standard Doji Artisan progression.

    Ring ordering rationale:
    - Air first (school ring; drives parry and counterattack dice).
    - Fire next (attack rolls and damage).
    - Void (initiative, VPs — VPs are spent on counterattacks).
    - Earth (serious wound buffer).
    - Water last (wound checks; counterattacker takes some hits).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("fire", 3), ("void", 3), ("earth", 3), ("water", 3),
        ("knacks", 4),  # R4T: air 3→4
        ("attack", 3),
        ("parry", 4),
        ("fire", 4), ("void", 4), ("earth", 4), ("water", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("air", 5), ("air", 6),
        ("fire", 5), ("void", 5), ("earth", 5), ("water", 5),
    ]
