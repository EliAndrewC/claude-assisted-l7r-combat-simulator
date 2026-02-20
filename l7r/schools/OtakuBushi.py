from l7r.combatant import Combatant


class OtakuBushi(Combatant):
    school_knacks = ['double_attack', 'iaijutsu', 'lunge']
    r1t_rolls = ['iaijutsu', 'lunge', 'wound_check']
    r2t_rolls = 'wound_check'

    def __init__(self, **kwargs):
        Combatant.__init__(self, **kwargs)

        self.events['post_defense'].append(self.sa_trigger)
        self.events['pre_attack'].append(self.r3t_pre_trigger)
        self.events['post_attack'].append(self.r3t_post_trigger)
        self.events['successful_attack'].append(self.r4t_succ_trigger)
        self.events['post_attack'].append(self.r4t_post_trigger)

    def r3t_pre_trigger(self):
        self.prev_wounds = (defender.light, defender.serious)

    def r3t_post_trigger(self):
        prev_light, prev_serious = self.prev_wounds
        if self.rank >= 3 and (self.enemy.light > prev_light or self.enemy.serious > prev_serious):
            diff = max(1, self.fire - self.enemy.fire)
            for i in range(len(self.enemy.actions)):
                self.enemy.actions[i] += diff

    def r4t_succ_trigger(self):
        if self.rank >= 4 and self.attack_knack == 'lunge':
            self.auto_once['damage_rolled'] -= 1
            self.base_damage_rolled += 1

    def r4t_post_trigger(self):
        self.base_damage_rolled = self.__class__.base_damage_rolled

    def sa_trigger(self):
        if self.actions:
            self.actions.pop()
            self.engine.attack('lunge', self, attacker)

    def next_damage(self, tn, extra_damage):
        roll, keep, serious = Combatant.next_damage(self, tn, extra_damage)
        if rank == 5 and self.attack_knack in ['attack', 'lunge']:
            serious += 1
            roll = max(2, roll - 10)
        return roll, keep, serious

    def choose_action(self):
        pass
