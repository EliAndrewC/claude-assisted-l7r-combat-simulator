"""Build progressions for the Mirumoto Bushi school."""

from __future__ import annotations

from l7r.builders import Progression


class MirumotoBushiProgression(Progression):
    """Standard Mirumoto Bushi progression.

    Prioritises reaching 3rd Dan quickly for the R3T shared disc bonuses,
    then builds up combat skills and rings before pushing to 4th and 5th Dan.

    Ring ordering rationale (Mirumoto perspective):
    - Air first (drives parry rolls — the Mirumoto's core mechanic;
      successful parries generate VPs via the special ability).
    - Water next (wound checks and skills; staying alive to keep
      parrying is the whole strategy).
    - Void (school ring, fuels VPs and initiative; starts at 3 and
      gets a free boost to 4 at R4T, so explicit raises come late).
    - Fire (attack dice; Mirumoto leans on parry, so Fire is less
      urgent than for offensive schools).
    - Earth last (parry schools get more from Air and Water than
      from pushing Earth).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("air", 3), ("water", 3), ("fire", 3), ("earth", 3),
        ("knacks", 4),  # R4T: void 3→4
        ("void", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("air", 4), ("water", 4), ("fire", 4), ("earth", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("void", 6),
        ("air", 5), ("water", 5), ("fire", 5), ("earth", 5),
    ]
