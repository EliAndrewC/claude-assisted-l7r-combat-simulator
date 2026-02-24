from __future__ import annotations

from l7r.combatant import Combatant
from l7r.types import RollType


class KuniWitchHunter(Combatant):
    """Kuni Witch Hunter school (Crab clan). Damage dealer.

    Strategy: Tanky Earth-based fighter. Gains extra dice on wound checks,
    free raises on attack and wound check, and at high rank reflects light
    wounds back to the attacker.

    Special ability: +1k1 on wound checks (since there are no tainted
    targets in the simulation, the taint detection bonus becomes wound
    check defense).
    School ring: Earth.
    School knacks: detect taint, iaijutsu, presence.

    Key techniques:
    - R1T: Extra rolled die on damage, interrogation, wound check.
    - R2T: Free raise (+5) on interrogation.
    - R3T: 10 shared free raises on attack + wound check.
    - R4T: +1 Earth (free). Extra action die (parry-only since no tainted
      targets). Override initiative to roll +1 die, hold one action.
    - R5T: After wound check, may reflect light wounds to attacker
      (attacker gets wound_check(light)) but Kuni also takes half
      that amount as a wound check themselves.
    """

    school_knacks: list[RollType] = ["detect_taint", "iaijutsu", "presence"]
    r1t_rolls: list[RollType] = ["damage", "interrogation", "wound_check"]
    r2t_rolls: RollType = "interrogation"
    school_ring = "earth"
    r4t_ring_boost = "earth"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        # SA: +1k1 on wound checks (no tainted targets → wound check bonus)
        self.extra_dice["wound_check"][0] += 1
        self.extra_dice["wound_check"][1] += 1

        if self.rank >= 3:
            raises = [5] * 10
            for roll_type in ["attack", "wound_check"]:
                self.multi[roll_type].append(raises)

        if self.rank >= 4:
            self.hold_one_action = True

        if self.rank >= 5:
            self.events["wound_check"].append(self.r5t_trigger)

    @property
    def init_dice(self) -> tuple[int, int]:
        """R4T: Roll one extra initiative die."""
        roll, keep = super().init_dice
        if self.rank >= 4:
            roll += 1
        return roll, keep

    def r5t_trigger(self, check: int, light: int, total: int) -> None:
        """R5T: After wound check, may reflect light wounds to attacker.

        The attacker takes a wound check against the full light wound
        amount, but the Kuni also takes half that amount as a wound
        check themselves. Only used when the light wounds are
        significant enough to be worth the self-damage and the Kuni
        isn't about to die.
        """
        if (
            light > 0
            and hasattr(self, 'enemy')
            and self.enemy
            and not self.enemy.dead
            and self.serious + 1 < self.sw_to_kill
        ):
            self_damage = light // 2
            self.enemy.wound_check(light)
            if self_damage > 0:
                self.wound_check(self_damage)
