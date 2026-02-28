from __future__ import annotations

from l7r.combatant import Combatant
from l7r.types import RollType


class AkodoBushi(Combatant):
    """Akodo Bushi school (Lion clan). A feint-focused tactical school.

    Strategy: Feint early to stockpile VPs (special ability grants 4 VPs
    per successful feint), then spend those VPs on powerful attacks.
    Excels at prolonged fights where resource accumulation pays off.

    Special ability: +4 temp VPs after successful feint.
    School ring: Water.
    School knacks: double attack, feint, iaijutsu.

    Key techniques:
    - R1T: Extra rolled die on double attack, feint, wound check.
    - R2T: Free raise (+5) on wound checks.
    - R3T: Convert wound check excess into discretionary attack bonuses.
    - R4T: Spend VPs after wound check for additional free raises.
    - R5T: Spend VPs during wound check to reflect damage back at attacker.

    Never holds actions (hold_one_action=False) because feints generate
    new actions. Higher wc_threshold (25) because accumulated disc bonuses
    on wound checks make it safe to carry more light wounds.
    """

    hold_one_action = False
    base_wc_threshold = 25

    feint_vp_threshold = 4
    """VP threshold below which we feint instead of attacking."""

    school_knacks: list[RollType] = ["double_attack", "feint", "iaijutsu"]
    r1t_rolls: list[RollType] = ["double_attack", "feint", "wound_check"]
    r2t_rolls: RollType = "wound_check"

    school_ring = "water"
    r4t_ring_boost = "water"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)
        self.events["successful_attack"].append(self.sa_trigger)
        self.events["post_attack"].append(self.sa_failed_feint)
        self.events["wound_check"].append(self.r3t_trigger)
        self.events["wound_check"].append(self.r5t_trigger)

    def sa_trigger(self) -> None:
        """Special ability: gain 4 temp VPs on a successful feint.
        This is the school's core resource engine."""
        if self.attack_knack == "feint":
            self.vps += self.feint_vp_threshold

    def sa_failed_feint(self) -> None:
        """Special ability: gain 1 VP on a failed feint."""
        if self.attack_knack == "feint" and self.attack_roll < self.enemy.tn:
            self.vps += 1

    def r3t_trigger(self, check: int, light: int, total: int) -> None:
        """R3T: When wound check exceeds the TN, convert the excess into
        discretionary bonuses usable on attacks. The harder we shrug off
        wounds, the harder we hit back."""
        exceeded = max(0, check - light)
        if exceeded and self.rank >= 3:
            disc = [self.attack * (exceeded // 5)]
            for knack in ["attack", "double_attack", "feint"]:
                self.multi[knack].append(disc)

    def r5t_trigger(self, check: int, light: int, total: int) -> None:
        """R5T: During wound check, spend VPs to deal 10 light wounds per
        VP back to the attacker. Only activates when we have light wounds
        to spare (>= 10) and VPs to spend (> 2)."""
        if self.rank == 5:
            damage = 0
            while light >= 10 and self.vps > 2:
                light -= 10
                damage += 10
                self.vps -= 1
            if damage:
                self.enemy.wound_check(damage)

    def choose_action(self) -> tuple[RollType, Combatant] | None:
        """Feint when low on VPs to refuel, then attack normally once we
        have disc bonuses stockpiled from R3T wound check triggers."""
        if self.actions and self.actions[0] <= self.phase:
            if self.vps < 4:
                self.actions.pop(0)
                return "feint", self.att_target()

            if self.disc_bonuses("attack"):
                return Combatant.choose_action(self)

    def disc_bonus(self, roll_type: RollType, needed: int) -> int:
        """Aggressively spend disc bonuses on attacks: if we have a large
        stockpile (30+), spend half of it as bonus even if not strictly
        needed, to convert accumulated resources into damage."""
        bonus = Combatant.disc_bonus(self, roll_type, needed)
        remaining = self.disc_bonuses(roll_type)
        if len(remaining) > 1 and sum(remaining) >= 30 and roll_type in ["attack", "double_attack"]:
            bonus += Combatant.disc_bonus(self, roll_type, sum(remaining) / 2)
        return bonus

    def need_higher_wc(self, light: int, check: int) -> bool:
        """Check if spending VPs to boost the wound check would actually
        prevent serious wounds. Used by wc_bonus to avoid wasteful spending."""
        if self.serious + 1 == self.sw_to_kill:
            needed = max(0, light - check)
        else:
            needed = max(0, light - check - 9)

        return needed < self.max_bonus("wound_check")

    def wc_bonus(self, light: int, check: int) -> tuple[int, list]:
        """R4T: Spend VPs after seeing the wound check roll to buy free
        raises (+5 each). Spends 1 VP for a single raise, or 2 VPs for
        a double raise when a single wouldn't cross a wound threshold."""
        if self.rank >= 4:
            while self.need_higher_wc(light, check):
                mb = self.max_bonus("wound_check")
                needed = 1
                if self.calc_serious(light, check + mb) == self.calc_serious(light, check + mb + 5):
                    needed = 2

                if self.vps >= needed:
                    self.vps -= needed
                    self.auto_once["wound_check"] += 5 * needed
                else:
                    break

        return Combatant.wc_bonus(self, light, check)
