from __future__ import annotations

from math import ceil

from l7r.combatant import Combatant
from l7r.records import AttackRecord
from l7r.types import RollType


class BayushiBushi(Combatant):
    """Bayushi Bushi school (Scorpion clan). A VP-efficient poison-style school.

    Strategy: Open with feints against unwounded enemies (to apply damage
    via R3T feint-as-damage), then switch to normal/double attacks once
    enemies are carrying light wounds. Extremely VP-efficient because the
    special ability converts VP spending on attacks into bonus damage dice.

    Special ability: Each VP spent on attack/feint/double attack adds +1
    rolled and +1 kept damage die.
    School ring: Fire.
    School knacks: double attack, feint, iaijutsu.

    Key techniques:
    - R1T: Extra rolled die on attack, double attack, iaijutsu.
    - R2T: Free raise (+5) on double attacks.
    - R3T: Feints deal damage (attack skill)k1 — turns feints offensive.
    - R4T: Gain a shared +5 disc bonus after every attack.
    - R5T: Wound check failures only count half the excess (halves serious).

    Higher vp_fail_threshold (0.85) because VPs are so valuable for damage.
    Higher datt_threshold (0.3) because R2T makes double attacks cheaper.
    """

    hold_one_action = False
    base_wc_threshold = 25
    vp_fail_threshold = 0.85
    datt_threshold = 0.3

    school_knacks: list[RollType] = ["double_attack", "feint", "iaijutsu"]
    r1t_rolls: list[RollType] = ["attack", "double_attack", "iaijutsu"]
    r2t_rolls: RollType = "double_attack"

    school_ring = "fire"
    r4t_ring_boost = "fire"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)
        self.events["vps_spent"].append(self.sa_trigger)
        self.events["pre_attack"].append(self.r3t_trigger)
        self.events["post_attack"].append(self.r4t_trigger)
        self.events["post_attack"].append(self.reset_damage)

    def sa_trigger(self, vps: int, roll_type: RollType) -> None:
        """Special ability: each VP spent on an attack adds +1 rolled and
        +1 kept damage die. This makes even 1 VP dramatically increase
        damage output."""
        if roll_type in ["feint", "attack", "double_attack"]:
            for i in range(vps):
                self.base_damage_rolled += 1
                self.base_damage_kept += 1

    def r3t_trigger(self) -> None:
        """R3T: Feints deal (attack skill)k1 damage instead of nothing.
        Turns feints from a utility action into a real offensive threat."""
        if self.rank >= 3 and self.attack_knack == "feint":
            self.base_damage_rolled, self.base_damage_kept = self.attack, 1

    def reset_damage(self) -> None:
        """Restore base damage dice after R3T feint damage modification."""
        self.base_damage_rolled = self.__class__.base_damage_rolled
        self.base_damage_kept = self.__class__.base_damage_kept

    def r4t_trigger(self) -> None:
        """R4T: After every attack, gain a +5 discretionary bonus usable
        on any future feint, attack, or double attack."""
        bonus = [5]
        if self.rank >= 4:
            for knack in ["feint", "attack", "double_attack"]:
                self.multi[knack].append(bonus)

    def choose_action(self) -> tuple[RollType, Combatant] | None:
        """Prefer feinting against unwounded targets (to apply R3T feint
        damage as an opener), then fall back to normal attack logic."""
        if self.actions and self.actions[0] <= self.phase:
            target = self.att_target("feint")
            if not target.light:
                self.actions.pop(0)
                return "feint", target

            return Combatant.choose_action(self)

    def next_damage(self, tn: int, extra_damage: bool) -> tuple[int, int, int]:
        if self.rank >= 3 and self.attack_knack == "feint":
            return self.base_damage_rolled, self.base_damage_kept, 0

        return Combatant.next_damage(self, tn, extra_damage)

    def att_target(self, knack: RollType = "attack") -> Combatant:
        """Prefer attacking enemies who already carry light wounds (to
        pile on before they can recover), unless no one is wounded."""
        target = max(self.attackable, key=lambda e: e.light)
        return target if target.light else Combatant.att_target(self, knack)

    def calc_serious(self, light: int, check: float) -> int:
        """R5T: Failed wound checks only count half the excess when
        calculating serious wounds. Makes the Bayushi extremely durable
        at Rank 5."""
        if self.rank == 5:
            return int(ceil(max(0, (light - check) // 2) / 10))

        return Combatant.calc_serious(self, light, check)

    def expected_serious(self, light: int, wc_roll: int, wc_keep: int) -> float:
        """R5T: halves damage before the staircase. Use halved light
        with the standard table since calc_serious(light, check) with
        halving equals calc_serious(light // 2, check) for standard."""
        if self.rank == 5:
            return Combatant.expected_serious(self, light // 2, wc_roll, wc_keep)
        return Combatant.expected_serious(self, light, wc_roll, wc_keep)

    def make_attack(self) -> AttackRecord:
        """R3T also makes feints that hit (even without beating the TN by
        the normal margin) count as successful for damage purposes."""
        rec = Combatant.make_attack(self)
        if not rec.hit and self.rank >= 3 and self.attack_roll >= self.enemy.tn:
            rec.hit = True
        return rec

    def att_vps(self, tn: int, roll: int, keep: int) -> int:
        """Always spend at least 1 VP on attacks to trigger the special
        ability's damage bonus, even if the base roll would already hit."""
        vps = Combatant.att_vps(self, tn, roll, keep)
        if self.vps and not vps:
            self.vps -= 1
            self.triggers("vps_spent", vps, self.attack_knack)
            vps += 1
        return vps
