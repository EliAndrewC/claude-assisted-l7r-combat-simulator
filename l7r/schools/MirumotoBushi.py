from l7r.combatant import Combatant


class MirumotoBushi(Combatant):
    school_knacks = ['double_attack', 'iaijutsu', 'lunge']
    r1t_rolls = ['attack', 'double_attack', 'parry']
    r2t_rolls = 'parry'

    def __init__(self, **kwargs):
        Combatant.__init__(self, **kwargs)

        self.events['successful_parry'].append(self.sa_trigger)
        self.events['pre_round'].append(self.r3t_trigger)

        if self.rank == 5:
            self.vps *= 2

    def sa_trigger(self):
        self.vps += (2 if self.rank == 5 else 1)

    def r3t_trigger(self):
        if self.rank >= 3:
            self.points = [2] * self.attack
            if self.rank >= 4:
                for knack in ['attack', 'double_attack', 'lunge', 'parry']:
                    self.multi[knack].append(self.points)

    @property
    def spendable_vps(self):
        return range(0, self.vps + 1, 2)

    def choose_action(self):
        pass

    def will_predeclare(self):
        pass

    def will_parry(self):
        pass
