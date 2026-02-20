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

from l7r.combatant import Combatant
from l7r.dice import actual_xky, d10


class Professional(Combatant):
    """A non-samurai combatant with wave man and/or ninja profession abilities.

    Profession abilities modify dice rolls, damage, and wound checks in
    ways that stack with each other but are less powerful than school
    techniques. The key difference from school combatants is that
    professionals have no rank, no school knacks, and their abilities
    are individually selected rather than coming in a fixed progression.
    """

    def __init__(self, *args, **kwargs):
        Combatant.__init__(self, *args, **kwargs)

        for i in self.wave_man["damage_compensator"]:
            if self.base_damage_rolled < 4:
                self.base_damage_rolled += 1

        for i in self.wave_man["init_bonus"]:
            self.extra_dice["initiative"] += 1

        for i in self.wave_man["wc_bonus"]:
            self.extra_dice["wound_check"] += 2

        for i in self.ninja["attack_bonus"]:
            self.always["attack"] += self.fire

        for i in self.ninja["difficult_attack"]:
            self.tn += 5

        self.events["pre_defense"].append(self.better_tn_trigger)
        self.events["pre_defense"].append(self.difficult_attack_trigger)
        self.events["pre_defense"].append(self.damage_reroll_pre_trigger)
        self.events["post_defense"].append(self.damage_reroll_post_trigger)
        self.events["successful_attack"].append(self.difficult_parry_trigger)

    def difficult_parry_trigger(self):
        """Wave man ability: raise the parry TN by 5 but lose 1 rolled
        damage die. Makes our attacks harder to parry at the cost of
        slightly less damage."""
        for i in self.wave_man["difficult_parry"]:
            self.attack_roll += 5
            self.auto_once["damage_rolled"] -= 1

    def better_tn_trigger(self):
        """Ninja ability: force the attacker to roll 1 fewer damage die,
        reducing incoming damage through misdirection."""
        for i in self.ninja["better_tn"]:
            self.enemy.auto_once["damage_rolled"] += 1

    def difficult_attack_trigger(self):
        """Ninja ability: reduce the attacker's rerolled 10s on the next
        attack roll, limiting their explosive dice potential."""
        for i in self.ninja["difficult_attack"]:
            self.enemy.auto_next[self.enemy.attack_knack] -= 1

    def damage_reroll_pre_trigger(self):
        """Set up damage roll interception: monkey-patch the enemy's xky()
        so we can force their lowest kept damage dice up to 10. Saved and
        restored in damage_reroll_post_trigger."""
        self.enemy.events["successful_attack"].append(self.damage_reroll_sa_trigger)
        self.old_xky = self.enemy.xky

    def damage_reroll_sa_trigger(self):
        """Ninja ability: when the enemy hits, replace their xky() with a
        version that forces low damage dice to 10 (paradoxically benefiting
        us less — this ability is about controlling damage variance)."""

        def new_xky(self, roll, keep, reroll, roll_type):
            if roll_type != "damage":
                return self.enemy.old_xky(roll, keep, reroll, roll_type)
            else:
                roll, keep, bonus = actual_xky(roll, keep)
                dice = sorted([d10(reroll) for i in range(roll)], reverse=True)
                for i in self.enemy.ninja["damage_roll"]:
                    dice[i + 1] = max(10, dice[i + 1])

                return bonus + sum(dice[:keep])

        self.enemy.xky = new_xky

    def damage_reroll_post_trigger(self):
        """Restore the enemy's original xky() after the attack resolves."""
        self.enemy.xky = self.old_xky
        self.enemy.events["successful_attack"].remove(self.damage_reroll_sa_trigger)

    def initiative(self):
        """Ninja ability: lower each action die by 3 (minimum 1), letting
        the ninja act earlier in each phase."""
        Combatant.initiative(self)
        for i in range(self.actions):
            for j in self.ninja["fast_attacks"]:
                self.init_order[i] = self.actions[i] = max(1, self.actions[i] - 3)

    def xky(self, roll, keep, reroll, roll_type):
        """Custom dice roller that applies wave man and ninja dice modifications.

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

        for i in range(roll):
            bump = max(0, 5 - dice[i])
            for j in self.ninja["wc_bump"]:
                dice[i] += bump

        result = sum(dice[:keep]) + bonus

        if roll_type == "damage":
            extra = max(roll - keep, 2 * len(self.ninja["damage_bump"]))
            result += sum(dice[-extra:])

            for i in self.wave_man["damage_round_up"]:
                result += (5 - result % 5) if result % 5 else 3

        return result

    def next_damage(self, tn, extra_damage):
        """Wave man "parry_bypass": even when the defender parried (no extra
        damage), still roll some bonus dice based on how much we exceeded
        the TN. This partially negates the parry's damage reduction."""
        roll, keep, serious = Combatant.next_damage(self, tn, extra_damage)
        if not extra_damage:
            negated = max(0, self.attack_roll - tn) // 5
            for i in self.wave_man["parry_bypass"]:
                roll += max(2, negated)
                negated = max(0, negated - 2)
        return roll, keep, serious

    def deal_damage(self, tn, extra_damage):
        """Wave man "tougher_wounds": raise the effective TN of the enemy's
        wound check by temporarily making their calc_serious treat the
        light wounds as higher than they actually are."""
        light, serious = Combatant.deal_damage(self, tn, extra_damage)

        raised_tn = 5 * len(self.wave_man["tougher_wounds"])

        orig_calc = self.enemy.calc_serious

        def calc_serious(self, light, check):
            return orig_calc(self, light - raised_tn, check)

        self.enemy.calc_serious = calc_serious

        def reset_calc():
            self.enemy.calc_serious = orig_calc
            return True

        self.events["post_attack"].append(reset_calc)

        return light + raised_tn, serious

    def make_attack(self):
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
                self.enemy.triggers("successful_attack")

        return success

    def wound_check(self, light, serious=0):
        """Wave man "wound_reduction": if the attacker rolled many damage
        dice (more than 10), reduce the light wound total by 5. This
        mitigates damage from high-powered attacks."""
        for i in self.wave_man["wound_reduction"]:
            if self.enemy.last_damage_rolled > 10:
                light = max(0, light - 5)

        Combatant.wound_check(self, light, serious)
