"""
Professional combatants: non-samurai fighters with profession abilities.

Professionals (wave men, ninja, etc.) don't have school ranks or school
knacks. Instead they pick profession abilities — each ability can be taken
twice. These abilities are tracked as lists on the combatant (e.g.
self.wave_man["near_miss"] might be [1, 1] if taken twice). The "for i in
self.wave_man[ability]" pattern applies the ability once per time it was taken.

This class overrides xky(), initiative(), next_damage(), deal_damage(),
make_attack(), and wound_check() to apply the various wave man and ninja
profession abilities during combat.
"""

from __future__ import annotations

from typing import Any

from l7r.combatant import Combatant
from l7r.dice import actual_xky, d10
from l7r.types import RollType


class Professional(Combatant):
    """A non-samurai combatant with wave man and/or ninja profession abilities.

    Profession abilities modify dice rolls, damage, and wound checks in
    ways that stack with each other but are less powerful than school
    techniques. The key difference from school combatants is that
    professionals have no rank, no school knacks, and their abilities
    are individually selected rather than coming in a fixed progression.
    """

    base_damage_rolled = 2
    """Professionals use a 2k2 weapon by default (e.g. a short sword or
    club), unlike samurai who carry a 4k2 katana."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        Combatant.__init__(self, *args, **kwargs)

        for i in self.wave_man["damage_compensator"]:
            if self.base_damage_rolled < 4:
                self.base_damage_rolled += 1

        for i in self.wave_man["init_bonus"]:
            self.extra_dice["initiative"][0] += 1

        for i in self.wave_man["wc_bonus"]:
            self.extra_dice["wound_check"][0] += 2

        for i in self.ninja["attack_bonus"]:
            self.always["attack"] += self.fire

        for i in self.ninja["difficult_attack"]:
            self.tn += 5

        self.events["pre_defense"].append(self.better_tn_trigger)
        self.events["pre_defense"].append(self.difficult_attack_pre_trigger)
        self.events["pre_defense"].append(self.damage_reroll_pre_trigger)
        self.events["post_defense"].append(self.better_tn_post_trigger)
        self.events["post_defense"].append(self.difficult_attack_post_trigger)
        self.events["post_defense"].append(self.damage_reroll_post_trigger)
        self.events["successful_attack"].append(self.difficult_parry_trigger)

    def difficult_parry_trigger(self) -> None:
        """Wave man ability: raise the parry TN by 5.

        The +5 to attack_roll makes the parry harder (parry TN =
        attack_roll), but attack_roll also feeds extra damage dice
        via ``(attack_roll - tn) // 5``.  The -1 to damage_rolled
        cancels out the phantom extra die that the +5 would
        otherwise generate.  The math is exact: +5 always produces
        exactly 1 extra die (since the attack already hit, so
        attack_roll >= tn), and -1 cancels it.
        """
        for i in self.wave_man["difficult_parry"]:
            self.attack_roll += 5
            self.auto_once["damage_rolled"] -= 1

    def better_tn_trigger(self) -> None:
        """Ninja ability: attacker rolls 1 fewer die on attack rolls against
        us, to a minimum of their Fire ring."""
        self._better_tn_reduced = 0
        for i in self.ninja["better_tn"]:
            roll, _ = self.enemy.att_dice(self.enemy.attack_knack)
            if roll > self.enemy.fire:
                self.enemy.extra_dice[self.enemy.attack_knack][0] -= 1
                self._better_tn_reduced += 1

    def better_tn_post_trigger(self) -> None:
        """Restore attacker's rolled dice after the attack resolves."""
        self.enemy.extra_dice[self.enemy.attack_knack][0] += self._better_tn_reduced

    def difficult_attack_pre_trigger(self) -> None:
        """Ninja ability: register per-attack handler for the difficult_attack
        damage clause (extra damage die if attacker exceeds raised TN)."""
        if self.ninja["difficult_attack"]:
            self.enemy.events["successful_attack"].append(
                self._difficult_attack_sa_trigger
            )

    def _difficult_attack_sa_trigger(self) -> None:
        """If the attacker's hit exceeded our TN enough to generate bonus
        damage dice, the attacker gets 1 extra damage die per instance."""
        for i in self.ninja["difficult_attack"]:
            if self.enemy.attack_roll >= self.tn + 5:
                self.enemy.auto_once["damage_rolled"] += 1

    def difficult_attack_post_trigger(self) -> None:
        """Remove the per-attack successful_attack handler."""
        if self._difficult_attack_sa_trigger in self.enemy.events["successful_attack"]:
            self.enemy.events["successful_attack"].remove(
                self._difficult_attack_sa_trigger
            )

    def damage_reroll_pre_trigger(self) -> None:
        """Set up damage roll interception: monkey-patch the enemy's xky()
        so we can force their lowest kept damage dice up to 10. Saved and
        restored in damage_reroll_post_trigger."""
        self.enemy.events["successful_attack"].append(self.damage_reroll_sa_trigger)
        self.old_xky = self.enemy.xky

    def damage_reroll_sa_trigger(self) -> None:
        """Ninja ability: when the enemy hits, replace their xky() with a
        version that caps exploded damage dice back to 10, reducing the
        attacker's damage variance on their strongest dice.

        The closure captures ``self`` (the ninja/defender) so we can
        reference ``self.old_xky`` and ``self.ninja["damage_roll"]``
        without relying on the attacker's attributes.
        """

        def new_xky(roll: int, keep: int, reroll: bool, roll_type: RollType) -> int:
            if roll_type != "damage":
                return self.old_xky(roll, keep, reroll, roll_type)
            else:
                roll, keep, bonus = actual_xky(roll, keep)
                dice = sorted([d10(reroll) for i in range(roll)], reverse=True)
                for i in self.ninja["damage_roll"]:
                    dice[i + 1] = min(10, dice[i + 1])

                return bonus + sum(dice[:keep])

        self.enemy.xky = new_xky

    def damage_reroll_post_trigger(self) -> None:
        """Restore the enemy's original xky() after the attack resolves."""
        self.enemy.xky = self.old_xky
        self.enemy.events["successful_attack"].remove(self.damage_reroll_sa_trigger)

    def initiative(self) -> None:
        """Ninja ability: lower each action die by 2 (minimum 1), letting
        the ninja act earlier in each phase."""
        Combatant.initiative(self)
        for i in range(len(self.actions)):
            for j in self.ninja["fast_attacks"]:
                self.init_order[i] = self.actions[i] = max(1, self.actions[i] - 2)

    def xky(self, roll: int, keep: int, reroll: bool, roll_type: RollType) -> int:
        """Custom dice roller that applies wave man and ninja dice
        modifications.

        Wave man "crippled_reroll" lets specific dice reroll 10s even when
        crippled. Ninja "wc_bump" raises low dice to at least 5. For damage
        rolls, ninja "damage_bump" keeps extra unkept dice, and wave man
        "damage_round_up" rounds the result up to the nearest multiple of 5.
        """
        roll, keep, bonus = actual_xky(roll, keep)
        dice = sorted([d10(reroll) for i in range(roll)], reverse=True)

        for i in self.wave_man["crippled_reroll"]:
            if dice[i] == 10:
                dice[i] += d10(True)

        if roll_type == "wound_check":
            for i in range(roll):
                bump = max(0, 5 - dice[i])
                for j in self.ninja["wc_bump"]:
                    dice[i] += bump

        result = sum(dice[:keep]) + bonus

        if roll_type == "damage":
            extra = min(roll - keep, 2 * len(self.ninja["damage_bump"]))
            if extra > 0:
                result += sum(dice[-extra:])

            for i in self.wave_man["damage_round_up"]:
                result += (5 - result % 5) if result % 5 else 3

        return result

    def next_damage(self, tn: int, extra_damage: bool) -> tuple[int, int, int]:
        """Wave man "parry_bypass": even when the defender parried (no extra
        damage), still roll some bonus dice based on how much we exceeded
        the TN. This partially negates the parry's damage reduction."""
        roll, keep, serious = Combatant.next_damage(self, tn, extra_damage)
        if not extra_damage:
            negated = max(0, self.attack_roll - tn) // 5
            for i in self.wave_man["parry_bypass"]:
                roll += min(2, negated)
                negated = max(0, negated - 2)
        return roll, keep, serious

    def deal_damage(self, tn: int, extra_damage: bool = True) -> tuple[int, int]:
        """Wave man "tougher_wounds": raise the effective TN of the enemy's
        wound check by temporarily making their calc_serious treat the
        light wounds as higher than they actually are."""
        light, serious = Combatant.deal_damage(self, tn, extra_damage)

        raised_tn = 5 * len(self.wave_man["tougher_wounds"])

        orig_calc = self.enemy.calc_serious

        def calc_serious(light: int, check: float) -> int:
            return orig_calc(light - raised_tn, check)

        self.enemy.calc_serious = calc_serious

        def reset_calc() -> bool:
            self.enemy.calc_serious = orig_calc
            return True

        self.events["post_attack"].append(reset_calc)

        return light + raised_tn, serious

    def make_attack(self) -> bool:
        """Wave man "near_miss": if the attack misses, add +5 to the roll
        and re-check. This turns near-misses into hits (albeit with no
        bonus damage, since attack_roll is reset to 0)."""
        success = Combatant.make_attack(self)
        if not success:
            for i in self.wave_man["near_miss"]:
                self.attack_roll += 5

            success = self.attack_roll >= self.enemy.tn
            if success:
                self.attack_roll = 0
                self.triggers("successful_attack")

        return success

    def wound_check(self, light: int, serious: int = 0) -> None:
        """Wave man "wound_reduction": if the attacker's hit generated
        extra damage dice from exceeding the TN, reduce the light wound
        total by 5."""
        for i in self.wave_man["wound_reduction"]:
            if self.enemy.attack_roll >= self.tn + 5:
                light = max(0, light - 5)

        Combatant.wound_check(self, light, serious)
