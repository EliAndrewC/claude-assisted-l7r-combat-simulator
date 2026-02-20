from l7r.combatant import Combatant


class ShinjoBushi(Combatant):
    """Shinjo Bushi school (Unicorn clan). A patient defensive school.

    Strategy: Wait and accumulate timing bonuses, then strike decisively
    in phase 10 when bonuses are maximized. Always pre-declares parries
    (getting the +5 bonus) and gains speed from successful parries.

    Special ability: Always has predeclare_bonus=5 (built into class),
    meaning parries always get the +5 free raise without explicitly
    committing.
    School ring: Earth.
    School knacks: double attack, iaijutsu, lunge.

    Key techniques:
    - R1T: Extra rolled die on double attack, parry, wound check.
    - R2T: Free raise (+5) on parry.
    - R3T: After successful parry, all action dice move earlier by
      (attack skill) phases. Parrying makes us faster.
    - R4T: Replace highest action die with 1 (guaranteed phase 1 action).
    - R5T: Convert parry roll excess into disc wound check bonuses.

    The choose_action override accumulates a timing bonus (2 * phases
    waited since first action) that applies to parry, attack, and double
    attack. Only attacks in phase 10 to maximize this bonus.
    """

    school_knacks = ["double_attack", "iaijutsu", "lunge"]
    r1t_rolls = ["double_attack", "parry", "wound_check"]
    r2t_rolls = "parry"
    # Always pre-declares parries — the +5 bonus is baked into the school.
    predeclare_bonus = 5

    def __init__(self, **kwargs):
        Combatant.__init__(self, **kwargs)

        self.events["successful_parry"].append(self.r3t_trigger)
        self.events["successful_parry"].append(self.r5t_trigger)

    def r3t_trigger(self):
        """R3T: After a successful parry, move all action dice earlier
        by (attack skill) phases. Repeated parrying makes us progressively
        faster, potentially enabling multiple actions per phase."""
        if self.rank >= 3:
            for i in range(len(self.actions)):
                self.actions[i] -= self.attack

    def r5t_trigger(self):
        """R5T: Convert the excess from a successful parry into a disc
        bonus for wound checks. The better we parry, the more resilient
        we become against hits that do get through."""
        exceeded = max(0, self.parry_roll - self.enemy.attack_roll)
        if exceeded and self.rank == 5:
            self.disc["wound_check"].append(exceeded)

    @property
    def wc_threshold(self):
        """Keep light wounds up to our max wound check bonus, since we can
        reliably make those checks. This lets us absorb more damage before
        voluntarily taking a serious wound."""
        return max(self.base_wc_threshold, self.max_bonus("wound_check"))

    def initiative(self):
        """R4T: After normal initiative, replace the highest (worst) action
        die with 1, guaranteeing an action in phase 1. This combines with
        the school's patience strategy — parry early, attack late."""
        Combatant.initiative(self)
        if self.rank >= 4:
            self.actions.insert(0, 1)
            highest = self.actions.pop()
            self.init_order = self.actions[:]
            self.log(f"R4T sets highest action die ({highest}) to 1")

    def choose_action(self):
        """Accumulate a timing bonus (2 * phases waited) that applies to
        parry, attack, and double attack. Only actually attacks in phase 10
        to maximize this bonus — the school's entire strategy is patience."""
        if self.actions:
            self.auto_once["parry"] = self.auto_once["attack"] = self.auto_once[
                "double_attack"
            ] = 2 * (self.phase - self.actions[0])
        if self.phase == 10:
            return super().choose_action()

    def will_predeclare(self):
        """Pre-declare a parry whenever we have at least 2 actions
        remaining. Since predeclare_bonus is always 5, this stacks with
        the class-level bonus for very strong parry rolls."""
        return len(self.actions) > 1
