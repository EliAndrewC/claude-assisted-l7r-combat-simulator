"""Build progressions for the Kitsuki Magistrate school."""

from __future__ import annotations

from l7r.builders import Progression
from l7r.schools.KitsukiMagistrate import KitsukiMagistrate


class KitsukiMagistrateProgression(Progression):
    """Standard Kitsuki Magistrate progression.

    Kitsuki is an investigator/debuffer that uses Water for parrying
    (unique among schools).  R3T generates shared disc bonuses for
    attack and wound-check rolls.  R5T reduces enemy rings.

    Ring ordering rationale:
    - Water first (school ring AND parry ring — Kitsuki's parry_dice
      property uses Water instead of Air, making Water the single most
      important ring for both offence-support and defence).
    - Fire next (attack rolls; R3T disc bonuses scale with attack
      skill, so landing attacks matters).
    - Void (initiative, VPs, and survivability).
    - Earth (serious wound buffer; Kitsuki is not a front-line
      fighter, so staying alive to keep debuffing is key).
    - Air last (not used for parrying due to the Water override).
    """

    school_class = KitsukiMagistrate

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
        "water", "fire", "void", "earth", "air",
        # --- knacks to 5 ---
        "knacks",
        # --- attack to 4, parry to 5 ---
        "attack",
        "parry",
        # --- rings to 5 ---
        "water", "fire", "void", "earth", "air",
    ]
