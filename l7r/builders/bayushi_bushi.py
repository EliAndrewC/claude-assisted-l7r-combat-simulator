"""Build progressions for the Bayushi Bushi school."""

from __future__ import annotations

from l7r.builders import Progression
from l7r.schools.BayushiBushi import BayushiBushi


class BayushiBushiProgression(Progression):
    """Standard Bayushi Bushi progression.

    Bayushi is hyper-aggressive VP-efficient offence: each VP spent on
    attack/feint/double-attack adds +1 rolled AND +1 kept damage die.
    hold_one_action is False and datt_threshold is high (0.3), so
    double attacks are favoured heavily.

    Ring ordering rationale:
    - Fire first (school ring; drives both attack rolls AND damage —
      double benefit for the most important stat).
    - Water next (wound checks; Bayushi takes hits to deal hits, and
      base_wc_threshold=25 means light wounds accumulate).
    - Void (VPs convert directly to damage via special ability, so
      a higher VP ceiling is valuable; also helps survivability).
    - Earth (serious wound buffer; with aggressive play, Earth keeps
      Bayushi alive long enough for VP-fuelled damage to win).
    - Air last (never holds actions, rarely parries; base TN from
      parry skill suffices).
    """

    school_class = BayushiBushi

    steps = [
        # --- knacks to 3 (3rd Dan) ---
        "knacks", "knacks",
        # --- attack to 2, parry to 3 ---
        "attack", "attack",
        "parry", "parry", "parry",
        # --- rings to 3 (fire already 3 as school ring) ---
        "water", "void", "earth", "air",
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
