from __future__ import annotations

from l7r.combatant import Combatant
from l7r.records import WoundCheckRecord
from l7r.types import RollType


class YogoWarden(Combatant):
    """Yogo Warden school (Scorpion clan). An Earth-based defensive school.

    Strategy: Tanky wound-absorption fighter that gains VPs from taking
    serious wounds, heals light wounds when spending VPs, and gets extra
    wound check bonuses from VP spending at higher ranks.

    Special ability: Gain 1 temporary VP each time you take a serious wound.
    School ring: Earth.
    School knacks: double attack, feint, iaijutsu.

    Key techniques:
    - R1T: Extra rolled die on attack, damage, wound check.
    - R2T: Free raise (+5) on wound checks.
    - R3T: When VPs are spent, decrease light wounds by 2 * attack.
    - R4T: +1 Earth (free). Extra +5 per VP spent on wound checks.
    - R5T: TBD — not yet implemented.
    """

    school_knacks: list[RollType] = ["double_attack", "feint", "iaijutsu"]
    r1t_rolls: list[RollType] = ["attack", "damage", "wound_check"]
    r2t_rolls: RollType = "wound_check"

    school_ring = "earth"
    r4t_ring_boost = "earth"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        if self.rank >= 3:
            self.events["vps_spent"].append(self.r3t_trigger)
        if self.rank >= 4:
            self.events["vps_spent"].append(self.r4t_trigger)

    def wound_check(self, light: int, serious: int = 0, **kwargs) -> WoundCheckRecord:
        """SA: After wound check completes, gain 1 VP if serious wounds
        increased. This fuels the VP economy — tanking hits generates
        resources for future rolls."""
        prev_serious = self.serious
        rec = super().wound_check(light, serious, **kwargs)
        if self.serious > prev_serious:
            self.vps += 1
        return rec

    def r3t_trigger(self, vps: int, knack: RollType) -> None:
        """R3T: When VPs are spent on any roll, decrease current light
        wounds by 2 * attack. Makes VP spending doubly efficient —
        the roll gets better AND light wounds are reduced."""
        self.light = max(0, self.light - 2 * self.attack)

    def r4t_trigger(self, vps: int, knack: RollType) -> None:
        """R4T: Each VP spent on wound checks gives an extra +5 bonus.
        Stacks with the R2T free raise for massive wound check resilience."""
        if knack == "wound_check":
            self.auto_once["wound_check"] += 5 * vps
