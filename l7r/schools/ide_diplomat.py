from __future__ import annotations

from l7r.combatant import Combatant
from l7r.dice import avg, xky
from l7r.types import RollType


class IdeDiplomat(Combatant):
    """Ide Diplomat school (Unicorn clan). Roll negation specialist.

    Strategy: Water-based support fighter. Uses feints to lower enemy
    TN, spends VPs to subtract from enemy attack rolls or add to own
    wound checks. At high rank, generates temporary VPs from VP
    spending.

    Special ability: After successful feint (met TN), lower target's
    TN by 10 for the next attack against them.
    School ring: Water.
    School knacks: double attack, feint, worldliness.

    Key techniques:
    - R1T: Extra rolled die on attack, wound check.
    - R2T: Free raise (+5) on attack.
    - R3T: Spend 1 VP to subtract 5k1 from enemy attack roll
      (pre_defense), OR spend 1 VP to add 5k1 to own wound check
      (wound_check event). Each VP buys one or the other, not both.
    - R4T: +1 Water (free). Extra VP recovery (non-combat, skipped).
    - R5T: Whenever spending a VP (not from R5T), gain 1 temp VP.
      Persists through the combat (no per-round reset).
    """

    school_knacks: list[RollType] = ["double_attack", "feint", "worldliness"]
    r1t_rolls: list[RollType] = ["attack", "wound_check"]
    r2t_rolls: RollType = "attack"
    school_ring = "water"
    r4t_ring_boost = "water"

    # --- R3T decision thresholds ---

    r3t_attack_sw_threshold: float = 0.6
    """Minimum expected serious wound reduction from depleting an enemy
    attack roll by 5k1 that justifies spending a VP. The reduction is
    estimated by comparing projected damage before vs after the
    average 5k1 roll (~8.5) is subtracted from the attack."""

    r3t_wc_sw_threshold: float = 0.6
    """Minimum expected serious wound reduction from boosting our own
    wound check by 5k1 that justifies spending a VP on it."""

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        self.events["successful_attack"].append(self.sa_trigger)

        if self.rank >= 3:
            self.events["pre_defense"].append(self.r3t_deplete_attack)
            self.events["wound_check"].append(self.r3t_boost_wc)

        if self.rank >= 5:
            self.r5t_vps = 0
            self.events["vps_spent"].append(self.r5t_trigger)

    def sa_trigger(self) -> None:
        """SA: After successful feint, lower target's TN by 10."""
        if self.attack_knack == "feint" and hasattr(self, 'enemy') and self.enemy:
            enemy = self.enemy
            enemy.tn -= 10

            def restore() -> bool:
                enemy.tn += 10
                return True

            enemy.events["post_defense"].append(restore)

    def _estimate_serious(self, attack_roll: int) -> float:
        """Estimate expected serious wounds from an attack roll.

        Computes the damage dice pool from the attack roll excess over
        TN, estimates the average light wounds, and looks up expected
        serious wounds from the wound table using integer light.
        """
        extra_rolled = max(0, attack_roll - self.tn) // 5
        base_roll, base_keep = self.enemy.damage_dice
        light = int(avg(True, base_roll + extra_rolled, base_keep))
        wc_roll, wc_keep = self.wc_dice
        bonus = self.max_bonus("wound_check")
        effective_light = max(0, light - bonus)
        return self.expected_serious(effective_light, wc_roll, wc_keep)

    def _attack_depletion_value(self) -> float:
        """Estimate serious wound reduction from subtracting avg 5k1.

        Compares expected serious wounds at the current enemy attack
        roll vs the attack roll reduced by the average 5k1 result.
        """
        avg_reduction = int(avg(True, 5, 1))
        before = self._estimate_serious(self.enemy.attack_roll)
        reduced = self.enemy.attack_roll - avg_reduction
        if reduced < self.tn:
            return before
        after = self._estimate_serious(reduced)
        return before - after

    def r3t_deplete_attack(self) -> None:
        """R3T: Optionally spend 1 VP to subtract 5k1 from enemy roll.

        Fires during pre_defense. Uses a heuristic to decide whether
        the expected serious wound reduction justifies the VP cost.
        Always spends if the reduction would cause the attack to miss.
        """
        if self.vps <= 0 or not hasattr(self, 'enemy') or not self.enemy:
            return
        if not hasattr(self.enemy, 'attack_roll'):
            return

        avg_reduction = avg(True, 5, 1)

        # Always spend if it would cause a miss
        would_miss = (
            self.enemy.attack_roll - int(avg_reduction) < self.tn
        )

        if would_miss or self._attack_depletion_value() >= self.r3t_attack_sw_threshold:
            reduction = xky(5, 1, True)
            self.enemy.attack_roll -= reduction
            self.vps -= 1
            self.triggers("vps_spent", 1, "parry")

    def r3t_boost_wc(
        self, check: int, light: int, total: int,
    ) -> None:
        """R3T: Optionally spend 1 VP to add 5k1 to wound check.

        Fires during the wound_check event. Estimates whether the
        average 5k1 boost (~8.5) would meaningfully reduce the
        expected serious wounds taken.
        """
        if self.vps <= 0:
            return

        avg_boost = avg(True, 5, 1)
        sw_before = self.calc_serious(total, check)
        sw_after = self.calc_serious(total, check + avg_boost)

        if sw_before - sw_after >= self.r3t_wc_sw_threshold:
            boost = xky(5, 1, True)
            self.auto_once["wound_check"] += boost
            self.vps -= 1
            self.triggers("vps_spent", 1, "wound_check")

    def r5t_trigger(self, vps: int, roll_type: RollType) -> None:
        """R5T: Gain 1 temp VP when spending a VP (not from R5T).

        The r5t_vps counter prevents infinite recursion: the VP
        granted by R5T doesn't itself trigger another R5T grant.
        The counter persists through the combat (not reset per round).
        """
        if self.r5t_vps < vps:
            self.r5t_vps += 1
            self.vps += 1
