from l7r.combatant import Combatant


class Professional(Combatant):
    def __init__(self, *args, **kwargs):
        Combatant.__init__(self, *args, **kwargs)

        for i in self.wave_man['damage_compensator']:
            if self.base_damage_rolled < 4:
                self.base_damage_rolled += 1

        for i in self.wave_man['init_bonus']:
            self.extra_dice['initiative'] += 1

        for i in self.wave_man['wc_bonus']:
            self.extra_dice['wound_check'] += 2

        for i in self.ninja['attack_bonus']:
            self.always['attack'] += self.fire

        for i in self.ninja['difficult_attack']:
            self.tn += 5

        self.events['pre_defense'].append(self.better_tn_trigger)
        self.events['pre_defense'].append(self.difficult_attack_trigger)
        self.events['pre_defense'].append(self.damage_reroll_pre_trigger)
        self.events['post_defense'].append(self.damage_reroll_post_trigger)
        self.events['successful_attack'].append(self.difficult_parry_trigger)

    def difficult_parry_trigger(self):
        for i in self.wave_man['difficult_parry']:
            self.attack_roll += 5
            self.auto_once['damage_rolled'] -= 1

    def better_tn_trigger(self):
        for i in self.ninja['better_tn']:
            self.enemy.auto_once['damage_rolled'] += 1

    def difficult_attack_trigger(self):
        for i in self.ninja['difficult_attack']:
            self.enemy.auto_next[enemy.attack_knack] -= 1

    def damage_reroll_pre_trigger(self):
        self.enemy.events['successful_attack'].append(self.damage_reroll_sa_trigger)
        self.old_xky = self.enemy.xky

    def damage_reroll_sa_trigger(self):
        def new_xky(self, roll, keep, reroll, roll_type):
            if roll_type != 'damage':
                return self.enemy.old_xky(roll, keep, reroll, roll_type)
            else:
                roll, keep, bonus = actual_xky(roll, keep)
                dice = sorted([d10(reroll) for i in range(roll)], reverse=True)
                for i in self.enemy.ninja['damage_roll']:
                    dice[i + 1] = max(10, dice[i + 1])

                return bonus + sum(dice[:keep])
        self.enemy.xky = new_xky

    def damage_reroll_post_trigger(self):
        self.enemy.xky = self.old_xky
        self.enemy.events['successful_attack'].remove(self.damage_reroll_sa_trigger)

    def initiative(self):
        Combatant.initiative(self)
        for i in range(self.actions):
            for j in self.ninja['fast_attacks']:
                self.init_order[i] = self.actions[i] = max(1, self.actions[i] - 3)

    def xky(self, roll, keep, reroll, roll_type):
        roll, keep, bonus = actual_xky(roll, keep)
        dice = sorted([d10(reroll) for i in range(roll)], reverse=True)

        for i in self.wave_man['crippled_reroll']:
            if dice[i] == 10:
                dice[i] += d10(True)

        for i in range(roll):
            bump = max(0, 5 - dice[i])
            for j in self.ninja['wc_bump']:
                dice[i] += bump

        result = sum(dice[:keep]) + bonus

        if roll_type == 'damage':
            extra = max(roll - keep, 2 * len(self.ninja['damage_bump']))
            result += sum(dice[-extra:])

            for i in self.wave_man['damage_round_up']:
                result += (5 - result % 5) if result % 5 else 3

        return result

    def next_damage(self, tn, extra_damage):
        roll, keep, serious = Combatant.next_damage(self, tn, extra_damage)
        if not extra_damage:
            negated = max(0, self.attack_roll - tn) // 5
            for i in self.wave_man['parry_bypass']:
                roll += max(2, negated)
                negated = max(0, negated - 2)
        return roll, keep, serious

    def deal_damage(self, tn, extra_damage):
        light, serious = Combatant.deal_damage(self, tn, extra_damage)

        raised_tn = 5 * len(self.wave_man['tougher_wounds'])

        orig_calc = self.enemy.calc_serious

        def calc_serious(self, light, check):
            return orig_calc(self, light - raised_tn, check)
        self.enemy.calc_serious = calc_serious

        def reset_calc():
            self.enemy.calc_serious = orig_calc
            return True
        self.events['post_attack'].append(reset_calc)

        return light + raised_tn, serious

    def make_attack(self):
        success = Combatant.make_attack(self)
        if not success:
            for i in self.wave_man['near_miss']:
                self.attack_roll += 5

            success = self.attack_roll >= self.enemy.tn
            if success:
                self.attack_roll = 0
                self.enemy.triggers('successful_attack')

        return success

    def wound_check(self, light, serious=0):
        for i in self.wave_man['wound_reduction']:
            if self.enemy.last_damage_rolled > 10:
                light = max(0, light - 5)

        Combatant.wound_check(self, light, serious)
