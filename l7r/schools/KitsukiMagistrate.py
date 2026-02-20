from l7r.combatant import Combatant


class KitsukiMagistrate(Combatant):
    school_knacks = ['discern_honor', 'iaijutsu', 'presence']
    r1t_rolls = ['interrogation', 'parry', 'wound_check']
    r2t_rolls = 'interrogation'

    def __init__(self, **kwargs):
        Combatant.__init__(self, **kwargs)

        self.events['pre_combat'].append(self.r5t_trigger)

        if self.rank >= 3:
            raises = [5] * self.attack
            for roll_type in ['attack', 'wound_check']:
                self.multi[roll_type].append(raises)

    def whammy(self, enemy):
        enemy.air -= 1
        enemy.fire -= 1
        enemy.water -= 1
        enemy.events['death'].append(self.whammy_reset)

    def whammy_reset(self):
        for enemy in self.targeted:
            enemy.air += 1
            enemy.fire += 1
            enemy.water += 1
            enemy.events['death'].remove(self.whammy_reset)

        self.r5t_trigger()

    def r5t_trigger(self):
        if self.rank == 5:
            xp = self.xp
            targets = sorted(self.attackable, key=lambda c: c.xp)
            self.targeted = []

            while not self.targeted or targets and xp >= targets[-1].xp:
                enemy = targets.pop()
                self.whammy(enemy)
                xp -= enemy.xp
                self.targeted.append(enemy)

    @property
    def parry_dice(self):
        roll, keep = self.extra_dice['parry']
        roll += self.water + self.parry
        keep += self.water
        return roll, keep
