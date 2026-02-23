"""Build progressions for the Bayushi Bushi school."""

from __future__ import annotations

from l7r.builders import Progression


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
