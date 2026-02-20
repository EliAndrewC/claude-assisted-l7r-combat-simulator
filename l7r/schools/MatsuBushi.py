from l7r.dice import prob
from l7r.combatant import Combatant


class MatsuBushi(Combatant):
    hold_one_action = False
    school_knacks = ['double_attack', 'iaijutsu', 'lunge']
    r1t_rolls = ['double_attack', 'iaijutsu', 'wound_check']
    r2t_rolls = 'iaijutsu'

    def __init__(self, **kwargs):
        Combatant.__init__(self, **kwargs)

        self.extra_dice['initiative'] = (10 - self.void - 1, 0)

        self.events['vps_spent'].append(self.r3t_trigger)
        self.events['pre_attack'].append(self.r5t_pre)
        self.events['post_attack'].append(self.r5t_post)

        if self.rank >= 4:
            self.vp_fail_threshold -= 0.15
            self.datt_threshold = 0.33

    def r3t_trigger(self, vps, roll_type):
        if self.rank >= 3:
            for i in range(vps):
                self.disc['wound_check'].append(3 * self.attack)

    def r5t_pre(self):
        if self.rank == 5:
            self.pre_sw = self.enemy.serious
            self.enemy.base_wc_threshold += 10

    def r5t_post(self):
        if self.rank == 5 and self.enemy.light == 0 and self.enemy.serious > self.pre_sw and not self.enemy.dead:
            self.log(f'sets {self.enemy.name} back to 10 light wounds instead of 0')
            self.enemy.light = 10
            self.enemy.base_wc_threshold -= 10

    def att_prob(self, knack, tn):
        roll, keep = self.att_dice(knack)
        if knack == 'double_attack' and self.vps:
            roll, keep = roll + 1, keep + 1
        return prob[not self.crippled][roll, keep, tn - self.max_bonus(knack)]

    def make_attack(self):
        success = Combatant.make_attack(self)
        if self.rank >= 4 and self.attack_knack == 'double_attack' and not success:
            if self.attack_roll >= self.enemy.tn - 20:
                self.log('R4T turns this miss into a hit with no extra damage')
                self.attack_roll = 0
                success = True
        return success
