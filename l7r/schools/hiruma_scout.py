from __future__ import annotations

from l7r.combatant import Combatant
from l7r.types import RollType


class HirumaScout(Combatant):
    """Hiruma Scout school (Crab clan). An Air-based parry school.

    Strategy: Parry-focused defender that accumulates attack bonuses
    from parrying and debuffs enemy damage at higher ranks. Adjacent
    allies get +5 TN from the scout's presence.

    Special ability: Adjacent allies get +5 TN (handled by formation/engine).
    School ring: Air.
    School knacks: double attack, feint, iaijutsu.

    Key techniques:
    - R1T: Extra rolled die on initiative, parry, wound check.
    - R2T: Free raise (+5) on parry.
    - R3T: After any parry attempt, add 2*attack to next attack and damage.
    - R4T: +1 Air (free). Lower all action dice by 2 (min 1) on initiative.
    - R5T: After any parry attempt, attacker deals 10 fewer light wounds
      on their next 2 damage rolls.
    """

    school_knacks: list[RollType] = ["double_attack", "feint", "iaijutsu"]
    r1t_rolls: list[RollType] = ["initiative", "parry", "wound_check"]
    r2t_rolls: RollType = "parry"

    school_ring = "air"
    r4t_ring_boost = "air"

    def make_parry(self, auto_success: bool = False) -> bool:
        """Execute a parry with R3T attack bonus and R5T damage debuff.

        R3T: After any parry attempt (hit or miss), gain +2*attack on
        the next attack roll and damage roll.
        R5T: After any parry attempt, the attacker deals 10 fewer light
        wounds on their next 2 damage rolls.
        """
        success = super().make_parry(auto_success)

        if self.rank >= 3:
            bonus = 2 * self.attack
            self.auto_once["attack"] += bonus
            self.auto_once["damage"] += bonus

        if self.rank >= 5 and hasattr(self, "enemy") and self.enemy:
            enemy = self.enemy
            remaining = [2]

            def reduce_damage() -> bool:
                enemy.auto_once["damage"] -= 10
                remaining[0] -= 1
                return remaining[0] <= 0

            enemy.events["pre_attack"].append(reduce_damage)

        return success

    def initiative(self) -> None:
        """R4T: After normal initiative, lower all action dice by 2
        (minimum 1). Scouts act earlier, giving them first parry
        opportunities and early counterplay."""
        Combatant.initiative(self)
        if self.rank >= 4:
            self.actions = [max(1, a - 2) for a in self.actions]
            self.init_order = self.actions[:]
            self.log("R4T lowers all action dice by 2")

    def will_predeclare(self) -> bool:
        """Pre-declare parries when we have actions to spare, since
        parrying fuels our R3T attack bonuses."""
        if len(self.actions) > 2:
            self.predeclare_bonus = 5
            return True
        self.predeclare_bonus = 0
        return False
