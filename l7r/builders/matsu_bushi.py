"""Build progressions for the Matsu Bushi school."""

from __future__ import annotations

from l7r.builders import Progression
from l7r.schools.MatsuBushi import MatsuBushi


class MatsuBushiProgression(Progression):
    """Standard Matsu Bushi progression.

    Matsu is an all-out berserker: always rolls 10 initiative dice
    (special ability), hold_one_action is False, and R4T makes even
    "failed" double attacks count.  R3T converts VP spending into
    wound-check disc bonuses, so spending VPs on attacks also
    improves survivability.

    Ring ordering rationale:
    - Fire first (school ring; drives attack and damage, and the
      R3T delaying effect scales with Fire vs enemy Fire).
    - Water next (wound checks; R3T VP-to-wound-check synergy means
      Water amplifies the benefit of every VP spent).
    - Void (initiative kept dice = Void; with 10 rolled dice from
      the special ability, higher Void means more actions per round;
      also helps survivability).
    - Earth (serious wound buffer; Matsu charges into the thick of
      things and needs to survive the return damage).
    - Air last (never holds actions; relies on overwhelming offence
      rather than parrying).
    """

    school_class = MatsuBushi

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
