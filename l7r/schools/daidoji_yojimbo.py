from __future__ import annotations

from copy import deepcopy

from l7r.combatant import Combatant
from l7r.dice import avg
from l7r.types import RollType


class DaidojiYojimbo(Combatant):
    """Daidoji Yojimbo school (Crane clan). A bodyguard counterattack school.

    Strategy: Protect allies via counterattacks and absorb damage for
    adjacent teammates. Counterattacks cost only 1 action die (instead
    of the normal 2 for interrupts), making them much more affordable.

    Special ability: Interrupt counterattacks cost 1 action die instead
    of 2. Enemy gets +5 on wound check when we counterattack. May
    counterattack for others at no penalty.
    School ring: Water.
    School knacks: counterattack, double attack, iaijutsu.

    Key techniques:
    - R1T: Extra rolled die on attack, counterattack, wound check.
    - R2T: Free raise (+5) on counterattack.
    - R3T: When counterattacking successfully, add 5 * attack as extra
      damage (makes counterattack wound checks much harder for the enemy).
    - R4T: +1 Water (free). May take damage for adjacent allies.
    - R5T: After successful wound check, lower attacker's TN by the
      amount the check exceeded the light wound total.
    """

    school_knacks: list[RollType] = ["counterattack", "double_attack", "iaijutsu"]
    r1t_rolls: list[RollType] = ["attack", "counterattack", "wound_check"]
    r2t_rolls: RollType = "counterattack"

    school_ring = "water"
    r4t_ring_boost = "water"

    self_counterattack_sw_threshold: float = 1.0
    """Minimum serious wounds our R3T wound check bonus would prevent
    to justify spending an action die to counterattack for ourselves."""

    ally_counterattack_sw_threshold: float = 0.75
    """Minimum serious wounds our R3T wound check bonus would prevent
    to justify counterattacking on an ally's behalf. Lower than the
    self threshold because a yojimbo will sacrifice themselves for
    their protectee."""

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        self.events["successful_attack"].append(self.r3t_trigger)

        if self.rank >= 5:
            self.events["wound_check"].append(self.r5t_trigger)

    def r3t_trigger(self) -> None:
        """R3T: Successful counterattacks add 5 * attack as extra damage,
        making the enemy's wound check dramatically harder."""
        if self.rank >= 3 and self.attack_knack == "counterattack":
            self.auto_once["damage"] += 5 * self.attack

    def r5t_trigger(self, check: int, light: int, light_total: int) -> None:
        """R5T: After successful wound check, lower attacker's TN by
        the excess (check - light_total). Punishes enemies for failing
        to finish us off."""
        excess = max(0, check - light_total)
        if excess and hasattr(self, "enemy") and self.enemy:
            enemy = self.enemy
            enemy.tn -= excess

            def restore() -> bool:
                enemy.tn += excess
                return True

            enemy.events["post_defense"].append(restore)

    def _counterattack_sw_saved(self, target: Combatant, enemy: Combatant) -> float:
        """Estimate how many serious wounds our R3T wound check bonus
        would prevent for the target.

        Computes the enemy's expected damage, then compares the
        target's expected serious wounds with and without the R3T
        bonus (5 * attack) applied to the wound check.
        """
        droll, dkeep, serious = deepcopy(enemy).next_damage(target.tn, True)
        light = avg(True, droll, dkeep)
        wc_roll, wc_keep = target.wc_dice

        sw_without = serious + target.avg_serious(light, wc_roll, wc_keep)[0][1]

        bonus = 5 * self.attack if self.rank >= 3 else 0
        sw_with = serious + target.avg_serious(max(0, light - bonus), wc_roll, wc_keep)[0][1]

        return sw_without - sw_with

    def will_counterattack(self, enemy: Combatant) -> bool:
        """SA: Counterattack using only 1 action die (instead of 2).

        Counterattacks if the serious wounds our R3T wound check bonus
        would prevent exceeds self_counterattack_sw_threshold.
        """
        if not self.counterattack or not self.actions:
            return False

        sw_saved = self._counterattack_sw_saved(self, enemy)
        if sw_saved >= self.self_counterattack_sw_threshold:
            self.actions.pop(0)
            return True
        return False

    def will_counterattack_for(self, ally: Combatant, enemy: Combatant) -> bool:
        """SA: May counterattack for adjacent allies at no penalty.

        Counterattacks if the serious wounds our R3T wound check bonus
        would prevent for the ally exceeds ally_counterattack_sw_threshold.
        Lower threshold than self because a yojimbo will sacrifice
        themselves for their protectee.
        """
        if not self.counterattack or not self.actions:
            return False

        sw_saved = self._counterattack_sw_saved(ally, enemy)
        if sw_saved >= self.ally_counterattack_sw_threshold:
            self.actions.pop(0)
            return True
        return False
