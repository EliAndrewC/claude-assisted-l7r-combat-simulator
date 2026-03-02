from __future__ import annotations

from l7r.combatant import Combatant
from l7r.records import ParryRecord
from l7r.types import RollType


class ShibaBushi(Combatant):
    """Shiba Bushi school (Phoenix clan). A protective bodyguard.

    Strategy: Parry-focused defender who protects allies and punishes
    attackers through parry damage.  Interrupt parries cost only 1
    action die (instead of 2), and parrying for others has no penalty.

    Special ability: Interrupt parries cost 1 action die instead of 2.
    May parry attacks directed at adjacent allies with no penalty.
    School ring: Air.
    School knacks: counterattack, double attack, iaijutsu.

    Key techniques:
    - R1T: Extra rolled die on double attack, parry, wound check.
    - R2T: Free raise (+5) on parry.
    - R3T: All parry rolls (hit or miss) deal (2*attack)k1 damage.
    - R4T: +1 Air (free), +3k1 on wound checks.
    - R5T: After successful parry, lower the parried enemy's TN by
      the amount the parry exceeded the attack roll (until next hit).
    """

    school_knacks: list[RollType] = [
        "counterattack", "double_attack", "iaijutsu",
    ]
    r1t_rolls: list[RollType] = ["double_attack", "parry", "wound_check"]
    r2t_rolls: RollType = "parry"
    school_ring = "air"
    r4t_ring_boost = "air"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        # R4T: +3 rolled, +1 kept on wound checks
        if self.rank >= 4:
            self.extra_dice["wound_check"][0] += 3
            self.extra_dice["wound_check"][1] += 1

    def choose_action(self) -> tuple[RollType, Combatant] | None:
        """R5T: Hold all actions until phase 10, then double attack.

        After parrying to debuff enemy TNs, tank a hit to save the last
        action for a devastating double attack against the lowest-TN enemy.
        Pre-R5T delegates to the base class.
        """
        if self.rank < 5:
            return super().choose_action()
        if self.phase != 10:
            return None
        if not self.actions:
            return None

        self.actions.pop(0)
        return "double_attack", self.att_target("double_attack")

    def make_parry(self, auto_success: bool = False) -> ParryRecord:
        """Execute a parry, then apply R3T damage and R5T TN reduction."""
        rec = super().make_parry(auto_success)

        # R3T: parry rolls deal (2*attack)k1 damage regardless of
        # success.  No extra dice from Fire or exceeding the TN.
        if self.rank >= 3:
            damage = self.xky(2 * self.attack, 1, True, "damage")
            wc_rec = self.enemy.wound_check(damage)
            if wc_rec:
                self.triggered_records.append(wc_rec)

        # R5T: lower the parried enemy's TN by the parry excess
        if rec.success and self.rank >= 5:
            excess = max(0, self.parry_roll - self.enemy.attack_roll)
            if excess:
                enemy = self.enemy
                enemy.tn -= excess

                def restore() -> bool:
                    enemy.tn += excess
                    return True

                enemy.events["post_defense"].append(restore)

        return rec

    def make_parry_for(
        self, ally: Combatant, enemy: Combatant,
    ) -> ParryRecord:
        """Parry for an adjacent ally with no TN penalty (SA)."""
        self.enemy = enemy
        return self.make_parry()

    def will_parry(self) -> bool:
        """SA: Interrupt parries cost only 1 action die instead of 2.

        Otherwise uses similar heuristics to the base class until fifth dan, at
        which point we're more likely to want to save our final action for a big
        double attack at the end of the round.
        """
        extra = self.projected_damage(self.enemy, True)
        base = self.projected_damage(self.enemy, False)

        self.interrupt = ""
        if self.predeclare_bonus:
            return True
        elif not self.actions:
            return False
        elif self.rank >= 5 and len(self.actions) == 1:
            # R5T: save last action for double attack unless lethal
            parry = extra + self.serious >= self.sw_to_kill
            if parry:
                if self.actions[0] <= self.phase:
                    self.actions.pop(0)
                else:
                    self.interrupt = "interrupt "
                    self.actions.pop(0)
            return parry
        elif self.actions[0] <= self.phase:
            # Normal parry: current-phase action available
            parry = (
                extra + self.serious >= self.sw_to_kill
                or extra - base >= self.sw_parry_threshold
            )
            if parry:
                self.actions.pop(0)
        else:
            # Interrupt: only costs 1 die (SA) and uses normal
            # threshold since the cost is the same as a regular parry.
            parry = (
                extra + self.serious >= self.sw_to_kill
                or extra - base >= self.sw_parry_threshold
            )
            if parry:
                self.interrupt = "interrupt "
                self.actions.pop(0)

        return parry

    def will_parry_for(
        self, ally: Combatant, enemy: Combatant,
    ) -> bool:
        """Proactively volunteer to parry for adjacent allies (SA).

        Uses the same damage heuristics as will_parry, but projects
        damage against the ally rather than self.
        """
        self.predeclare_bonus = 0
        if not self.actions:
            return False

        extra = ally.projected_damage(enemy, True)
        base = ally.projected_damage(enemy, False)

        self.interrupt = ""
        if self.rank >= 5 and len(self.actions) == 1:
            # R5T: save last action for double attack unless ally would die
            parry = extra + ally.serious >= ally.sw_to_kill
            if parry:
                if self.actions[0] <= self.phase:
                    self.actions.pop(0)
                else:
                    self.interrupt = "interrupt "
                    self.actions.pop(0)
            return parry
        elif self.actions[0] <= self.phase:
            parry = (
                extra + ally.serious >= ally.sw_to_kill
                or extra - base >= self.sw_parry_threshold
            )
            if parry:
                self.actions.pop(0)
        else:
            parry = (
                extra + ally.serious >= ally.sw_to_kill
                or extra - base >= self.sw_parry_threshold
            )
            if parry:
                self.interrupt = "interrupt "
                self.actions.pop(0)

        return parry

    def will_predeclare(self) -> bool:
        """Pre-declare parries every time we have actions to spare."""
        if len(self.actions) > 2:
            self.predeclare_bonus = 5
            return True
        self.predeclare_bonus = 0
        return False
