"""Build progressions for the Mirumoto Bushi school."""

from __future__ import annotations

from l7r.builders import Progression
from l7r.schools.MirumotoBushi import MirumotoBushi


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

    school_class = MirumotoBushi

    steps = [
        # --- knacks to 3 (3rd Dan) ---
        "knacks", "knacks",
        # --- attack to 2, parry to 3 ---
        "attack", "attack",
        "parry", "parry", "parry",
        # --- rings to 3 (void already 3 as school ring) ---
        "air", "water", "fire", "earth",
        # --- knacks to 4 (4th Dan, R4T: void 3→4) ---
        "knacks",
        # --- attack to 3, parry to 4 ---
        "attack",
        "parry",
        # --- rings to 4 (void already 4 from R4T) ---
        "air", "water", "fire", "earth",
        # --- knacks to 5 (5th Dan) ---
        "knacks",
        # --- attack to 4, parry to 5 ---
        "attack",
        "parry",
        # --- rings to 5 ---
        "void", "air", "water", "fire", "earth",
    ]
