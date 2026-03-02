"""Build progressions for the Daidoji Yojimbo school."""

from __future__ import annotations

from l7r.builders import Progression


class DaidojiYojimboProgression(Progression):
    """Standard Daidoji Yojimbo progression.

    Daidoji is a bodyguard counterattack school: cheap interrupt
    counterattacks (1 action die), enhanced counterattack damage (R3T),
    and the ability to protect allies (R4T).

    Ring ordering rationale:
    - Air first (drives TN and parry rolls — as a bodyguard, staying
      alive and being hard to hit is critical for protecting allies).
    - Fire next (counterattack and attack rolls use Fire + skill;
      higher Fire means more effective counterattacks).
    - Void (initiative and VP pool; acting early and having VPs to
      spend on counterattack rolls matters).
    - Earth (serious wound buffer; bodyguards need to survive hits
      taken on behalf of allies).
    """

    steps = [
        ("knacks", 2), ("knacks", 3),
        ("attack", 2),
        ("parry", 2), ("parry", 3),
        ("air", 3), ("fire", 3), ("void", 3), ("earth", 3),
        ("knacks", 4),  # R4T: water 3→4
        ("water", 5),    # school ring, discounted after R4T
        ("attack", 3),
        ("parry", 4),
        ("air", 4), ("fire", 4), ("void", 4), ("earth", 4),
        ("knacks", 5),
        ("attack", 4),
        ("parry", 5),
        ("water", 6),
        ("air", 5), ("fire", 5), ("void", 5), ("earth", 5),
    ]
