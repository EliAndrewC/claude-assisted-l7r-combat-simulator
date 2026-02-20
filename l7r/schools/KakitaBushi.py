from l7r.combatant import Combatant


class KakitaBushi(Combatant):
    hold_one_action = False
    school_knacks = ['double_attack', 'iaijutsu', 'lunge']
    r1t_rolls = ['attack', 'double_attack', 'iaijutsu']
    r2t_rolls = 'iaijutsu'

    def __init__(self, **kwargs):
        Combatant.__init__(self, **kwargs)

        self.events['successful_attack'].append(self.r4t_trigger)
        self.events['pre_round'].append(self.r5t_trigger)

    def r4t_trigger(self, enemy):
        if self.rank >= 4 and self.attack_knack == 'iaijutsu':
            self.auto_once['damage'] += 5

    def r5t_trigger(self):
        if self.rank == 5:
            target = self.att_target()
            knack = 'iaijutsu' if target.iaijutsu else 'attack'
            bonus = 5 + 5 * (self.iaijutsu - getattr(enemy, knack)) + (0 if target.iaijutsu else 5)
            roll, keep = self.att_dice('iaijutsu')
            our_total = self.xky(roll, keep, not self.crippled, 'iaijutsu') + bonus

            roll, keep = enemy.att_dice(knack)
            enemy_total = enemy.xky(roll, keep) + enemy.always[knack]

            roll, keep = self.damage_dice
            roll += (our_total - enemy_total) // 5
            damage = self.xky(roll, keep, True, 'damage') + 5
            enemy.wound_check(damage)

    def initiative(self):
        roll, keep = self.init_dice
        dice = [d10(False) for i in range(roll)]
        self.actions = [(0 if die == 10 else die) for die in dice][:keep]
        self.init_order = self.actions[:]
        self.log(f'initiative: {self.actions}', indent=0)

    def r3t_bonus(self):
        next = self.enemy.actions[0] if self.enemy.actions else 11
        if self.phase < next:
            bonus += self.attack * (self.phase - next)
        return bonus

    def max_bonus(self, roll_type):
        return Combatant.max_bonus(self, roll_type) + self.r3t_bonus()

    def disc_bonus(self, roll_type, needed):
        bonus = self.r3t_bonus()
        return bonus + Combatant.disc_bonus(roll_type, needed - bonus)

    def choose_action(self):
        pass  # TODO
