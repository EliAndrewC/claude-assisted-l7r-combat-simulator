from __future__ import annotations

from l7r.combatant import Combatant
from l7r.types import RollType


class Courtier(Combatant):
    """Courtier school (Crane clan). An Air-scaling attacker with per-target VP.

    Strategy: Uses Air for both offense and defense. Special ability adds
    Air to attack and damage rolls as flat bonuses. At high ranks, tracks
    unique targets for VP generation.

    Special ability: Add Air to all attack rolls and damage rolls.
    School ring: Air.
    School knacks: discern honor, oppose social, worldliness.

    Key techniques:
    - R1T: Extra rolled die on wound check. (Tact/manipulation are
      non-combat and fixed at 5.)
    - R2T: Free raise on manipulation (non-combat; set for completeness
      as oppose_social, the closest combat-relevant knack).
    - R3T: 10 shared free raises on attack + wound check.
    - R4T: +1 Air (free). Track targets; first successful attack on each
      new target grants 1 VP.
    - R5T: Add Air to attack (stacks with SA), parry, and wound check.
    """

    school_knacks: list[RollType] = ["discern_honor", "oppose_social", "worldliness"]
    r1t_rolls: list[RollType] = ["wound_check"]
    r2t_rolls: RollType = "oppose_social"
    school_ring = "air"
    r4t_ring_boost = "air"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        # SA: +Air to attack and damage
        self.always["attack"] += self.air
        self.always["damage"] += self.air

        if self.rank >= 3:
            raises = [5] * 10
            for roll_type in ["attack", "wound_check"]:
                self.multi[roll_type].append(raises)

        if self.rank >= 4:
            self.r4t_targets: set[Combatant] = set()
            self.events["successful_attack"].append(self.r4t_trigger)

        if self.rank >= 5:
            self.always["attack"] += self.air
            self.always["parry"] += self.air
            self.always["wound_check"] += self.air

    def r4t_trigger(self) -> None:
        """R4T: On successful attack, if enemy not yet targeted, gain 1 VP."""
        if self.enemy not in self.r4t_targets:
            self.r4t_targets.add(self.enemy)
            self.vps += 1
