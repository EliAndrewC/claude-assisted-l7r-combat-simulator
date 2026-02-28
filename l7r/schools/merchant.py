from __future__ import annotations

from l7r.combatant import Combatant
from l7r.dice import avg, d10, actual_xky
from l7r.records import DiceRoll, WoundCheckRecord
from l7r.types import RollType


class Merchant(Combatant):
    """Merchant school. Post-roll VP spending and other dice shenanigans.

    Strategy: Water-based survivalist. The special ability allows spending
    VPs after seeing the roll result. The Merchant never wastes VPs on rolls
    that would have succeeded anyway, and can precisely target the gap when
    a roll falls short.

    Special ability: May spend VPs after seeing the roll result instead of
    before. Overrides att_vps/parry_vps/wc_vps to return 0 (suppressing
    pre-roll VP spending) and handles VP decisions inside xky() after dice
    are rolled.
    School ring: Water.
    School knacks: discern honor, oppose knowledge, worldliness.

    Key techniques:
    - R1T: Extra rolled die on wound check.
    - R2T: Free raise (+5) on interrogation.
    - R3T: 10 shared free raises on attack + wound check.
    - R4T: +1 Water (free). Stipend bonus (non-combat, skipped).
    - R5T: After rolling, may reroll all dice that sum to >= 5*(X-1)
      where X is the number of dice being rerolled. Implemented by
      overriding xky() for combat rolls.
    """

    school_knacks: list[RollType] = ["discern_honor", "oppose_knowledge", "worldliness"]
    r1t_rolls: list[RollType] = ["wound_check"]
    r2t_rolls: RollType = "interrogation"
    school_ring = "water"
    r4t_ring_boost = "water"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        if self.rank >= 3:
            raises = [5] * 10
            for roll_type in ["attack", "wound_check"]:
                self.multi[roll_type].append(raises)

    # --- SA: Suppress pre-roll VP spending ---

    def att_vps(self, tn: int, roll: int, keep: int) -> int:
        """Merchant never pre-commits VPs to attacks; handled post-roll."""
        return 0

    def parry_vps(self, tn: int, roll: int, keep: int) -> int:
        """Merchant never pre-commits VPs to parries; handled post-roll."""
        return 0

    def wc_vps(self, light: int, roll: int, keep: int) -> int:
        """Merchant never pre-commits VPs to wound checks; handled post-roll."""
        return 0

    def wound_check(self, light: int, serious: int = 0, **kwargs) -> WoundCheckRecord:
        """Stash light_total so xky can access it for post-roll VP decisions."""
        self._wc_light_total = light + self.light
        return Combatant.wound_check(self, light, serious, **kwargs)

    # --- SA + R5T: Post-roll VP spending inside xky ---

    def xky(self, roll: int, keep: int, reroll: bool, roll_type: RollType) -> int:
        """Roll dice, apply R5T reroll, then decide VPs after seeing results.

        Flow:
        1. Apply overflow rules via actual_xky
        2. Roll base dice
        3. R5T reroll (rank >= 5): greedy 5/6-seeded reroll
        4. Skip VP spending for damage rolls
        5. Decide post-roll VPs based on roll_type
        6. If VPs > 0: fire vps_spent, deduct, add VP dice
        7. Return final result
        """
        roll, keep, bonus = actual_xky(roll, keep)
        dice = [d10(reroll) for _ in range(roll)]
        dice.sort()

        # R5T: reroll dice whose sum >= 5*(X-1)
        if self.rank >= 5:
            to_reroll = [i for i, d in enumerate(dice) if d in (5, 6)]
            reroll_sum = sum(dice[i] for i in to_reroll)

            candidates = [
                i for i, d in enumerate(dice)
                if d <= 4 and i not in set(to_reroll)
            ]
            for i in reversed(candidates):
                new_count = len(to_reroll) + 1
                new_sum = reroll_sum + dice[i]
                if new_sum >= 5 * (new_count - 1):
                    to_reroll.append(i)
                    reroll_sum = new_sum

            for i in to_reroll:
                dice[i] = d10(reroll)

            dice.sort()

        # Damage rolls: no VP spending, return immediately
        if roll_type == "damage":
            total = bonus + sum(dice[-keep:])
            self.last_dice_roll = self._build_dice_roll(dice, roll, keep, bonus, reroll, total)
            return total

        # Decide post-roll VPs
        rolled = len(dice)
        kept = keep
        vps = self._decide_post_roll_vps(dice, rolled, kept, bonus, reroll, roll_type)

        if vps > 0:
            self.triggers("vps_spent", vps, roll_type)
            self.vps -= vps
            for _ in range(vps):
                if rolled < 10:
                    dice.append(d10(reroll))
                    rolled += 1
                    kept += 1
                else:
                    # +1 rolled overflows to +1 kept, plus VP's
                    # own +1 kept = net +2 kept (capped at 10).
                    new_kept = kept + 2
                    if new_kept > 10:
                        bonus += new_kept - 10
                        kept = 10
                    else:
                        kept = new_kept

        dice.sort()
        total = bonus + sum(dice[-kept:])
        self.last_dice_roll = self._build_dice_roll(dice, rolled, kept, bonus, reroll, total)
        return total

    @staticmethod
    def _build_dice_roll(
        dice: list[int], roll: int, keep: int, bonus: int, reroll: bool, total: int,
    ) -> DiceRoll:
        """Build a DiceRoll record from the Merchant's raw dice list."""
        from l7r.records import DieResult
        sorted_dice = sorted(dice)
        die_results = []
        for i, face in enumerate(sorted_dice):
            die_results.append(DieResult(
                face=face,
                kept=i >= len(sorted_dice) - keep,
                exploded=face > 10,
            ))
        return DiceRoll(
            roll=roll, keep=keep, reroll=reroll,
            dice=die_results, overflow_bonus=bonus, total=total,
        )

    def _decide_post_roll_vps(
        self,
        dice: list[int],
        rolled: int,
        kept: int,
        bonus: int,
        reroll: bool,
        roll_type: RollType,
    ) -> int:
        """Dispatch VP decision by roll type."""
        if self.vps <= 0:
            return 0

        attack_types = {"attack", "counterattack", "double_attack", "feint", "iaijutsu", "lunge"}  # merchants can theoretically buy any of these
        if roll_type in attack_types and hasattr(self, "enemy"):
            return self._attack_post_roll_vps(dice, rolled, kept, bonus, reroll)
        elif roll_type == "parry" and hasattr(self, "enemy"):
            return self._parry_post_roll_vps(dice, rolled, kept, bonus, reroll)
        elif roll_type == "wound_check" and hasattr(self, "_wc_light_total"):
            return self._wc_post_roll_vps(dice, rolled, kept, bonus, reroll)
        return 0

    def _simulate_vp_result(
        self,
        dice: list[int],
        rolled: int,
        kept: int,
        bonus: int,
        reroll: bool,
        n_vps: int,
    ) -> float:
        """Estimate result if n_vps are spent, without actually rolling.

        For each VP: if rolled < 10, add avg(reroll, 1, 1) as an estimated
        die value and increment both rolled and kept. If rolled >= 10,
        the +1 rolled overflows to +1 kept plus the VP's own +1 kept
        gives net +2 kept (capped at 10, excess becomes +2 bonus each).
        """
        sim_dice = list(dice)
        sim_rolled = rolled
        sim_kept = kept
        sim_bonus = bonus

        for _ in range(n_vps):
            if sim_rolled < 10:
                sim_dice.append(avg(reroll, 1, 1))
                sim_rolled += 1
                sim_kept += 1
            else:
                new_kept = sim_kept + 2
                if new_kept > 10:
                    sim_bonus += new_kept - 10
                    sim_kept = 10
                else:
                    sim_kept = new_kept

        sim_dice.sort()
        return sim_bonus + sum(sim_dice[-sim_kept:])

    def _attack_post_roll_vps(
        self,
        dice: list[int],
        rolled: int,
        kept: int,
        bonus: int,
        reroll: bool,
    ) -> int:
        """Decide VPs for attack rolls. TN = self.enemy.tn."""
        if self.vps <= 0:
            return 0

        tn = self.enemy.tn
        max_att_bonus = self.max_bonus(self.attack_knack)
        current = bonus + sum(sorted(dice)[-kept:])

        # Already hitting — consider spending VPs for extra damage
        if current + max_att_bonus >= tn:
            vps = 0
            while vps < self.vps:
                current_with_vps = self._simulate_vp_result(
                    dice, rolled, kept, bonus, reroll, vps,
                )
                next_with_vps = self._simulate_vp_result(
                    dice, rolled, kept, bonus, reroll, vps + 1,
                )
                excess_cur = max(0, current_with_vps + max_att_bonus - tn)
                excess_next = max(0, next_with_vps + max_att_bonus - tn)
                extra_rolled_cur = int(excess_cur) // 5
                extra_rolled_next = int(excess_next) // 5
                damage_cur = self._avg_damage(extra_rolled_cur)
                damage_next = self._avg_damage(extra_rolled_next)
                if damage_next - damage_cur >= self.vp_damage_threshold:
                    vps += 1
                else:
                    break
            return vps

        # Not hitting — find minimum VPs to close the gap
        for n in range(1, self.vps + 1):
            estimated = self._simulate_vp_result(dice, rolled, kept, bonus, reroll, n)
            if estimated + max_att_bonus >= tn:
                return n

        # Even all VPs can't close the gap
        return 0

    def _parry_post_roll_vps(
        self,
        dice: list[int],
        rolled: int,
        kept: int,
        bonus: int,
        reroll: bool,
    ) -> int:
        """Decide VPs for parry rolls. TN = self.enemy.attack_roll."""
        if self.vps <= 0:
            return 0

        tn = self.enemy.attack_roll
        max_parry_bonus = self.max_bonus("parry") + self.predeclare_bonus
        current = bonus + sum(sorted(dice)[-kept:])

        if current + max_parry_bonus >= tn:
            return 0

        for n in range(1, self.vps + 1):
            estimated = self._simulate_vp_result(dice, rolled, kept, bonus, reroll, n)
            if estimated + max_parry_bonus >= tn:
                return n

        return 0

    def _wc_post_roll_vps(
        self,
        dice: list[int],
        rolled: int,
        kept: int,
        bonus: int,
        reroll: bool,
    ) -> int:
        """Decide VPs for wound checks. TN = self._wc_light_total."""
        if self.vps <= 0:
            return 0

        light_total = self._wc_light_total
        max_wc_bonus = self.max_bonus("wound_check")

        # Work backwards from max VPs
        base_result = self._simulate_vp_result(dice, rolled, kept, bonus, reroll, 0)
        base_serious = self.calc_serious(light_total, base_result + max_wc_bonus)

        for n in range(self.vps, 0, -1):
            est_result = self._simulate_vp_result(dice, rolled, kept, bonus, reroll, n)
            est_serious = self.calc_serious(light_total, est_result + max_wc_bonus)
            sw_prevented = base_serious - est_serious
            if sw_prevented > 0 and (
                sw_prevented / n >= self.sw2vp_threshold
                or est_serious + self.serious >= self.sw_to_kill
            ):
                return n

        return 0
