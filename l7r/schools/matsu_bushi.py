from __future__ import annotations

from l7r.dice import prob
from l7r.combatant import Combatant
from l7r.records import AttackRecord
from l7r.types import RollType


class MatsuBushi(Combatant):
    """Matsu Bushi school (Lion clan). An aggressive berserker school.

    Strategy: All-out offense with maximum initiative dice (always rolls
    10 dice), converting VP spending into wound check resilience, and
    punishing enemies who fail wound checks.

    Special ability: Roll 10 dice on initiative (always maximum).
    School ring: Fire.
    School knacks: double attack, iaijutsu, lunge.

    Key techniques:
    - R1T: Extra rolled die on double attack, iaijutsu, wound check.
    - R2T: Free raise (+5) on iaijutsu.
    - R3T: Each VP spent on any roll also grants a disc wound check bonus
      of 3 * attack skill. Spending VPs on attacks also fuels survivability.
    - R4T: Failed double attacks that would have hit without the +20 TN
      penalty still count as hits (but with no extra damage). Also lowers
      vp_fail_threshold and raises datt_threshold to favor double attacks.
    - R5T: After dealing serious wounds, force the enemy to keep 15 light
      wounds instead of resetting to 0 (making their next wound check
      much harder).

    Never holds actions because the school is pure aggression.
    """

    hold_one_action = False
    school_knacks: list[RollType] = ["double_attack", "iaijutsu", "lunge"]
    r1t_rolls: list[RollType] = ["double_attack", "iaijutsu", "wound_check"]
    r2t_rolls: RollType = "iaijutsu"

    school_ring = "fire"
    r4t_ring_boost = "fire"

    def __init__(self, **kwargs) -> None:
        Combatant.__init__(self, **kwargs)

        self.extra_dice["initiative"] = (10 - self.void - 1, 0)

        self.events["vps_spent"].append(self.r3t_trigger)
        self.events["pre_attack"].append(self.r5t_pre)
        self.events["post_attack"].append(self.r5t_post)

        if self.rank >= 4:
            self.vp_fail_threshold -= 0.15
            self.datt_threshold = 0.33

    def r3t_trigger(self, vps: int, roll_type: RollType) -> None:
        """R3T: Each VP spent on any roll also generates a discretionary
        wound check bonus of 3 * attack. This synergy means aggressive
        VP spending on attacks also builds defensive reserves."""
        if self.rank >= 3:
            for i in range(vps):
                self.disc["wound_check"].append(3 * self.attack)

    def r5t_pre(self) -> None:
        """R5T setup: record the enemy's current serious wounds so we can
        detect whether this attack dealt any."""
        if self.rank == 5:
            self.pre_sw = self.enemy.serious

    def r5t_post(self) -> None:
        """R5T payoff: if we dealt serious wounds and the enemy survived,
        force them to keep 15 light wounds instead of clearing to 0.
        This makes their next wound check dramatically harder."""
        if (
            self.rank == 5
            and self.enemy.light == 0
            and self.enemy.serious > self.pre_sw
            and not self.enemy.dead
        ):
            self.enemy.light = 15

    def att_prob(self, knack: RollType, tn: int) -> float:
        """When estimating double attack probability, factor in that we'll
        likely spend at least 1 VP (giving +1 rolled and kept die). This
        makes the heuristic more willing to attempt double attacks."""
        roll, keep = self.att_dice(knack)
        if knack == "double_attack" and self.vps:
            roll, keep = roll + 1, keep + 1
        return prob[not self.crippled][roll, keep, tn - self.max_bonus(knack)]

    def make_attack(self) -> AttackRecord:
        """R4T: If a double attack misses but would have hit as a normal
        attack (i.e. we only missed because of the +20 TN penalty), it
        still counts as a hit — just without the extra damage dice."""
        rec = Combatant.make_attack(self)
        if self.rank >= 4 and self.attack_knack == "double_attack" and not rec.hit:
            if self.attack_roll >= self.enemy.tn - 20:
                self.attack_roll = 0
                rec.hit = True
        return rec
