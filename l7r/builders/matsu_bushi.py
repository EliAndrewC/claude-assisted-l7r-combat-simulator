"""Build progressions for the Matsu Bushi school."""

from __future__ import annotations

from l7r.builders import Progression


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

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("water", 3), ("void", 3), ("earth", 3), ("air", 3),
        ("knacks", 4),  # R4T: fire 3→4
        ("attack", 3),
        ("parry", 4),
        ("water", 4), ("void", 4), ("earth", 4), ("air", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("fire", 5), ("fire", 6),
        ("water", 5), ("void", 5), ("earth", 5), ("air", 5),
    ]
