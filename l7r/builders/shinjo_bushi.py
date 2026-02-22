"""Build progressions for the Shinjo Bushi school."""

from __future__ import annotations

from l7r.builders import Progression
from l7r.schools.ShinjoBushi import ShinjoBushi


class ShinjoBushiProgression(Progression):
    """Standard Shinjo Bushi progression.

    Shinjo is a patient defensive school that always pre-declares
    parries (built-in +5 bonus) and gains speed from successful
    parries (R3T moves all action dice earlier).  R4T guarantees a
    phase-1 action, and R5T converts parry excess into wound-check
    disc bonuses.

    Ring ordering rationale:
    - Air first (school ring AND parry ring — drives parry rolls,
      the core mechanic; every successful parry accelerates the
      action schedule via R3T).
    - Water next (wound checks; R5T converts parry excess into
      wound-check bonuses, so Water amplifies that defensive
      synergy).
    - Void (initiative and VPs; less critical once R4T guarantees
      a phase-1 action, but still helps survivability).
    - Fire (attack rolls; Shinjo eventually needs to strike, and
      Fire determines damage dice).
    - Earth last (parry schools get more mileage from Air and
      Water than from pushing Earth).
    """

    school_class = ShinjoBushi

    steps = [
        # --- knacks to 3 (3rd Dan) ---
        "knacks", "knacks",
        # --- attack to 2, parry to 3 ---
        "attack", "attack",
        "parry", "parry", "parry",
        # --- rings to 3 (air already 3 as school ring) ---
        "water", "void", "fire", "earth",
        # --- knacks to 4 ---
        "knacks",
        # --- attack to 3, parry to 4 ---
        "attack",
        "parry",
        # --- rings to 4 ---
        "air", "water", "void", "fire", "earth",
        # --- knacks to 5 (5th Dan) ---
        "knacks",
        # --- attack to 4, parry to 5 ---
        "attack",
        "parry",
        # --- rings to 5 ---
        "air", "water", "void", "fire", "earth",
    ]
