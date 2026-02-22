from __future__ import annotations

from l7r.combatant import Combatant
from l7r.types import RollType


class MirumotoBushi(Combatant):
    """Mirumoto Bushi school (Dragon clan). A defensive two-sword school.

    Strategy: Parry-focused — gains VPs from successful parries and
    accumulates shared disc bonuses each round. Spends VPs in pairs
    (2 at a time) reflecting the two-sword style.

    Special ability: Gain 1 VP per successful parry (2 at Rank 5).
    School ring: Void.
    School knacks: counterattack, double attack, iaijutsu.

    Key techniques:
    - R1T: Extra rolled die on attack, double attack, parry.
    - R2T: Free raise (+5) on parry.
    - R3T: Each round, gain (attack) shared +2 disc bonuses.
    - R4T: The R3T bonuses become usable on attack, double attack,
      lunge, AND parry (shared pool across all four).
    - R5T: Start with double VPs and gain 2 VPs per successful parry.

    NOTE: choose_action, will_predeclare, and will_parry are stubs (pass).
    The Mirumoto's parry-centric strategy needs custom AI logic that
    hasn't been implemented yet.
    """

    school_knacks: list[RollType] = ["counterattack", "double_attack", "iaijutsu"]
    r1t_rolls: list[RollType] = ["attack", "double_attack", "parry"]
    r2t_rolls: RollType = "parry"

    school_ring: str = "void"
    r4t_ring_boost: str = "void"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        self.events["successful_parry"].append(self.sa_trigger)
        self.events["pre_round"].append(self.r3t_trigger)

        if self.rank == 5:
            self.vps *= 2

    def sa_trigger(self) -> None:
        """Special ability: gain VPs from successful parries. The core
        resource engine — parrying fuels future attacks and more parries."""
        self.vps += 2 if self.rank == 5 else 1

    def r3t_trigger(self) -> None:
        """R3T/R4T: Generate shared disc bonuses each round. At R3T, these
        are just stored. At R4T, they're registered as multi bonuses usable
        on attacks, double attacks, lunges, and parries."""
        if self.rank >= 3:
            self.points = [2] * self.attack
            if self.rank >= 4:
                for knack in ["attack", "double_attack", "lunge", "parry"]:
                    self.multi[knack].append(self.points)

    @property
    def spendable_vps(self) -> range:
        """Mirumoto spends VPs in pairs (0, 2, 4, ...) reflecting the
        two-sword style where both swords must work in concert."""
        return range(0, self.vps + 1, 2)

    def choose_action(self) -> tuple[RollType, Combatant] | None:
        pass

    def will_predeclare(self) -> bool:
        pass

    def will_parry(self) -> bool:
        pass
