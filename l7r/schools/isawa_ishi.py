from __future__ import annotations

from l7r.combatant import Combatant
from l7r.types import RollType


class IsawaIshi(Combatant):
    """Isawa Ishi school (Phoenix clan). A Void-based support school.

    Strategy: VP-rich support character. Starts with more VPs than any
    other school (highest ring + rank), but is limited in how many VPs
    can be spent per roll. At higher ranks, prevents enemies from
    spending VPs and can negate enemy school abilities entirely.

    Special ability: Max VPs = highest ring + rank (instead of lowest
    ring). Can't spend more than lowest_ring - 1 VPs per roll.
    School ring: Void.
    School knacks: absorb void, kharmic spin, otherworldliness (non-combat).

    Key techniques:
    - R1T: Extra rolled die on attack, damage, wound check.
    - R2T: Free raise (+5) on attack.
    - R3T: Support ability — spend 1 VP to add precepts dice to ally's
      roll. No-op in 1v1 combat.
    - R4T: +1 Void (free). Opposing characters can't spend VPs when
      attacking this character.
    - R5T: Negate enemy school abilities for a fight (costs 2*rank VPs).
    """

    school_knacks: list[RollType] = ["absorb_void", "kharmic_spin", "otherworldliness"]
    r1t_rolls: list[RollType] = ["attack", "damage", "wound_check"]
    r2t_rolls: RollType = "attack"

    school_ring = "void"
    r4t_ring_boost = "void"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        # SA: Max VPs = highest ring + rank (override base calculation)
        highest = max(self.air, self.earth, self.fire, self.water, self.void)
        self.vps = highest + self.rank

        if self.rank >= 4:
            self.events["pre_defense"].append(self.r4t_trigger)

        if self.rank >= 5:
            self.events["pre_combat"].append(self.r5t_trigger)

    @property
    def spendable_vps(self) -> range:
        """SA: Can't spend more than (lowest ring - 1) VPs per roll.
        This limits burst power but the larger VP pool provides
        sustained efficiency over many rolls."""
        lowest = min(self.air, self.earth, self.fire, self.water, self.void)
        limit = max(0, lowest - 1)
        return range(min(self.vps, limit) + 1)

    def r4t_trigger(self) -> None:
        """R4T: When defending, temporarily zero the enemy's VPs so
        they can't spend VPs on the attack roll against us."""
        if hasattr(self, "enemy") and self.enemy:
            self._saved_enemy_vps = self.enemy.vps
            self.enemy.vps = 0

            def restore() -> bool:
                self.enemy.vps = self._saved_enemy_vps
                return True

            self.events["post_defense"].append(restore)

    def r5t_trigger(self) -> None:
        """R5T: Negate enemy school abilities for the fight. Costs
        2*rank VPs. Removes R1T extra dice, R2T free raise, and sets
        the enemy's rank to 0 (disabling rank-gated techniques)."""
        cost = 2 * self.rank
        if self.vps >= cost:
            self.vps -= cost
            for enemy in self.attackable:
                for roll_type in enemy.r1t_rolls:
                    enemy.extra_dice[roll_type][0] = max(
                        0, enemy.extra_dice[roll_type][0] - 1
                    )
                if enemy.r2t_rolls:
                    enemy.always[enemy.r2t_rolls] = max(
                        0, enemy.always[enemy.r2t_rolls] - 5
                    )
                enemy.rank = 0
