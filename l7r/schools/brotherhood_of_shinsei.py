from __future__ import annotations

from l7r.combatant import Combatant
from l7r.types import RollType


class BrotherhoodOfShinsei(Combatant):
    """Brotherhood of Shinsei school. A monk martial arts school.

    Strategy: Unarmed fighter with enhanced damage dice and shared
    discretionary bonuses each round. Parry attempts don't reduce
    damage at higher ranks, and the monk can counter-attack after
    being attacked at rank 5.

    Special ability: +1k1 on unarmed damage (extra rolled and kept
    damage dice).
    School ring: Water.
    School knacks: conviction, otherworldliness, worldliness (non-combat).

    Key techniques:
    - R1T: Extra rolled die on attack, damage, wound check.
    - R2T: Free raise (+5) on attack.
    - R3T: Each round, generate 2*rank shared free raises usable on
      attack and wound check. May spend them to lower action dice by 5.
    - R4T: +1 Water (free). Failed parries against us don't reduce the
      attacker's rolled damage dice (we compensate for the reduction).
    - R5T: After being attacked, spend an action to counter-attack.
      If counter-attack matches or exceeds the attack roll, cancel it.
    """

    school_knacks: list[RollType] = ["conviction", "otherworldliness", "worldliness"]
    r1t_rolls: list[RollType] = ["attack", "damage", "wound_check"]
    r2t_rolls: RollType = "attack"

    school_ring = "water"
    r4t_ring_boost = "water"

    reserved_raises = 2
    """How many R3T free raises to keep in reserve for wound checks
    and failed attack rolls rather than spending to act earlier."""

    max_lower_cost = 1
    """Maximum R3T points to spend lowering a single action die to
    the current phase (0 = never lower, 1 = only if within 5,
    2 = if within 10)."""

    sw_lower_threshold: float = 1.0
    """Minimum expected serious wounds the attack must deal to justify
    spending R3T points to act earlier. Similar in spirit to
    sw_parry_threshold but for offensive action-lowering decisions."""

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        # SA: +1k1 on unarmed damage
        self.extra_dice["damage"][0] += 1
        self.extra_dice["damage"][1] += 1

        self.events["pre_round"].append(self.r3t_trigger)

    def r3t_trigger(self) -> None:
        """R3T: Generate 2*rank shared free raises each round, usable
        on attack and wound check rolls. Similar to Mirumoto's R3T but
        with different knack coverage and larger individual bonuses."""
        if self.rank >= 3:
            self.points = [5] * (2 * self.rank)
            for knack in ["attack", "wound_check"]:
                self.multi[knack].append(self.points)

    def choose_action(self) -> tuple[RollType, Combatant] | None:
        """R3T action-lowering: spend free raises to act earlier.

        If no action die is ready for this phase, consider spending
        R3T points (each lowers a die by 5) to bring a future action
        into the current phase. Guarded by three knobs:
        - reserved_raises: points to keep for wound checks / attacks
        - max_lower_cost: max points to spend per action lowered
        - sw_lower_threshold: min expected serious wounds to justify it
        """
        # If we have a current-phase action, use normal logic.
        if self.actions and self.actions[0] <= self.phase:
            return super().choose_action()

        if self.rank < 3 or not self.actions:
            return None

        points = getattr(self, "points", [])
        if not points:
            return None

        # How many points to lower the next action die to this phase?
        lowest_action = self.actions[0]
        cost = (lowest_action - self.phase + 4) // 5
        if cost <= 0 or cost > self.max_lower_cost:
            return None

        available = len(points) - self.reserved_raises
        if cost > available:
            return None

        # Respect hold_one_action: don't use our only action offensively.
        if self.hold_one_action and len(self.actions) < 2:
            return None

        # Estimate expected serious wounds the hit would deal to the
        # weakest target (assuming the hit lands — the threshold is
        # about damage per hit, not damage * probability).
        target = min(self.attackable, key=lambda e: e.tn)
        roll, keep = self.att_dice("attack")
        expected_light = self.expected_att_damage(
            target.tn, roll, keep, self.max_bonus("attack"),
        )
        wc_roll, wc_keep = target.wc_dice
        total_light = target.light + expected_light
        expected_sw = target.avg_serious(
            total_light, wc_roll, wc_keep,
        )[0][1]

        if expected_sw < self.sw_lower_threshold:
            return None

        # Spend points and act.
        del self.points[:cost]
        self.actions.pop(0)
        knack: RollType = "attack"

        if self.double_attack:
            tn = min(e.tn for e in self.attackable)
            datt_prob = self.att_prob("double_attack", tn + 20)
            att_prob = self.att_prob("attack", tn)
            if att_prob - datt_prob <= self.datt_threshold:
                knack = "double_attack"

        return knack, self.att_target(knack)

    def make_parry(self, auto_success: bool = False) -> bool:
        """R4T: When our parry fails, compensate for the damage dice
        reduction that normally occurs. The attacker keeps their full
        rolled damage dice as if no parry was attempted."""
        success = super().make_parry(auto_success)
        if not success and self.rank >= 4:
            excess_dice = max(0, self.enemy.attack_roll - self.tn) // 5
            self.enemy.auto_once["damage_rolled"] += excess_dice
        return success

    def will_react_to_attack(self, enemy: Combatant) -> bool:
        """R5T: After being attacked, may spend an action to
        counter-attack. If our counter-attack roll matches or exceeds
        the enemy's attack roll, the attack is cancelled."""
        if self.rank < 5 or not self.actions:
            return False
        self.actions.pop(0)
        return True

    def will_parry(self) -> bool:
        """Parry heuristic that accounts for R3T point spending.

        Similar to Mirumoto: if no current-phase action, try spending
        R3T points to lower a future action die to the current phase.
        """
        if self.predeclare_bonus:
            return True

        if not self.actions and not getattr(self, "points", []):
            return False

        has_current = self.actions and self.actions[0] <= self.phase

        if not has_current:
            if not self.actions or not getattr(self, "points", []):
                return False
            lowest_action = self.actions[0]
            cost = (lowest_action - self.phase + 4) // 5
            if cost <= 0 or cost > len(getattr(self, "points", [])):
                return False
            extra = self.projected_damage(self.enemy, True)
            base = self.projected_damage(self.enemy, False)
            if extra + self.serious >= self.sw_to_kill or extra - base >= self.sw_parry_threshold:
                del self.points[:cost]
                self.actions.pop(0)
                return True
            return False

        extra = self.projected_damage(self.enemy, True)
        base = self.projected_damage(self.enemy, False)
        parry = extra + self.serious >= self.sw_to_kill or extra - base >= self.sw_parry_threshold
        if parry:
            self.actions.pop(0)
        return parry
