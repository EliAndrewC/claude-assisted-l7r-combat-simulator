"""Build progressions for the Mirumoto Bushi school."""

from __future__ import annotations

from l7r.builders import Progression
from l7r.schools.MirumotoBushi import MirumotoBushi


class MirumotoBushiProgression(Progression):
    """Standard Mirumoto Bushi progression.

    Prioritises reaching 3rd Dan quickly for the R3T shared disc bonuses,
    then builds up combat skills and rings before pushing to 4th and 5th Dan.

    Ring ordering rationale (Mirumoto perspective):
    - Void first at every tier (school ring, fuels VPs and initiative).
    - Air next (drives parry rolls — the Mirumoto's core mechanic).
    - Water before Earth at 3 (wound checks matter early).
    - Earth before Water at 4-5 (serious wound thresholds matter more
      once fights get longer and harder-hitting).
    - Fire last (attack rolled dice help, but Mirumoto leans on parry).
    """

    school_class = MirumotoBushi

    steps = [
        ("knacks", 3),                    # 3rd Dan before anything else
        ("attack", 2), ("parry", 3),      # basic combat skills
        # --- rings to 3: void already 3 (school ring) ---
        ("air", 3), ("water", 3), ("earth", 3), ("fire", 3),
        ("knacks", 4),                    # 4th Dan (triggers r4t_ring_boost: void→4)
        ("attack", 3), ("parry", 4),
        # --- rings to 4: void already 4 from R4T ---
        ("air", 4), ("earth", 4), ("water", 4), ("fire", 4),
        ("knacks", 5),                    # 5th Dan
        ("attack", 4), ("parry", 5),
        # --- rings to 5 ---
        ("void", 5), ("air", 5), ("earth", 5), ("water", 5), ("fire", 5),
    ]
