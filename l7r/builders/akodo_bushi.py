"""Build progressions for the Akodo Bushi school."""

from __future__ import annotations

from l7r.builders import Progression
from l7r.schools.AkodoBushi import AkodoBushi


class AkodoBushiProgression(Progression):
    """Standard Akodo Bushi progression.

    Akodo is feint-driven offence: feints generate VPs (special ability
    gives +4 temp VPs per successful feint), which fuel attacks and R4T
    wound-check VP spending.  hold_one_action is False — every action
    goes towards attacking.

    Ring ordering rationale:
    - Fire first (drives attack rolls and damage dice — the primary
      output once VP reserves are built up from feinting).
    - Water next (school ring; R1T/R2T both boost wound checks, and
      R3T converts wound-check excess into attack disc bonuses).
    - Void (initiative, VP ceiling, and survivability — Akodo
      generates VPs from feints but Void still sets the floor).
    - Earth (serious wound buffer; base_wc_threshold=25 means Akodo
      keeps more light wounds, so Earth matters but less than Water
      or Void).
    - Air last (hold_one_action=False, so parrying is rare; base TN
      from parry skill is enough).
    """

    school_class = AkodoBushi

    steps = [
        # --- knacks to 3 (3rd Dan) ---
        "knacks", "knacks",
        # --- attack to 2, parry to 3 ---
        "attack", "attack",
        "parry", "parry", "parry",
        # --- rings to 3 (water already 3 as school ring) ---
        "fire", "void", "earth", "air",
        # --- knacks to 4 ---
        "knacks",
        # --- attack to 3, parry to 4 ---
        "attack",
        "parry",
        # --- rings to 4 ---
        "fire", "water", "void", "earth", "air",
        # --- knacks to 5 ---
        "knacks",
        # --- attack to 4, parry to 5 ---
        "attack",
        "parry",
        # --- rings to 5 ---
        "fire", "water", "void", "earth", "air",
    ]
