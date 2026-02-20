from l7r.combatant import Combatant


class OtakuBushi(Combatant):
    """Otaku Bushi school (Unicorn clan). An aggressive mounted school.

    Strategy: Relentless offense — automatically counterattacks after
    being attacked (spending an action to lunge the attacker), delays
    enemy actions by dealing wounds, and converts lunge damage dice
    to kept dice at higher ranks.

    Special ability: After being attacked (post-defense), spend an action
    to immediately lunge the attacker.
    School ring: Fire.
    School knacks: double attack, iaijutsu, lunge.

    Key techniques:
    - R1T: Extra rolled die on iaijutsu, lunge, wound check.
    - R2T: Free raise (+5) on wound checks.
    - R3T: When dealing wounds, delay enemy actions by (Fire - enemy Fire)
      phases. Punishes low-Fire enemies and disrupts their action economy.
    - R4T: Lunge damage dice trade rolled for kept (fewer dice but all
      count), making lunge damage more consistent.
    - R5T: All attacks and lunges deal +1 automatic serious wound but
      roll 10 fewer damage dice. Trades raw damage for guaranteed lethality.
    """

    school_knacks = ["double_attack", "iaijutsu", "lunge"]
    r1t_rolls = ["iaijutsu", "lunge", "wound_check"]
    r2t_rolls = "wound_check"

    def __init__(self, **kwargs):
        Combatant.__init__(self, **kwargs)

        self.events["post_defense"].append(self.sa_trigger)
        self.events["pre_attack"].append(self.r3t_pre_trigger)
        self.events["post_attack"].append(self.r3t_post_trigger)
        self.events["successful_attack"].append(self.r4t_succ_trigger)
        self.events["post_attack"].append(self.r4t_post_trigger)

    def r3t_pre_trigger(self):
        """R3T setup: snapshot the enemy's current wounds before our attack
        so we can detect if we dealt new wounds in r3t_post_trigger."""
        self.prev_wounds = (self.enemy.light, self.enemy.serious)

    def r3t_post_trigger(self):
        """R3T payoff: if we dealt any wounds, push all the enemy's
        remaining action dice later by (our Fire - their Fire). This
        can delay or even prevent their future actions this round."""
        prev_light, prev_serious = self.prev_wounds
        if self.rank >= 3 and (
            self.enemy.light > prev_light or self.enemy.serious > prev_serious
        ):
            diff = max(1, self.fire - self.enemy.fire)
            for i in range(len(self.enemy.actions)):
                self.enemy.actions[i] += diff

    def r4t_succ_trigger(self):
        """R4T: On a successful lunge, convert 1 rolled damage die to 1
        kept die. Fewer total dice but all are kept, making lunge damage
        much more consistent."""
        if self.rank >= 4 and self.attack_knack == "lunge":
            self.auto_once["damage_rolled"] -= 1
            self.base_damage_rolled += 1

    def r4t_post_trigger(self):
        """Reset base_damage_rolled to class default after the attack,
        undoing the R4T modification."""
        self.base_damage_rolled = self.__class__.base_damage_rolled

    def sa_trigger(self):
        """Special ability: after being attacked, immediately spend an
        action to counterattack with a lunge. Reflects the mounted
        warrior's aggressive response to any threat."""
        if self.actions:
            self.actions.pop()
            self.engine.attack("lunge", self, self.enemy)

    def next_damage(self, tn, extra_damage):
        """R5T: Attacks and lunges automatically deal +1 serious wound
        but roll 10 fewer damage dice. Trades raw damage for guaranteed
        lethality — even a weak hit is devastating."""
        roll, keep, serious = Combatant.next_damage(self, tn, extra_damage)
        if self.rank == 5 and self.attack_knack in ["attack", "lunge"]:
            serious += 1
            roll = max(2, roll - 10)
        return roll, keep, serious

    def choose_action(self):
        pass
