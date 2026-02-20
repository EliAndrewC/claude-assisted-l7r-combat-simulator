from l7r.combatant import Combatant


class KitsukiMagistrate(Combatant):
    """Kitsuki Magistrate school (Dragon clan). An investigator/debuffer.

    Strategy: Not primarily a combat school — excels at weakening enemies
    before and during combat through ring reduction. Uses Water for parrying
    instead of Air (unique among schools).

    School ring: Water.
    School knacks: discern honor, iaijutsu, presence.

    Key techniques:
    - R1T: Extra rolled die on interrogation, parry, wound check.
    - R2T: Free raise (+5) on interrogation.
    - R3T: Gains (attack) free raises as shared disc bonuses on attack
      and wound check rolls.
    - R5T: "Whammy" — reduce all attackable enemies' Air, Fire, and Water
      by 1 each (devastating combat debuff). Redistributes on enemy death.

    Unique: parry_dice uses Water instead of Air, reflecting the school's
    emphasis on perception over reflexes.
    """

    school_knacks = ["discern_honor", "iaijutsu", "presence"]
    r1t_rolls = ["interrogation", "parry", "wound_check"]
    r2t_rolls = "interrogation"

    def __init__(self, **kwargs):
        Combatant.__init__(self, **kwargs)

        self.events["pre_combat"].append(self.r5t_trigger)

        if self.rank >= 3:
            raises = [5] * self.attack
            for roll_type in ["attack", "wound_check"]:
                self.multi[roll_type].append(raises)

    def whammy(self, enemy):
        """Apply the R5T debuff: reduce an enemy's combat rings by 1 each.
        This weakens their attacks (Fire), parries (Air), and wound checks
        (Water) simultaneously. Registers a death handler to undo it."""
        enemy.air -= 1
        enemy.fire -= 1
        enemy.water -= 1
        enemy.events["death"].append(self.whammy_reset)

    def whammy_reset(self):
        """Undo all whammies (restore rings) and re-apply to new targets.
        Called when a whammied enemy dies, freeing up budget to debuff others."""
        for enemy in self.targeted:
            enemy.air += 1
            enemy.fire += 1
            enemy.water += 1
            enemy.events["death"].remove(self.whammy_reset)

        self.r5t_trigger()

    def r5t_trigger(self):
        """R5T: Distribute whammies across enemies, spending XP budget.
        Targets lowest-XP enemies first (easier to debuff), continuing
        until we run out of budget."""
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
        """Uses Water + parry skill instead of Air + parry skill for
        parrying, reflecting the school's perceptive fighting style."""
        roll, keep = self.extra_dice["parry"]
        roll += self.water + self.parry
        keep += self.water
        return roll, keep
