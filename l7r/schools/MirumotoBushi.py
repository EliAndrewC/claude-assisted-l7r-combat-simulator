from __future__ import annotations

from l7r.combatant import Combatant
from l7r.types import RollType


class MirumotoBushi(Combatant):
    """Mirumoto Bushi school (Dragon clan). A defensive two-sword school.

    Strategy: Parry-focused — gains VPs from successful parries and
    accumulates shared disc bonuses each round.

    Special ability: Gain 1 VP per successful parry.
    School ring: Void.
    School knacks: counterattack, double attack, iaijutsu.

    Key techniques:
    - R1T: Extra rolled die on attack, double attack, parry.
    - R2T: Free raise (+5) on parry.
    - R3T: Each round, gain (attack) shared +2 disc bonuses on attacks,
      double attacks, counterattacks, and parries.
    - R4T: Failed parries halve the attacker's rolled damage dice.
    - R5T: Each VP spent gives an extra +10 bonus to the roll.

    AI strategy: Hold all actions until phase 10, parrying attacks along
    the way (spending R3T points to lower action dice when needed). Build
    up VPs from successful parries, then double attack at end of round
    if VPs make it viable. Uses a higher parry threshold (configurable
    via late_parry_threshold) when down to 1-2 actions.
    """

    school_knacks: list[RollType] = ["counterattack", "double_attack", "iaijutsu"]
    r1t_rolls: list[RollType] = ["attack", "double_attack", "parry"]
    r2t_rolls: RollType = "parry"

    school_ring: str = "void"
    r4t_ring_boost: str = "void"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        self.events["successful_parry"].append(self.sa_trigger)
        self.events["pre_round"].append(self.r3t_trigger)

        if self.rank >= 5:
            self.events["vps_spent"].append(self.r5t_trigger)

    def sa_trigger(self) -> None:
        """Special ability: gain VPs from successful parries. The core
        resource engine — parrying fuels future attacks and more parries."""
        self.vps += 1

    def r3t_trigger(self) -> None:
        """R3T/R4T: Generate shared disc bonuses each round on attacks, double
        attacks, counterattacks, and parries."""
        if self.rank >= 3:
            self.points = [2] * self.attack
            for knack in ["attack", "double_attack", "counterattack", "parry"]:
                self.multi[knack].append(self.points)

    def r5t_trigger(self, vps: int, knack: RollType) -> None:
        """R5T: Each VP spent gives an extra +10 bonus to the roll."""
        self.auto_once[knack] += 10 * vps

    late_parry_threshold: int = 4
    """Serious wound threshold for parrying when down to 1-2 actions.

    Higher than the base sw_parry_threshold, reflecting that the Mirumoto
    prefers to tank hits late in the round and save actions for their
    final double attack.  Configurable for simulation tuning.
    """

    def choose_action(self) -> tuple[RollType, Combatant] | None:
        """Hold all actions until phase 10, then attack.

        In phase 10, prefer double attack if spending available VPs (plus
        any remaining R3T disc points) gives a reasonable chance of hitting
        the double attack TN (+20).  Otherwise fall back to a regular attack.
        """
        if self.phase != 10:
            return None
        if not self.actions:
            return None

        self.actions.pop(0)

        if self.double_attack:
            tn = min(e.tn for e in self.attackable)
            datt_prob = self.att_prob("double_attack", tn + 20)
            att_prob = self.att_prob("attack", tn)
            if att_prob - datt_prob <= self.datt_threshold:
                return "double_attack", self.att_target("double_attack")

        return "attack", self.att_target("attack")

    def will_predeclare(self) -> bool:
        """Pre-declare parries early in the round when actions are plentiful.

        Returns True (and sets predeclare_bonus=5) when we have more than
        2 actions remaining — early in the round, we're happy to commit to
        parrying since it builds VPs via the special ability.
        """
        if len(self.actions) > 2:
            self.predeclare_bonus = 5
            return True
        self.predeclare_bonus = 0
        return False

    def will_parry(self) -> bool:
        """AI decision: whether to parry the current attack.

        The Mirumoto's parry strategy has several layers:

        1. If pre-declared, always parry (already committed).
        2. If an action die is available this phase, use it normally.
        3. If no current-phase action, spend R3T points to lower the
           cheapest future action die to the current phase.
        4. When down to 1-2 actions, use a higher damage threshold
           (late_parry_threshold) — prefer tanking hits to save actions
           for the final double attack.
        5. Always parry if the hit would kill us.
        """
        if self.predeclare_bonus:
            return True

        if not self.actions and not self.points:
            return False

        # Determine if we can get an action for this phase
        has_current = self.actions and self.actions[0] <= self.phase

        if not has_current:
            # Try to lower a future action die using R3T points
            if not self.actions or not self.points:
                return False
            # Find cheapest action to lower
            lowest_action = self.actions[0]
            cost = lowest_action - self.phase
            if cost <= 0 or cost > len(self.points):
                return False
            # Check damage projection before spending points
            extra = self.projected_damage(self.enemy, True)
            base = self.projected_damage(self.enemy, False)
            threshold = self._parry_threshold()
            if extra + self.serious >= self.sw_to_kill or extra - base >= threshold:
                # Commit: spend points and consume the action
                del self.points[:cost]
                self.actions.pop(0)
                return True
            return False

        # Normal parry with current-phase action
        extra = self.projected_damage(self.enemy, True)
        base = self.projected_damage(self.enemy, False)
        threshold = self._parry_threshold()
        parry = extra + self.serious >= self.sw_to_kill or extra - base >= threshold
        if parry:
            self.actions.pop(0)
        return parry

    def _parry_threshold(self) -> int:
        """Return the damage threshold for deciding to parry.

        Uses the higher late_parry_threshold when we're down to 1-2
        actions, to preserve them for the end-of-round attack.
        """
        if len(self.actions) <= 2:
            return self.late_parry_threshold
        return self.sw_parry_threshold

    def make_parry(self, auto_success: bool = False) -> bool:
        """Execute a parry, with R4T damage reduction on failure.

        At rank 4+, when our parry fails, the attacker's rolled damage
        dice are halved — reflecting the two-sword style disrupting the
        attacker's follow-through even on a failed parry.
        """
        success = super().make_parry(auto_success)
        if not success and self.rank >= 4:
            rolled = self.enemy.extra_dice["damage"][0]
            reduction = self.enemy.damage_dice[0] // 2
            self.enemy.extra_dice["damage"][0] -= reduction

            def restore() -> bool:
                self.enemy.extra_dice["damage"][0] = rolled
                return True  # one-shot: remove after firing

            self.events["post_defense"].append(restore)
        return success
