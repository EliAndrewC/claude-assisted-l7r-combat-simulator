"""Build progressions for the Shinjo Bushi school."""

from __future__ import annotations

from l7r.builders import Progression


class ShinjoBushiProgression(Progression):
    """Standard Shinjo Bushi progression.

    Shinjo is a patient defensive school that always pre-declares
    parries (built-in +5 bonus) and gains speed from successful
    parries (R3T moves all action dice earlier).  R4T guarantees a
    phase-1 action, and R5T converts parry excess into wound-check
    disc bonuses.

    Ring ordering rationale:
    - Air first (school ring; also drives parry rolls, the core
      mechanic — every successful parry accelerates the action
      schedule via R3T).
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
