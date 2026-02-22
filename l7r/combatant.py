"""
Core combatant logic for the L7R combat simulator.

A Combatant represents a single fighter in combat, encapsulating their stats,
wound state, available actions, and the AI decision-making logic for when to
attack, parry, and spend resources like void points and discretionary bonuses.

School subclasses override specific methods and register event triggers to
implement their unique rank techniques. The base Combatant class implements
the generic rules that apply to all fighters.
"""

from __future__ import annotations

import random
from math import ceil
from copy import deepcopy
from itertools import combinations
from collections import defaultdict
from typing import Any, Callable

from l7r.dice import d10, prob, xky, avg
from l7r.types import RollType, BonusKey, EventName


def all_subsets(xs: list[int]) -> list[tuple[int, ...]]:
    """Return every non-empty subset of xs.

    Used by disc_bonus() to find the cheapest combination of discretionary
    bonuses that meets a target value.
    """
    all = []
    for i in range(1, len(xs) + 1):
        all.extend(combinations(xs, i))
    return all


class Combatant:
    """A single fighter in combat, with stats, wounds, actions, and AI logic.

    This class serves double duty: it holds all the game-mechanical state for
    a combatant (rings, wounds, action dice, bonuses), AND it implements the
    default AI decision-making logic for spending void points, choosing when
    to parry, selecting targets, etc.

    School subclasses (AkodoBushi, BayushiBushi, etc.) override specific
    methods and register event triggers to implement their rank techniques.

    Stats are passed as keyword arguments and set via __dict__.update(),
    so any keyword becomes an attribute. The five Rings (air, earth, fire,
    water, void) and skill levels (attack, parry, plus school knacks) are
    expected to be provided this way.
    """

    counts: defaultdict[type, int] = defaultdict(int)
    """Tracks how many of each subclass have been created, so we can give
    them names like "AkodoBushi1", "AkodoBushi2", etc."""

    # --- AI decision thresholds ---
    # These control the simulated combatant's tactical decisions. Tuning
    # them is one of the main goals of this simulator.

    sw_parry_threshold: int = 2
    """How many additional serious wounds (from the extra damage dice granted
    by an unparried hit vs a parried hit) justify spending an action to
    parry. Higher = more willing to take hits without parrying. When using
    an interrupt (spending 2 actions to parry out of turn), the threshold
    is doubled since the cost is higher."""

    sw2vp_threshold: float = 0.5
    """Minimum ratio of (serious wounds prevented) / (VPs spent) that makes
    spending void points on a wound check worthwhile. E.g. 0.5 means we
    need to prevent at least 1 serious wound per 2 VPs spent."""

    vp_fail_threshold: float = 0.7
    """Minimum probability of success we require before we're willing to
    commit void points to an attack or parry roll. Spending VPs on a roll
    that's likely to fail anyway is wasteful, so we only spend if we
    estimate at least this chance of success."""

    datt_threshold: float = 0.20
    """Maximum acceptable gap between our probability of landing a normal
    attack vs a double attack. Double attacks have +20 TN but deal
    bonus damage + a serious wound, so if our hit chance only drops by
    this much or less, we prefer the double attack."""

    base_wc_threshold: int = 10
    """Light wound total below which we choose to keep accumulating light
    wounds rather than voluntarily taking a serious wound to reset them.
    Keeping light wounds is risky because future wound checks become
    harder, but taking unnecessary serious wounds is also bad."""

    hold_one_action: bool = True
    """Whether to reserve one action die for potential parrying rather than
    spending all actions on attacks. Schools with strong offensive
    techniques (or built-in defensive abilities) set this to False."""

    base_damage_rolled: int = 4
    """Base rolled weapon damage dice. A katana is 4k2 by default. Fire Ring
    is added to rolled dice separately in the damage_dice property."""

    base_damage_kept: int = 2
    """Base kept weapon damage dice."""

    extra_vps: int = 0
    """Additional void points granted at character creation."""

    extra_serious: int = 0
    """Additional serious wounds tolerated before death,
    from character creation."""

    xp: int = 0
    """Experience points. Used by certain abilities (e.g. Kitsuki R5T)
    to budget effects based on the combatant's and targets' experience."""

    # --- School configuration ---
    # Subclasses set these to define their school's identity.

    rank: int = 0
    """Current Dan rank (1-5). Determines which rank techniques are active.
    Set to 0 for non-school combatants (e.g. mooks, professionals)."""

    school_knacks: list[RollType] = []
    """The three advanced skills this school teaches. Each knack's level
    equals the school rank (or is set individually if rank=0)."""

    r1t_rolls: list[RollType] = []
    """1st Dan technique: roll types that get +1 rolled die."""

    r2t_rolls: RollType | None = None
    """2nd Dan technique: roll type that gets a permanent free raise (+5)."""

    school_ring: str = ""
    """The ring associated with this school (e.g. 'void' for Mirumoto).
    Starts at 3 instead of 2 during character creation."""

    r4t_ring_boost: str = ""
    """Ring that gets a free +1 at 4th Dan (the R4T ring boost)."""

    interrupt: str = ""
    """Prepended to parry log messages to indicate an interrupt action."""

    def __init__(self, **kwargs: Any) -> None:
        # Initialize all school knacks to 0; they'll be set from rank below.
        for knack in ["counterattack", "double_attack", "feint", "iaijutsu", "lunge"]:
            setattr(self, knack, 0)

        self.engine: Any = None
        """Back-reference to the Engine running this combat. Set by
        Engine.fight(). Used for logging and formation queries; None
        when testing standalone."""

        self.crippled: bool = False
        self.dead: bool = False
        self.light: int = 0
        self.serious: int = 0

        self.events: defaultdict[EventName, list[Callable[..., Any]]] = defaultdict(list)
        """Event hook system: maps event names to lists of handler functions.
        School techniques register handlers here (e.g. "successful_attack",
        "wound_check", "pre_round"). Handlers that return a truthy value
        are automatically removed, enabling one-shot triggers."""

        self.multi: defaultdict[RollType, list[list[int]]] = defaultdict(list)
        """Multi-use discretionary bonuses, keyed by roll type. Unlike ``disc``
        (which holds individual bonuses), ``multi`` holds lists of bonus
        groups that are shared references — multiple roll types can point
        to the same list, so using a bonus from one depletes it for all.
        This models abilities like "X free raises usable on any of these
        roll types.\""""

        self.attackable: set[Combatant] = set()
        """Which enemies this combatant can currently reach and attack.
        Managed by the Formation, not by the Combatant itself."""

        self.extra_dice: defaultdict[RollType, list[int]] = defaultdict(lambda: [0, 0])
        """Extra dice [rolled, kept] added to specific roll types by
        abilities. E.g. the 1st Dan technique adds [1, 0] to certain rolls."""

        self.disc: defaultdict[RollType, list[int]] = defaultdict(list)
        """Discretionary bonuses: a list of available bonus values for each
        roll type. The AI chooses the optimal subset to spend when needed.
        These represent limited-use abilities like "N free raises per day.\""""

        self.always: defaultdict[RollType, int] = defaultdict(int)
        """Permanent bonuses that always apply to a roll type. E.g. the 2nd
        Dan technique typically grants a free raise (+5) on one roll type."""

        self.auto_once: defaultdict[BonusKey, int] = defaultdict(int)
        """One-shot bonuses that apply to the next roll of a given type and
        then reset to 0. Used for temporary buffs from triggers like
        double attack's extra damage dice."""

        self.counts[self.__class__] += 1
        self.name: str = self.__class__.__name__ + str(self.counts[self.__class__])

        # Apply all keyword arguments as instance attributes. This is the
        # primary way stats (air, earth, fire, water, void, attack, parry,
        # rank, etc.) are set on a combatant.
        self.__dict__.update(kwargs)

        self.reset_tn()
        self.vps: int = self.extra_vps + min(
            [self.air, self.earth, self.fire, self.water, self.void]
        )
        """Void points = lowest ring + any extras. VPs are the most precious
        resource: each one adds +1 rolled AND +1 kept die to a roll."""

        # Register base combat knack triggers (these apply to all combatants).
        self.events["pre_attack"].append(self.lunge_pre_trigger)
        self.events["pre_attack"].append(self.lunge_succ_trigger)
        self.events["successful_attack"].append(self.feint_trigger)
        self.events["pre_attack"].append(self.datt_pre_trigger)
        self.events["post_attack"].append(self.datt_post_trigger)
        self.events["post_attack"].append(self.reset_damage)
        self.events["successful_attack"].append(self.datt_succ_trigger)

        # If rank is set, all school knacks default to that rank.
        # Otherwise, infer rank from the lowest knack value.
        if self.rank:
            for knack in self.school_knacks:
                setattr(self, knack, self.rank)
        elif self.school_knacks:
            self.rank = min(getattr(self, knack) for knack in self.school_knacks)

        # Apply 1st and 2nd Dan techniques.
        for roll_type in self.r1t_rolls:
            self.extra_dice[roll_type][0] += 1
        if self.r2t_rolls:
            self.always[self.r2t_rolls] += 5

    def __getstate__(self) -> dict[str, Any]:
        """Exclude event handlers from pickling, since they contain bound
        methods that don't serialize cleanly."""
        d = self.__dict__.copy()
        del d["events"]
        return d

    def triggers(self, event: EventName, *args: Any, **kwargs: Any) -> None:
        """Fire all handlers registered for the named event.

        Any handler that returns a truthy value is removed afterward. This
        lets one-shot effects (like "reset TN after this attack") clean
        themselves up by returning True.
        """
        to_remove = [f for f in self.events[event] if f(*args, **kwargs)]
        for f in to_remove:
            self.events[event].remove(f)

    def reset_tn(self) -> bool:
        """Restore TN to its base value: 5 + 5 * parry skill.

        Returns True so it can serve as a one-shot event handler that
        auto-removes itself from the event list after firing.
        """
        self.tn = 5 + 5 * self.parry
        return True

    def reset_damage(self) -> None:
        """Clear temporary damage bonuses after each attack resolves.

        Auto-once damage bonuses (extra rolled/kept dice, flat damage) must
        not carry over to the next attack.
        """
        for bonus in ["damage_rolled", "damage_kept", "damage"]:
            self.auto_once[bonus] = 0

    def datt_succ_trigger(self) -> None:
        """Double attack hit bonus: +1 automatic serious wound and +4 extra
        rolled damage dice, reflecting the devastating power of landing
        a double attack despite its +20 TN penalty."""
        if self.attack_knack == "double_attack":
            self.auto_once["serious"] += 1
            self.auto_once["damage_rolled"] += 4

    def datt_pre_trigger(self) -> None:
        """Temporarily raise the defender's TN by 20 during a double attack.

        This makes the attack harder to parry. The TN is restored in
        datt_post_trigger after the attack resolves.
        """
        if self.attack_knack == "double_attack":
            self.enemy.tn += 20

    def datt_post_trigger(self) -> None:
        """Restore the defender's TN after a double attack."""
        if self.attack_knack == "double_attack":
            self.enemy.tn -= 20

    def feint_trigger(self) -> None:
        """Feint success: gain 1 temporary VP and create an immediate action
        in the current phase (by replacing the highest remaining action die).

        Feints deal no damage but generate resources for future attacks."""
        if self.attack_knack == "feint" and len(self.actions):
            self.vps += 1
            self.actions.pop()
            self.actions.insert(0, self.phase)

    def lunge_pre_trigger(self) -> None:
        """Lunge penalty: drop our own TN by 5, making us easier to hit
        for the rest of the round. The tradeoff is more damage on our hit."""
        if self.attack_knack == "lunge":
            self.tn -= 5
            self.events["post_defense"].append(self.reset_tn)

    def lunge_succ_trigger(self) -> None:
        """Lunge hit bonus: +1 extra rolled damage die.

        Unlike normal extra damage, lunge dice are rolled even if the
        defender attempted (but failed) a parry.
        """
        if self.attack_knack == "lunge":
            self.auto_once["damage_rolled"] += 1

    def log(self, message: str, *, indent: int = 4) -> None:
        """Write a combat log message prefixed with this combatant's name.
        No-ops if no engine is attached (e.g. during standalone tests)."""
        if self.engine is not None:
            self.engine.log(" " * indent + self.name + ": " + message)

    def xky(self, roll: int, keep: int, reroll: bool, roll_type: RollType) -> int:
        """Roll XkY dice. Base implementation delegates to dice.xky().

        Schools and professions override this to modify dice individually
        (e.g. rerolling specific dice, bumping low values, keeping extra
        unkept dice for damage).
        """
        return xky(roll, keep, reroll)

    @property
    def spendable_vps(self) -> range:
        """Range of VP amounts we can consider spending on a single roll.

        Usually 0..vps. Mirumoto overrides this to spend in increments of 2
        (since their VPs work differently).
        """
        return range(self.vps + 1)

    @property
    def wc_threshold(self) -> int:
        """Light wound total below which we keep light wounds rather than
        voluntarily taking a serious wound. Schools may override this to
        be more aggressive about absorbing light wounds."""
        return self.base_wc_threshold

    @property
    def sw_to_cripple(self) -> int:
        """Serious wounds needed to become crippled (no longer reroll 10s
        on skill rolls). Equals Earth ring."""
        return self.earth

    @property
    def sw_to_kill(self) -> int:
        """Serious wounds needed to die. Equals 2 * Earth ring,
        plus any extra_serious from character creation."""
        return self.extra_serious + 2 * self.earth

    @property
    def adjacent(self) -> list[Combatant]:
        """Allies standing next to us in the formation, who may be able
        to parry on our behalf or be affected by area abilities.
        Returns [] when no engine/formation is attached (standalone
        testing)."""
        if self.engine is None:
            return []
        return self.engine.formation.adjacent(self)

    def use_disc_bonuses(self, roll_type: RollType, bonuses: tuple[int, ...]) -> None:
        """Consume specific discretionary bonuses that were selected for use.

        Removes each chosen bonus value from whichever pool (disc or multi)
        contains it. Called after disc_bonus() picks the optimal subset.
        """
        all = [self.disc[roll_type]] + self.multi[roll_type]
        for bonus in bonuses:
            for bonus_group in all:
                if bonus in bonus_group:
                    bonus_group.remove(bonus)
                    break

    def disc_bonuses(self, roll_type: RollType) -> list[int]:
        """List all currently available discretionary bonuses for a roll type.

        Combines both the dedicated per-type pool (disc) and any shared
        multi-type pools (multi) into a flat list of available values.
        """
        all = deepcopy(self.disc[roll_type])
        for bonuses in self.multi[roll_type]:
            all.extend(bonuses)
        return all

    def disc_bonus(self, roll_type: RollType, needed: int) -> int:
        """Find the cheapest combination of discretionary bonuses that meets
        the needed value, spend them, and return the total.

        Uses a brute-force subset search (acceptable because characters
        rarely have more than a few discretionary bonuses available).
        Returns 0 if nothing is needed, or the best available total if
        the target can't be fully met.
        """
        if not needed:
            return 0

        bonuses = self.disc_bonuses(roll_type)
        all = [(sum(sub), sub) for sub in all_subsets(bonuses)]
        enough = [e for e in all if e[0] >= needed]
        best = min(enough)[1] if enough else []
        self.use_disc_bonuses(roll_type, best)
        return sum(best)

    def max_bonus(self, roll_type: RollType) -> int:
        """Theoretical maximum bonus if we used every available resource
        (always + auto_once + all discretionary). Used for probability
        estimates when deciding whether to spend VPs."""
        return (
            self.always[roll_type] + self.auto_once[roll_type] + sum(self.disc_bonuses(roll_type))
        )

    def auto_once_bonus(self, bonus_key: BonusKey) -> int:
        """Retrieve and consume a one-shot bonus. Returns the current value
        and resets it to 0 so it won't apply again."""
        bonus = self.auto_once[bonus_key]
        self.auto_once[bonus_key] = 0
        return bonus

    def choose_action(self) -> tuple[RollType, Combatant] | None:
        """AI decision: what to do when it's our turn to act.

        Returns (knack, target) if we choose to attack, or None to pass.

        The base logic:
        - Only act if we have an action die ready for this phase
        - If hold_one_action is True, keep one action in reserve for parrying
          (unless it's phase 10 and actions are use-it-or-lose-it)
        - Prefer double attack over normal attack if our hit probability
          only drops by datt_threshold or less (since double attacks deal
          significantly more damage when they land)
        """
        if (
            self.actions
            and self.actions[0] <= self.phase
            and (
                self.phase == 10
                or not self.hold_one_action
                or len(self.actions) >= 2
                and self.actions[1] <= self.phase
            )
        ):
            self.actions.pop(0)
            knack = "attack"

            if self.double_attack:
                tn = min(e.tn for e in self.attackable)
                datt_prob = self.att_prob("double_attack", tn + 20)
                att_prob = self.att_prob("attack", tn)
                if att_prob - datt_prob <= self.datt_threshold:
                    knack = "double_attack"

            return knack, self.att_target(knack)

    def will_counterattack(self, enemy: Combatant) -> bool:
        """Whether to counterattack before the enemy's attack resolves.
        Base combatants never counterattack; schools may override."""
        return False

    def will_counterattack_for(self, ally: Combatant, enemy: Combatant) -> bool:
        """Whether to counterattack on behalf of an adjacent ally.
        Base combatants never do this; schools may override."""
        return False

    @property
    def init_dice(self) -> tuple[int, int]:
        """Initiative dice pool: (Void + 1)k(Void), plus extra dice from
        abilities. Each kept die becomes an action in the phase matching
        its face value (lower = earlier = better)."""
        roll, keep = self.extra_dice["initiative"]
        roll += self.void + 1
        keep += self.void
        return roll, keep

    def initiative(self) -> None:
        """Roll action dice for the round.

        Each d10 (without rerolling 10s) becomes an action in the phase
        matching its face value. Lower is better since you act sooner.
        We keep the lowest dice and sort them — this becomes our action
        schedule for the round.
        """
        roll, keep = self.init_dice
        self.actions = sorted(d10(False) for i in range(roll))[:keep]
        self.init_order = self.actions[:]
        self.log(f"initiative: {self.actions}", indent=0)

    @property
    def damage_dice(self) -> tuple[int, int]:
        """Base damage dice pool: (weapon_rolled + Fire)k(weapon_kept).

        Fire Ring is added to rolled dice because stronger fighters swing
        harder. Kept dice come from the weapon base only.
        """
        roll, keep = self.extra_dice["damage"]
        roll += self.base_damage_rolled + self.fire
        keep += self.base_damage_kept
        return roll, keep

    def next_damage(self, tn: int, extra_damage: bool) -> tuple[int, int, int]:
        """Calculate the damage dice pool for the current attack.

        Returns (rolled, kept, bonus_serious_wounds).

        If extra_damage is True (hit was not parried), we add bonus rolled
        dice for every 5 points the attack exceeded the TN by, plus any
        auto_once bonuses from abilities like double attack. If False
        (parried but failed), we skip those extras — the parry attempt
        negated the precision bonus even though it didn't fully block.
        """
        extra_rolled = max(0, self.attack_roll - tn) // 5 + self.auto_once_bonus("damage_rolled")
        extra_kept = self.auto_once_bonus("damage_kept")
        extra_serious = self.auto_once_bonus("serious")

        roll, keep = self.damage_dice
        if extra_damage:
            roll += extra_rolled
            keep += extra_kept

        return roll, keep, (extra_serious if extra_damage else 0)

    def deal_damage(self, tn: int, extra_damage: bool = True) -> tuple[int, int]:
        """Roll damage dice and return (light_wounds, serious_wounds).

        Damage always rerolls 10s (even when crippled). The total becomes
        light wounds, plus any bonus serious wounds from abilities.
        """
        roll, keep, serious = self.next_damage(tn, extra_damage)
        self.last_damage_rolled = roll
        light = self.xky(roll, keep, True, "damage") + self.auto_once_bonus("damage")
        self.log(f"deals {light} light and {serious} serious wounds")
        return light, serious

    @property
    def wc_dice(self) -> tuple[int, int]:
        """Wound check dice pool: (Water + 1)k(Water).

        Water Ring represents physical toughness and recovery."""
        roll, keep = self.extra_dice["wound_check"]
        roll += self.water + 1
        keep += self.water
        return roll, keep

    def calc_serious(self, light: int, check: float) -> int:
        """Calculate serious wounds from a failed wound check.

        1 serious wound for failing, plus 1 more for every full 10 points
        the light wound total exceeds the check result.  Note that "check" is
        a float because this is called to calculate either how many wounds
        someone takes from a hit, but also to estimate how many they might take
        based on the average for such a roll (which is used to make decisions
        about things like whether to spend a void point on the wound check).
        """
        return int(ceil(max(0, light - check) / 10))

    def avg_serious(self, light: int, roll: int, keep: int) -> list[list[int, int]]:
        """Estimate expected serious wounds for each level of VP spending.

        Returns a list of [vps_spent, estimated_serious_wounds] pairs,
        used by the decision function to determine how many VPs are worth
        spending on a wound check.
        """
        wounds = []
        for vps in self.spendable_vps:
            avg_wc = avg(True, roll + vps, keep + vps) + self.max_bonus("wound_check")
            wounds.append([vps, self.calc_serious(light, avg_wc)])
        return wounds

    def wc_bonus(self, light: int, check: int) -> int:
        """Decide which static bonuses to apply to a wound check.

        If we're one serious wound from death, spend everything available
        to survive. Otherwise, only spend enough discretionary bonuses to
        avoid taking more serious wounds than necessary — don't waste
        limited resources when taking 1 serious wound is acceptable.
        """
        bonus = self.always["wound_check"] + self.auto_once_bonus("wound_check")
        if self.serious + 1 == self.sw_to_kill:
            # Desperate: spend all available bonuses to survive.
            needed = max(0, light - check - bonus)
            return bonus + self.disc_bonus("wound_check", needed)
        else:
            # Only spend enough to reduce serious wounds by at least 1.
            # The -9 accounts for the 10-point window between wound
            # thresholds: we need to close the gap to the next threshold.
            needed = max(0, light - check - bonus - 9)
            while needed > sum(self.disc_bonuses("wound_check")):
                needed = max(0, needed - 10)
            return bonus + self.disc_bonus("wound_check", needed)

    def wc_vps(self, light: int, roll: int, keep: int) -> int:
        """Decide how many void points to spend on a wound check.

        Works backwards from maximum VPs, looking for the sweet spot where
        spending VPs prevents enough serious wounds to justify the cost.
        Only spends if the ratio of (serious wounds prevented / VPs spent)
        meets sw2vp_threshold, OR if we'd die without spending.
        """
        wounds = self.avg_serious(light, roll, keep)
        for i in range(len(wounds) - 1, 0, -1):
            vps, serious = wounds[i]
            if serious < wounds[i - 1][1] and (
                self.sw2vp_threshold <= (wounds[0][1] - serious) / vps
                or serious + self.serious >= self.sw_to_kill
            ):
                self.triggers("vps_spent", vps, "wound_check")
                self.vps -= vps
                return vps
        return 0

    def wound_check(self, light: int, serious: int = 0) -> None:
        """Perform a full wound check after taking damage.

        The wound check TN is the cumulative light wound total (new damage
        plus any existing light wounds). After rolling:
        - If the check fails: take 1+ serious wounds, light wounds reset to 0
        - If the check succeeds and light wounds are low enough: keep them
        - If the check succeeds but light wounds are dangerously high: take
          1 voluntary serious wound to reset light wounds to 0 (unless
          we're one serious wound from death, in which case we keep light
          wounds no matter how high they are)
        """
        light_total = light + self.light
        prev_serious = self.serious
        self.serious += serious

        roll, keep = self.wc_dice
        vps = self.wc_vps(light_total, roll, keep)
        check = self.xky(roll + vps, keep + vps, True, "wound_check")
        check += self.wc_bonus(light_total, check)

        self.triggers("wound_check", check, light, light_total)
        if check < light_total:
            self.light = 0
            self.serious += self.calc_serious(light_total, check)
        elif light_total <= self.wc_threshold or self.serious >= self.sw_to_kill - 1:
            # Keep light wounds: either they're low enough to be safe, or
            # we're one serious wound from death and can't afford to take
            # a voluntary one.
            self.light = light_total
        else:
            # Voluntarily take 1 serious wound to clear light wound total,
            # since accumulating light wounds makes future checks harder.
            self.light = 0
            self.serious += 1

        self.log(
            f"{check} wound check ({vps} vp) vs {light_total} light wounds, takes {self.serious - prev_serious} serious"
        )
        self.crippled = self.serious >= self.sw_to_cripple
        self.dead = self.serious >= self.sw_to_kill

    def att_dice(self, knack: RollType) -> tuple[int, int]:
        """Attack dice pool: (Fire + skill)k(Fire) for the given knack."""
        roll, keep = self.extra_dice[knack]
        roll += self.fire + getattr(self, knack)
        keep += self.fire
        return roll, keep

    def att_prob(self, knack: RollType, tn: int) -> float:
        """Look up our probability of hitting a given TN with a given knack.

        Uses the pre-computed probability tables, accounting for whether
        we're crippled (which determines if we reroll 10s).
        """
        roll, keep = self.att_dice(knack)
        return prob[not self.crippled][roll, keep, tn - self.max_bonus(knack)]

    def att_target(self, knack: RollType = "attack") -> Combatant:
        """Choose which enemy to attack using weighted random selection.

        Weights favor wounded, low-TN, and action-depleted targets — we
        want to finish off weakened enemies and press advantages. For
        double attacks, we restrict to the lowest-TN target since the
        +20 TN penalty makes it impractical against harder targets.
        """
        min_tn = min(e.tn for e in self.attackable)
        targets = [e for e in self.attackable if knack != "double_attack" or e.tn == min_tn]
        return random.choice(
            sum(
                [
                    [e] * (1 + e.serious + (30 - e.tn) // 5 + len(e.init_order) - len(e.actions))
                    for e in targets
                ],
                [],
            )
        )

    def att_bonus(self, tn: int, attack_roll: int) -> int:
        """Apply bonuses to an attack roll after the dice are rolled.

        Uses always bonuses first, then spends the minimum discretionary
        bonuses needed to meet the TN.
        """
        bonus = self.always[self.attack_knack] + self.auto_once_bonus(self.attack_knack)
        needed = max(0, tn - attack_roll - bonus)
        return bonus + self.disc_bonus(self.attack_knack, needed)

    def att_vps(self, tn: int, roll: int, keep: int) -> int:
        """Decide how many void points to pre-commit to an attack roll.

        Starts from 0 VPs and works up, spending the minimum number of VPs
        that brings our success probability above vp_fail_threshold. If even
        maximum VPs can't reach the threshold, spends nothing (don't throw
        good VPs after bad).
        """
        max_bonus = self.max_bonus(self.attack_knack)
        for vps in self.spendable_vps:
            if (
                prob[self.crippled][roll + vps, keep + vps, tn - max_bonus]
                >= self.vp_fail_threshold
            ):
                self.triggers("vps_spent", vps, self.attack_knack)
                self.vps -= vps
                return vps
        return 0

    def make_attack(self) -> bool:
        """Execute a full attack: roll dice, apply bonuses, check for hit.

        Returns True if the attack hits (and isn't a feint). Feints return
        False even on a "hit" because they deal no damage — their benefit
        comes from the successful_attack trigger granting VPs and actions.
        """
        roll, keep = self.att_dice(self.attack_knack)
        vps = self.att_vps(self.enemy.tn, roll, keep)
        result = self.xky(roll + vps, keep + vps, not self.crippled, self.attack_knack)
        self.attack_roll = result + self.att_bonus(self.enemy.tn, result)
        self.log(f"{self.attack_roll} {self.attack_knack} roll ({vps} vp) vs {self.enemy.tn} tn")

        success = self.attack_roll >= self.enemy.tn
        if success:
            self.triggers("successful_attack")
        return success and self.attack_knack != "feint"

    @property
    def parry_dice(self) -> tuple[int, int]:
        """Parry dice pool: (Air + parry_skill)k(Air).

        Air Ring governs parrying because it represents reflexes and
        awareness.
        """
        roll, keep = self.extra_dice["parry"]
        roll += self.air + self.parry
        keep += self.air
        return roll, keep

    def will_predeclare(self) -> bool:
        """Whether to commit to parrying before seeing the attack roll.

        Pre-declaring grants a +5 bonus (free raise) to the parry, but
        commits the action even if the attack would have missed. Base
        combatants never pre-declare; defensive schools override this.
        """
        self.predeclare_bonus = 0
        return False

    def projected_damage(self, enemy: Combatant, extra_damage: bool) -> int:
        """Estimate how many serious wounds an enemy's attack would inflict.

        Uses deepcopy to avoid mutating the enemy's state during the
        estimate. Used by will_parry() to decide if parrying is worth
        the action cost.
        """
        droll, dkeep, serious = deepcopy(enemy).next_damage(self.tn, extra_damage)
        light = avg(True, droll, dkeep)
        wcroll, wckeep = self.wc_dice
        return serious + self.avg_serious(light, wcroll, wckeep)[0][1]

    def will_parry(self) -> bool:
        """AI decision: whether to attempt to parry the current attack.

        Compares projected damage with extra dice (unparried hit) vs without
        (parried but failed). The difference tells us how much worse it is
        to not parry.

        Decision factors:
        - If we pre-declared, we're already committed: always parry
        - If we have no available actions, we can't parry
        - If we'd need to interrupt (spend a future action), the damage
          threshold is doubled since the cost is higher
        - If not parrying would kill us, always parry
        """
        extra = self.projected_damage(self.enemy, True)
        base = self.projected_damage(self.enemy, False)

        self.interrupt = ""
        if self.predeclare_bonus:
            parry = True
        elif not self.actions or self.actions[0] > self.phase and len(self.actions) < 2:
            parry = False
        elif self.actions[0] > self.phase:
            # Interrupt: costs 2 action dice (the last two) since we're
            # acting out of turn.
            parry = (
                extra + self.serious >= self.sw_to_kill
                or extra - base >= 2 * self.sw_parry_threshold
            )
            if parry:
                self.interrupt = "interrupt "
                self.actions[-2:] = []
        else:
            # Normal parry: costs 1 action die from the current phase.
            parry = (
                extra + self.serious >= self.sw_to_kill or extra - base >= self.sw_parry_threshold
            )
            if parry:
                self.actions.pop(0)

        return parry

    def will_predeclare_for(self, ally: Combatant, enemy: Combatant) -> bool:
        """Whether to pre-declare a parry on behalf of an adjacent ally.
        Base combatants never do this; schools may override."""
        self.predeclare_bonus = 0
        return False

    def will_parry_for(self, ally: Combatant, enemy: Combatant) -> bool:
        """Whether to parry on behalf of an adjacent ally.
        Base combatants never do this; schools may override."""
        return False

    def parry_bonus(self, tn: int, parry_roll: int) -> int:
        """Apply bonuses to a parry roll after the dice are rolled.

        Includes predeclare bonus (+5 if we committed early), always
        bonuses, and the minimum discretionary bonuses needed to succeed.
        """
        bonus = self.predeclare_bonus + self.always["parry"] + self.auto_once_bonus("parry")
        self.predeclare_bonus = 0
        needed = max(0, tn - parry_roll - bonus)
        return bonus + self.disc_bonus("parry", needed)

    def parry_vps(self, tn: int, roll: int, keep: int) -> int:
        """Decide how many VPs to spend on a parry roll.

        Same logic as att_vps: find the minimum VPs that bring our success
        probability above vp_fail_threshold.
        """
        max_bonus = self.max_bonus("parry") + self.predeclare_bonus
        for vps in self.spendable_vps:
            if (
                prob[self.crippled][roll + vps, keep + vps, tn - max_bonus]
                >= self.vp_fail_threshold
            ):
                self.triggers("vps_spent", vps, "parry")
                self.vps -= vps
                return vps
        return 0

    def make_parry_for(self, ally: Combatant, enemy: Combatant) -> bool:
        """Parry on behalf of an adjacent ally.

        When parrying for someone else, the TN is raised by 5 * attacker's
        skill rank in the knack being used, making it harder to intercept
        a skilled attacker's strike.
        """
        enemy.attack_roll += 5 * getattr(enemy, enemy.attack_knack)
        success = self.make_parry(enemy)
        enemy.attack_roll -= 5 * getattr(enemy, enemy.attack_knack)
        return success

    def make_parry(self, auto_success: bool = False) -> bool:
        """Execute a full parry: roll dice, apply bonuses, check for success.

        The parry TN is the attacker's attack roll result. If auto_success
        is True, the parry succeeds regardless of the roll (used for
        certain guaranteed-parry abilities).
        """
        roll, keep = self.parry_dice
        vps = self.parry_vps(self.enemy.attack_roll, roll, keep)
        result = self.xky(roll + vps, keep + vps, not self.crippled, "parry")
        self.parry_roll = result + self.parry_bonus(self.enemy.attack_roll, result)
        self.log(f"{self.parry_roll} {self.interrupt}parry roll ({vps} vp)")

        success = auto_success or self.parry_roll >= self.enemy.attack_roll
        if success:
            self.triggers("successful_parry")
        return success
