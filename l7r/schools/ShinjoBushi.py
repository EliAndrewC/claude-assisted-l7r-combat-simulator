from l7r.combatant import Combatant


class ShinjoBushi(Combatant):
    school_knacks = ['double_attack', 'iaijutsu', 'lunge']
    r1t_rolls = ['double_attack', 'parry', 'wound_check']
    r2t_rolls = 'parry'
    predeclare_bonus = 5

    def __init__(self, **kwargs):
        Combatant.__init__(self, **kwargs)

        self.events['successful_parry'].append(self.r3t_trigger)
        self.events['successful_parry'].append(self.r5t_trigger)

    def r3t_trigger(self):
        if self.rank >= 3:
            for i in range(len(self.actions)):
                self.actions[i] -= self.attack

    def r5t_trigger(self):
        exceeded = max(0, self.parry_roll - self.enemy.attack_roll)
        if exceeded and self.rank == 5:
            self.disc['wound_check'].append(exceeded)

    @property
    def wc_threshold(self):
        return max(self.base_wc_threshold, self.max_bonus('wound_check'))

    def initiative(self):
        Combatant.initiative(self)
        if self.rank >= 4:
            self.actions.insert(0, 1)
            highest = self.actions.pop()
            self.init_order = self.actions[:]
            self.log(f'R4T sets highest action die ({highest}) to 1')

    def choose_action(self):
        if self.actions:
            self.auto_once['parry'] = self.auto_once['attack'] = self.auto_once['double_attack'] = 2 * (self.phase - self.actions[0])
        if self.phase == 10:
            return super().choose_action()

    def will_predeclare(self):
        return len(self.actions) > 1
