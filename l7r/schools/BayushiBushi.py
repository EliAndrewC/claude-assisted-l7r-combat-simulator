from math import ceil

from l7r.combatant import Combatant


class BayushiBushi(Combatant):
    hold_one_action = False
    base_wc_threshold = 25
    vp_fail_threshold = 0.85
    datt_threshold = 0.3

    school_knacks = ['double_attack', 'feint', 'iaijutsu']
    r1t_rolls = ['attack', 'double_attack', 'iaijutsu']
    r2t_rolls = 'double_attack'

    def __init__(self, **kwargs):
        Combatant.__init__(self, **kwargs)
        self.events['vps_spent'].append(self.sa_trigger)
        self.events['pre_attack'].append(self.r3t_trigger)
        self.events['post_attack'].append(self.r4t_trigger)
        self.events['post_attack'].append(self.reset_damage)

    def sa_trigger(self, vps, roll_type):
        if roll_type in ['feint', 'attack', 'double_attack']:
            for i in range(vps):
                self.base_damage_rolled += 1
                self.base_damage_kept += 1

    def r3t_trigger(self):
        if self.rank >= 3 and self.attack_knack == 'feint':
            self.base_damage_rolled, self.base_damage_kept = self.attack, 1

    def reset_damage(self):
        self.base_damage_rolled = self.__class__.base_damage_rolled
        self.base_damage_kept = self.__class__.base_damage_kept

    def r4t_trigger(self):
        bonus = [5]
        if self.rank >= 4:
            for knack in ['feint', 'attack', 'double_attack']:
                self.multi[knack].append(bonus)

    def choose_action(self):
        if self.actions and self.actions[0] <= self.phase:
            target = self.att_target('feint')
            if not target.light:
                self.actions.pop(0)
                return 'feint', target

            return Combatant.choose_action(self)

    def next_damage(self, tn, extra_damage):
        if self.rank >= 3 and self.attack_knack == 'feint':
            return self.base_damage_rolled, self.base_damage_kept, 0

        return Combatant.next_damage(self, tn, extra_damage)

    def att_target(self, knack=''):
        light, target = sorted((e.light, e) for e in self.attackable)[-1]
        return target if light else Combatant.att_target(self, knack)

    def calc_serious(self, light, check):
        if self.rank == 5:
            return int(ceil(max(0, (light - check) // 2) / 10))

        return Combatant.calc_serious(self, light, check)

    def make_attack(self):
        return Combatant.make_attack(self) or self.rank >= 3 and self.attack_roll >= self.enemy.tn

    def att_vps(self, tn, roll, keep):
        vps = Combatant.att_vps(self, tn, roll, keep)
        if self.vps and not vps:
            self.vps -= 1
            self.triggers('vps_spent', vps, self.attack_knack)
            vps += 1
        return vps
