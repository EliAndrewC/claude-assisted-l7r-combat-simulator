from __future__ import annotations

from math import ceil

from l7r.combatant import Combatant
from l7r.dice import xky
from l7r.types import RollType


class HidaBushi(Combatant):
    """Hida Bushi school (Crab clan). A tough counterattack school.

    Strategy: Tank damage and counterattack aggressively. Interrupt
    counterattacks cost only 1 action die. At higher ranks, rerolls
    make attacks more consistent and R4T allows absorbing light wounds
    by taking voluntary serious wounds.

    Special ability: Interrupt counterattacks cost 1 action die instead
    of 2. Attacker gets +5 on their attack roll when we counterattack
    (tradeoff for cheap counterattacks).
    School ring: Water.
    School knacks: counterattack, iaijutsu, lunge.

    Key techniques:
    - R1T: Extra rolled die on attack, counterattack, wound check.
    - R2T: Free raise (+5) on counterattack.
    - R3T: Reroll 2*attack dice on counterattack, attack dice on other
      rolls. When crippled, halve the reroll count but still reroll 10s.
    - R4T: +1 Water (free). Instead of wound check, may take 2 serious
      wounds to zero light wounds.
    - R5T: Counterattack excess adds to damage wound check. May
      counterattack after seeing damage dealt.
    """

    school_knacks: list[RollType] = ["counterattack", "iaijutsu", "lunge"]
    r1t_rolls: list[RollType] = ["attack", "counterattack", "wound_check"]
    r2t_rolls: RollType = "counterattack"

    school_ring = "water"
    r4t_ring_boost = "water"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        if self.rank >= 5:
            self.events["successful_attack"].append(self.r5t_trigger)

    def xky(self, roll: int, keep: int, reroll: bool, roll_type: RollType) -> int:
        """R3T: Roll extra dice (reroll the lowest). On counterattack,
        reroll 2*attack dice; on other rolls, reroll attack dice.
        When crippled, halve the reroll count (round up) but reroll 10s."""
        if self.rank >= 3:
            extra = 2 * self.attack if getattr(self, "attack_knack", None) == "counterattack" else self.attack
            if self.crippled:
                extra = ceil(extra / 2)
                reroll = True
            roll += extra
        return xky(roll, keep, reroll)

    def will_counterattack(self, enemy: Combatant) -> bool:
        """SA: Counterattack using only 1 action die. The attacker gets
        +5 on their attack roll as a tradeoff."""
        if not self.counterattack or not self.actions:
            return False

        extra = self.projected_damage(enemy, True)
        base = self.projected_damage(enemy, False)
        if extra + self.serious >= self.sw_to_kill or extra - base >= self.sw_parry_threshold:
            self.actions.pop(0)
            return True
        return False

    def will_react_to_attack(self, enemy: Combatant) -> bool:
        """R5T: May counterattack after seeing the damage dealt. More
        informed than a normal counterattack (which happens before damage)."""
        if self.rank < 5 or not self.counterattack or not self.actions:
            return False
        self.actions.pop(0)
        return True

    def r5t_trigger(self) -> None:
        """R5T: When counterattacking, add the attack roll excess over
        the TN as extra damage on the wound check."""
        if self.attack_knack == "counterattack":
            excess = max(0, self.attack_roll - self.enemy.tn)
            if excess:
                self.auto_once["damage"] += excess

    def wound_check(self, light: int, serious: int = 0) -> None:
        """R4T: Instead of a normal wound check, may take 2 serious
        wounds to immediately zero out light wounds. Used when light
        wounds are dangerously high and we can afford the serious wounds."""
        if (
            self.rank >= 4
            and self.light + light > self.wc_threshold
            and self.serious + 2 < self.sw_to_kill
        ):
            self.log("R4T: takes 2 serious to zero light wounds")
            self.light = 0
            self.serious += serious + 2
            self.crippled = self.serious >= self.sw_to_cripple
            self.dead = self.serious >= self.sw_to_kill
            return

        super().wound_check(light, serious)
