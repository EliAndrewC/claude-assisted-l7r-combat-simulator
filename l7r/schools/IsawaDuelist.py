from l7r.combatant import Combatant


class IsawaDuelist(Combatant):
    """Isawa Duelist school (Phoenix clan). A Water-based damage dealer.

    Strategy: Open with a lunge on the first action, then look for further
    lunge opportunities. Uses Water instead of Fire for damage dice, which
    synergizes with the Phoenix's typically high Water ring.

    School ring: Water.
    School knacks: double attack, iaijutsu, lunge.

    Key techniques:
    - R1T: Extra rolled die on double attack, lunge, wound check.
    - R2T: Free raise (+5) on wound checks.
    - R3T: Can lower own TN by 5 to gain +3*attack bonus on attack rolls.
    - R5T: Convert wound check excess into disc bonuses for future checks.

    Damage dice use Water ring instead of Fire, making this school uniquely
    effective for characters who invest heavily in Water.
    """

    school_knacks = ["double_attack", "iaijutsu", "lunge"]
    r1t_rolls = ["double_attack", "lunge", "wound_check"]
    r2t_rolls = "wound_check"

    def __init__(self, **kwargs):
        Combatant.__init__(self, **kwargs)

        self.events["wound_check"].append(self.r5t_trigger)

    def r5t_trigger(self, check, light, light_total):
        """R5T: Convert wound check excess into discretionary +1 bonuses
        for future wound checks. The better you shrug off damage, the
        more resilient you become."""
        exceeded = max(0, check - light_total)
        if exceeded and self.rank == 5:
            self.disc["wound_check"].extend([1] * exceeded)

    @property
    def damage_dice(self):
        """Use Water ring instead of Fire for damage rolled dice. Swaps
        Fire out of the base calculation and substitutes Water."""
        roll, keep = super(IsawaDuelist, self).damage_dice
        return roll - self.fire + self.water, keep

    def max_bonus(self, roll_type):
        bonus = Combatant.max_bonus(self, roll_type)
        if roll_type in ["attack", "double_attack", "lunge"]:
            bonus += 3 * self.attack
        return bonus

    def disc_bonus(self, roll_type, needed):
        """R3T: If normal disc bonuses aren't enough but adding 3*attack
        would reach the target, lower own TN by 5 (making us easier to
        hit) in exchange for the attack bonus. A risky tradeoff."""
        bonus = Combatant.disc_bonus(self, roll_type, needed)
        if (
            self.rank >= 3
            and bonus < needed
            and bonus + 3 * self.attack >= needed
            and roll_type in ["attack", "double_attack", "lunge"]
        ):
            self.tn -= 5
            self.events["post_defense"].append(self.reset_tn)
            bonus += 3 * self.attack
        return bonus

    def choose_action(self):
        """Always lunge on the first action of the round, then fall back
        to base logic (partially implemented — TODO for other cases)."""
        if self.actions == self.init_order:
            self.actions.pop()
            return "lunge", self.att_target()

        # TODO: when else do we want to lunge?
