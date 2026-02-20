from l7r.combatant import Combatant


class IsawaDuelist(Combatant):
    school_knacks = ['double_attack', 'iaijutsu', 'lunge']
    r1t_rolls = ['double_attack', 'lunge', 'wound_check']
    r2t_rolls = 'wound_check'

    def __init__(self, **kwargs):
        Combatant.__init__(self, **kwargs)

        self.events['wound_check'].append(self.r5t_trigger)

    def r5t_trigger(self, check, light, light_total):
        exceeded = max(0, check - light_total)
        if exceeded and self.rank == 5:
            self.disc['wound_check'].extend([1] * exceeded)

    @property
    def damage_dice(self):
        roll, keep = super(MatsuBushi, self).damage_dice
        return roll - self.fire + self.water, keep

    def max_bonus(self, roll_type):
        bonus = Combatant.max_bonus(self, roll_type)
        if roll_type in ['attack', 'double_attack', 'lunge']:
            bonus += 3 * self.attack
        return bonus

    def disc_bonus(self, roll_type, needed):
        bonus = Combatant.disc_bonus(self, roll_type, needed)
        if self.rank >= 3 and bonus < needed and bonus + 3 * self.attack >= needed and roll_type in ['attack', 'double_attack', 'lunge']:
            self.tn -= 5
            self.events['post_defense'].append(self.reset_tn)
            bonus += 3 * self.attack
        return bonus

    def choose_action(self):
        if self.actions == self.init_order:
            self.actions.pop()
            return 'lunge', self.att_target()

        # TODO: when else do we want to lunge?
