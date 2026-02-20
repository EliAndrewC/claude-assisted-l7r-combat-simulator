from l7r.combatant import log


class Engine:
    def __init__(self, formation):
        self.formation = formation
        self.combatants = formation.combatants

    @property
    def finished(self):
        return self.formation.one_side_finished

    def fight(self):
        for c in self.combatants:
            c.engine = self
            c.triggers('pre_fight')

        while not self.finished:
            self.round()

    def parry(self, defender, attacker):
        if defender.will_parry():
            return defender.make_parry(), True

        for def_ally in defender.adjacent:
            if def_ally.will_parry_for(defender, attacker):
                return def_ally.make_parry_for(defender, attacker), True

        return False, False

    def attack(self, knack, attacker, defender):
        log(f'Phase #{self.phase}: {attacker.name} {knack} vs {defender.name}')

        if defender.will_counterattack(attacker):
            self.attack('counterattack', defender, attacker)
        elif knack != 'counterattack':
            attacker.tn += 5 * attacker.parry
            for def_ally in attacker.attackable:
                if not attacker.dead and def_ally.will_counterattack_for(defender, attacker):
                    self.attack('counterattack', enemy, attacker)
            attacker.tn -= 5 * attacker.parry

        if attacker.dead:
            return

        attacker.attack_knack = knack
        defender.enemy = attacker
        attacker.enemy = defender
        attacker.triggers('pre_attack')
        defender.triggers('pre_defense')

        if not defender.will_predeclare():
            for def_ally in set(defender.adjacent).union(def_ally.attackable):
                if def_ally.will_predeclare_for(defender, attacker):
                    break

        if attacker.make_attack():
            succeeded, attempted = self.parry(defender, attacker)
            if not succeeded:
                light, serious = attacker.deal_damage(defender.tn, extra_damage=not attempted)
                defender.wound_check(light, serious)
        else:
            for d in [defender] + defender.adjacent:
                if d.predeclare_bonus:
                    d.make_parry()
                    d.triggers('successful_parry')

        attacker.triggers('post_attack')
        if not defender.dead:
            defender.triggers('post_defense')

    def round(self):
        for c in self.combatants:
            c.triggers('pre_round')
            c.initiative()
        self.combatants.sort(key=lambda c: c.init_order)

        for phase in range(11):
            self.phase = phase
            for c in self.combatants:
                c.phase = phase

            action_taken = True
            while action_taken:
                action_taken = False
                for attacker in self.combatants:
                    if not attacker.dead:
                        action = attacker.choose_action()
                        if action:
                            action_taken = True
                            knack, defender = action
                            self.attack(knack, attacker, defender)
                            for combatant in [attacker, defender]:
                                if combatant.dead:
                                    combatant.triggers('death')
                                    self.formation.death(combatant)
                            if self.finished:
                                return

            self.combatants = [c for c in self.combatants if not c.dead]

        for c in self.combatants:
            c.triggers('post_round')


if __name__ == '__main__':
    import random
    from l7r.combatant import Combatant
    from l7r.formations import Surround
    from l7r.schools import BayushiBushi
    mook = Combatant(
        air=5, earth=5, fire=5, water=5, void=5,
        attack=4, parry=5,
        base_damage_rolled=3
    )
    bushi = BayushiBushi(air=3, earth=5, fire=6, water=5, void=5, attack=4, parry=5, rank=5)
    formation = Surround([mook], [bushi])
    engine = Engine(formation)
    engine.fight()
    print(f'mook ends the combat with {mook.serious} serious wounds compared to the bushi with {bushi.serious}')
