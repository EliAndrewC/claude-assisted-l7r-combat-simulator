from __future__ import annotations

from l7r.combatant import Combatant
from l7r.types import RollType


class IsawaDuelist(Combatant):
    """Isawa Duelist school (Phoenix clan). A Water-based damage dealer.

    Strategy: Open with a lunge on the first action, then look for further
    lunge opportunities. Uses Water instead of Fire for damage dice, which
    synergizes with the Phoenix's typically high Water ring.

    School ring: Water.
    School knacks: double attack, iaijutsu, lunge.

    Key techniques:
    - R1T: Extra rolled die on double attack, lunge, wound check.
    - R2T: Free raise (+5) on wound checks.
    - R3T: Can lower own TN by 5 to gain +3*attack bonus on attack rolls.
    - R4T: Interrupt lunge (once per round, costs 1 action die).
    - R5T: Convert wound check excess into disc bonuses for future checks.

    Damage dice use Water ring instead of Fire, making this school uniquely
    effective for characters who invest heavily in Water.
    """

    school_knacks: list[RollType] = ["double_attack", "iaijutsu", "lunge"]
    r1t_rolls: list[RollType] = ["double_attack", "lunge", "wound_check"]
    r2t_rolls: RollType = "wound_check"
    school_ring = "water"
    r4t_ring_boost = "water"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        self.events["wound_check"].append(self.r5t_trigger)
        self.events["pre_round"].append(self._reset_r4t_lunge)
        self._r4t_lunged = False

    def _reset_r4t_lunge(self) -> None:
        """Reset the once-per-round R4T interrupt lunge flag."""
        self._r4t_lunged = False

    def r5t_trigger(self, check: int, light: int, light_total: int) -> None:
        """R5T: Convert wound check excess into discretionary +1 bonuses
        for future wound checks. The better you shrug off damage, the
        more resilient you become."""
        exceeded = max(0, check - light_total)
        if exceeded and self.rank == 5:
            self.disc["wound_check"].extend([1] * exceeded)

    @property
    def damage_dice(self) -> tuple[int, int]:
        """Use Water ring instead of Fire for damage rolled dice. Swaps
        Fire out of the base calculation and substitutes Water."""
        roll, keep = super(IsawaDuelist, self).damage_dice
        return roll - self.fire + self.water, keep

    def max_bonus(self, roll_type: RollType) -> int:
        bonus = Combatant.max_bonus(self, roll_type)
        if (self.rank >= 3
                and roll_type in ["attack", "double_attack", "lunge"]):
            bonus += 3 * self.attack
        return bonus

    def disc_bonus(self, roll_type: RollType, needed: int) -> int:
        """R3T: If normal disc bonuses aren't enough but adding 3*attack
        would reach the target, lower own TN by 5 (making us easier to
        hit) in exchange for the attack bonus. A risky tradeoff.

        If the enemy parries, the TN penalty is negated immediately.
        Otherwise it persists until the next defense."""
        bonus = Combatant.disc_bonus(self, roll_type, needed)
        if (
            self.rank >= 3
            and bonus < needed
            and bonus + 3 * self.attack >= needed
            and roll_type in ["attack", "double_attack", "lunge"]
        ):
            self.tn -= 5
            self.events["post_attack"].append(self._r3t_post_attack)
            bonus += 3 * self.attack
        return bonus

    def _r3t_post_attack(self) -> bool:
        """After attack, check if enemy parried. If so, negate the
        R3T TN penalty. Otherwise keep it until next defense."""
        if self.was_parried:
            self.reset_tn()
        else:
            self.events["post_defense"].append(self.reset_tn)
        return True  # one-shot handler

    def choose_action(self) -> tuple[RollType, Combatant] | None:
        """Isawa Duelist action logic:
        - Out of turn: R4T interrupt lunge if threat is high (costs 1 action)
        - First action of the round: always lunge
        - Later actions: double attack if viable, otherwise lunge
        """
        if not self.actions or self.actions[0] > self.phase:
            # R4T: interrupt lunge (1 action die, once per round)
            if (self.rank >= 4 and not self._r4t_lunged
                    and self.actions):
                target = max(
                    self.attackable,
                    key=lambda e: self.projected_damage(e, True))
                if self.projected_damage(target, True) >= 2:
                    self._r4t_lunged = True
                    self.actions.pop()
                    return "lunge", target
            return None

        # Respect hold_one_action (base default is True)
        if not (
            self.phase == 10
            or not self.hold_one_action
            or len(self.actions) >= 2
            and self.actions[1] <= self.phase
        ):
            return None

        first_action = self.actions == self.init_order
        self.actions.pop(0)

        # First action of the round: always lunge
        if first_action:
            return "lunge", self.att_target("lunge")

        # Prefer double attack when probability is high enough
        if self.double_attack:
            tn = min(e.tn for e in self.attackable)
            datt_prob = self.att_prob("double_attack", tn + 20)
            lunge_prob = self.att_prob("lunge", tn)
            if (lunge_prob - datt_prob <= self.datt_threshold
                    and datt_prob >= self.vp_fail_threshold):
                return "double_attack", self.att_target("double_attack")

        # Default: lunge (Isawa's preferred knack)
        return "lunge", self.att_target("lunge")
