"""Build progressions for the Isawa Duelist school."""

from __future__ import annotations

from l7r.builders import Progression


class IsawaDuelistProgression(Progression):
    """Standard Isawa Duelist progression.

    Isawa Duelist is a Water-based damage dealer who swaps Fire for Water
    on damage dice.  Opens with a lunge, then looks for further lunge and
    double-attack opportunities.  hold_one_action is True (default), so
    the school parries reactively.

    Ring ordering rationale:
    - Air first (hold_one_action=True means this school parries; Air
      drives parry TN, the primary defensive stat).
    - Void next (initiative and VP ceiling; VPs fuel disc bonuses and
      the school generates them through combat tempo).
    - Fire (general attack stat; less critical than usual because
      damage_dice swaps Fire for Water, but still affects attack rolls).
    - Earth last (wound buffer; lowest priority since Air and Water
      provide more defensive value for this school).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("air", 3), ("void", 3), ("fire", 3), ("earth", 3),
        ("knacks", 4),  # R4T: water 3→4
        ("water", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("air", 4), ("void", 4), ("fire", 4), ("earth", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("water", 6),
        ("air", 5), ("void", 5), ("fire", 5), ("earth", 5),
    ]
