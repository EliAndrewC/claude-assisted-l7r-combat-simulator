"""Build progressions for the Otaku Bushi school."""

from __future__ import annotations

from l7r.builders import Progression


class OtakuBushiProgression(Progression):
    """Standard Otaku Bushi progression.

    Otaku is an aggressive mounted school that counterattacks after
    being attacked (special ability spends an action to lunge the
    attacker).  hold_one_action is False — all actions go to offence,
    with the SA providing reactive defence.

    Ring ordering rationale:
    - Water first (wound checks are survival-critical; R1T boosts
      wound checks with an extra rolled die, and staying alive is
      essential to trigger SA counterattacks).
    - Void next (initiative and VP ceiling; helps act early to set
      up the counterattack cycle).
    - Earth (wound buffer; Otaku takes hits to trigger SA counter-
      attacks, so a large serious wound pool keeps the school in
      the fight longer).
    - Air last (hold_one_action=False, so the school does not parry
      proactively; base TN from parry skill suffices).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("water", 3), ("void", 3), ("earth", 3), ("air", 3),
        ("knacks", 4),  # R4T: fire 3→4
        ("fire", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("water", 4), ("void", 4), ("earth", 4), ("air", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("fire", 6),
        ("water", 5), ("void", 5), ("earth", 5), ("air", 5),
    ]
