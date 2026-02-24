from __future__ import annotations

from l7r.combatant import Combatant
from l7r.types import RollType


class IkomaBard(Combatant):
    """Ikoma Bard school (Lion clan). Forced parry and damage floor.

    Strategy: Fire-based aggressive attacker. Forces enemies to waste
    actions on parrying, then deals consistent high damage. At high
    rank, ensures a minimum damage floor on unparried hits. Feints
    against hard-to-hit enemies to lower their TN for follow-up.

    Special ability: Once per round, set enemy.forced_parry = True
    before attacking, forcing them to use an action to parry.
    On successful feint, lower target's TN by 10 for the next
    attack against them.
    School ring: Fire.
    School knacks: discern honor, oppose knowledge, oppose social.

    Key techniques:
    - R1T: Extra rolled die on attack, wound check.
    - R2T: Free raise (+5) on attack.
    - R3T: 10 shared free raises on attack + wound check.
    - R4T: +1 Fire (free). Damage floor: if attack is unparried and
      no extra kept dice, rolled dice = max(10, rolled).
    - R5T: Extra SA use per round (allow 2 uses instead of 1).
    """

    school_knacks: list[RollType] = ["discern_honor", "oppose_knowledge", "oppose_social"]
    r1t_rolls: list[RollType] = ["attack", "wound_check"]
    r2t_rolls: RollType = "attack"
    school_ring = "fire"
    r4t_ring_boost = "fire"

    feint_threshold: float = 0.5
    """If attack hit probability is below this, feint instead to lower
    the target's TN by 10 for the next attack."""

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        self.sa_used_this_round = 0
        self.events["pre_round"].append(self.sa_reset)
        self.events["successful_attack"].append(self.sa_feint_trigger)

        if self.rank >= 3:
            raises = [5] * 10
            for roll_type in ["attack", "wound_check"]:
                self.multi[roll_type].append(raises)

    @property
    def sa_max_uses(self) -> int:
        """Maximum SA uses per round. R5T allows 2."""
        return 2 if self.rank >= 5 else 1

    def sa_reset(self) -> None:
        """Reset SA usage counter at start of round."""
        self.sa_used_this_round = 0

    def sa_feint_trigger(self) -> None:
        """SA: After successful feint, lower target's TN by 10."""
        if self.attack_knack == "feint" and hasattr(self, 'enemy') and self.enemy:
            enemy = self.enemy
            enemy.tn -= 10

            def restore() -> bool:
                enemy.tn += 10
                return True

            enemy.events["post_defense"].append(restore)

    def choose_action(self) -> tuple[RollType, Combatant] | None:
        """Choose attack knack, feinting if hit probability is too low.

        If the probability of hitting with a normal attack is below
        feint_threshold, feint instead to lower the target's TN by 10
        for the follow-up attack. Forced parry SA is only applied on
        real attacks, not feints.
        """
        action = super().choose_action()
        if action:
            knack, target = action

            # Feint if attack probability is too low
            if knack in ("attack", "double_attack"):  # bards don't innately have double attack but can purchase it separately
                if self.att_prob(knack, target.tn) < self.feint_threshold:
                    return ("feint", target)

            # SA: forced parry (on real attacks, not feints)
            if self.sa_used_this_round < self.sa_max_uses:
                target.forced_parry = True
                self.sa_used_this_round += 1
        return action

    def next_damage(self, tn: int, extra_damage: bool) -> tuple[int, int, int]:
        """R4T: Damage floor — if attack is unparried and no extra kept
        dice from the attack, set rolled dice to max(10, rolled)."""
        roll, keep, serious = super().next_damage(tn, extra_damage)
        if self.rank >= 4 and extra_damage:
            extra_kept = self.auto_once["damage_kept"]
            if extra_kept == 0:
                roll = max(10, roll)
        return roll, keep, serious
