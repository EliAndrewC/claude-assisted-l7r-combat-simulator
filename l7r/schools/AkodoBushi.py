from math import ceil

from l7r.combatant import Combatant


class AkodoBushi(Combatant):
    hold_one_action = False
    base_wc_threshold = 25

    school_knacks = ['double_attack', 'feint', 'iaijutsu']
    r1t_rolls = ['double_attack', 'feint', 'wound_check']
    r2t_rolls = 'wound_check'

    def __init__(self, **kwargs):
        Combatant.__init__(self, **kwargs)
        self.events['successful_attack'].append(self.sa_trigger)
        self.events['wound_check'].append(self.r3t_trigger)
        self.events['wound_check'].append(self.r5t_trigger)

    def sa_trigger(self):
        if self.attack_knack == 'feint':
            self.vps += 4

    def r3t_trigger(self, check, light, total):
        exceeded = max(0, check - light)
        if exceeded and self.rank >= 3:
            disc = [self.attack * (exceeded // 5)]
            for knack in ['attack', 'double_attack', 'feint']:
                self.multi[knack].append(disc)

    def r5t_trigger(self, check, light, total):
        if self.rank == 5:
            damage = 0
            while light >= 10 and self.vps > 2:
                light -= 10
                damage += 10
                self.vps -= 1
            if damage:
                self.log('spends {} vps to deal {} light wounds'.format(int(ceil(damage / 10)), damage))
                self.enemy.wound_check(damage)

    def choose_action(self):
        if self.actions and self.actions[0] <= self.phase:
            if self.vps < 4:
                self.actions.pop(0)
                return 'feint', self.att_target()

            if self.disc_bonuses('attack'):
                return Combatant.choose_action(self)

    def disc_bonus(self, roll_type, needed):
        bonus = Combatant.disc_bonus(self, roll_type, needed)
        remaining = self.disc_bonuses(roll_type)
        if len(remaining) > 1 and sum(remaining) >= 30 and roll_type in ['attack', 'double_attack']:
            bonus += Combatant.disc_bonus(self, roll_type, sum(remaining) / 2)
        return bonus

    def need_higher_wc(self, light, check):
        if self.serious + 1 == self.sw_to_kill:
            needed = max(0, light - check)
        else:
            needed = max(0, light - check - 9)

        return needed < self.max_bonus('wound_check')

    def wc_bonus(self, light, check):
        if self.rank >= 4:
            while self.need_higher_wc(light, check):
                mb = self.max_bonus('wound_check')
                needed = 1
                if self.calc_serious(light, check + mb) == self.calc_serious(light, check + mb + 5):
                    needed = 2

                if self.vps >= needed:
                    self.vps -= needed
                    self.auto_once['wound_check'] += 5 * needed
                else:
                    break

        return Combatant.wc_bonus(self, light, check)
