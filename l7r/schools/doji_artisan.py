from __future__ import annotations

from l7r.combatant import Combatant
from l7r.types import RollType


class DojiArtisan(Combatant):
    """Doji Artisan school (Crane clan). Reactive counterattacker with scaling.

    Strategy: Air-based defensive counterattacker. The special ability
    allows a reactive counterattack after being hit. If the Artisan has
    a ready action, the counterattack is free (normal VP evaluation).
    If not, the SA lets them spend 1 VP to counterattack anyway, and
    that VP also grants +1k1 on the counterattack roll.

    Special ability: After being hit, may counterattack. If no action
    is available in the current phase, costs 1 VP (which also gives
    +1k1 on the counterattack roll).
    School ring: Air.
    School knacks: counterattack, oppose social, worldliness.

    Key techniques:
    - R1T: Extra rolled die on counterattack, wound check.
    - R2T: Free raise on manipulation (non-combat; oppose_social).
    - R3T: 10 shared free raises on counterattack + wound check.
    - R4T: +1 Air (free). Track attacked_by set; bonus on attack
      against enemies who haven't attacked us this round.
    - R5T: On any roll, add bonus. Attack: (enemy TN - 10) // 5.
      Parry: (attack roll - 10) // 5. Wound check:
      (wound check TN - 10) // 5.
    """

    school_knacks: list[RollType] = ["counterattack", "oppose_social", "worldliness"]
    r1t_rolls: list[RollType] = ["counterattack", "wound_check"]
    r2t_rolls: RollType = "oppose_social"
    school_ring = "air"
    r4t_ring_boost = "air"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        if self.rank >= 3:
            raises = [5] * 10
            for roll_type in ["counterattack", "wound_check"]:
                self.multi[roll_type].append(raises)

        if self.rank >= 4:
            self.attacked_by: set[Combatant] = set()
            self.events["pre_round"].append(self.r4t_reset)
            self.events["pre_defense"].append(self.r4t_track)

        if self.rank >= 5:
            self.r5t_parry_bonus = 0
            self.events["pre_attack"].append(self.r5t_attack_bonus)
            self.events["pre_defense"].append(self.r5t_defense_bonus)
            self.events["post_defense"].append(self.r5t_cleanup_parry)
            self.events["wound_check"].append(self.r5t_wc_bonus)

    def _has_ready_action(self) -> bool:
        """Check if we have an action die ready in the current phase."""
        return bool(self.actions and self.actions[0] <= self.phase)

    def will_react_to_attack(self, enemy: Combatant) -> bool:
        """SA: React to attack when we have a ready action or VPs."""
        return self._has_ready_action() or self.vps > 0

    def will_counterattack(self, enemy: Combatant) -> bool:
        """SA counterattack: free if we have a ready action, otherwise
        costs 1 VP (which also grants +1k1 on the roll)."""
        if self._has_ready_action():
            self.actions.pop(0)
            return True

        if self.vps <= 0:
            return False

        self.vps -= 1
        # The SA VP also grants +1k1 on the counterattack roll
        self.extra_dice["counterattack"][0] += 1
        self.extra_dice["counterattack"][1] += 1

        def restore() -> bool:
            self.extra_dice["counterattack"][0] -= 1
            self.extra_dice["counterattack"][1] -= 1
            return True

        self.events["post_attack"].append(restore)
        return True

    def r4t_reset(self) -> None:
        """R4T: Reset tracked attackers at start of round."""
        self.attacked_by = set()

    def r4t_track(self) -> None:
        """R4T: Track who attacks us."""
        if hasattr(self, 'enemy'):
            self.attacked_by.add(self.enemy)

    def choose_action(self) -> tuple[RollType, Combatant] | None:
        """R4T: Add phase bonus against non-attackers."""
        action = super().choose_action()
        if action and self.rank >= 4:
            knack, target = action
            if hasattr(self, 'attacked_by') and target not in self.attacked_by:
                self.auto_once[knack] += self.phase
        return action

    def r5t_attack_bonus(self) -> None:
        """R5T: Before attacking, add (enemy TN - 10) // 5 bonus."""
        if hasattr(self, 'enemy') and self.enemy:
            bonus = max(0, (self.enemy.tn - 10) // 5)
            self.auto_once[self.attack_knack] += bonus

    def r5t_defense_bonus(self) -> None:
        """R5T: Before defending, add parry bonus from attack roll.

        Only sets the parry bonus here. The wound check bonus is
        handled separately in r5t_wc_bonus (wound_check event) since
        it's based on wound check TN, not attack roll.
        """
        if hasattr(self, 'enemy') and self.enemy and hasattr(self.enemy, 'attack_roll'):
            bonus = max(0, (self.enemy.attack_roll - 10) // 5)
            self.r5t_parry_bonus = bonus
            self.auto_once["parry"] += bonus

    def r5t_cleanup_parry(self) -> None:
        """Remove unused R5T parry bonus if no parry was attempted."""
        if self.r5t_parry_bonus:
            self.auto_once["parry"] -= self.r5t_parry_bonus
            self.r5t_parry_bonus = 0

    def r5t_wc_bonus(self, check: int, light: int, total: int) -> None:
        """R5T: Add bonus to wound check based on wound check TN."""
        bonus = max(0, (total - 10) // 5)
        self.auto_once["wound_check"] += bonus
