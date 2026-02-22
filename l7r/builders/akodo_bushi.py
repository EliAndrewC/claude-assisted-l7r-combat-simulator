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
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("fire", 3), ("void", 3), ("earth", 3), ("air", 3),
        ("knacks", 4),  # R4T: water 3→4
        ("attack", 3),
        ("parry", 4),
        ("fire", 4), ("void", 4), ("earth", 4), ("air", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("water", 5), ("water", 6),
        ("fire", 5), ("void", 5), ("earth", 5), ("air", 5),
    ]
