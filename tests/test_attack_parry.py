"""Tests for the attack/parry sequence, knack triggers, event lifecycle,
and TN mutation symmetry.

These tests cover the combat mechanics that sit between the bonus/dice
layer (already tested) and the engine orchestration layer: make_attack,
make_parry, VP spending, knack-specific triggers, and the event system
that ties them together.
"""

from unittest.mock import patch

from l7r.combatant import Combatant


def make_combatant(**overrides) -> Combatant:
    """Create a Combatant with sensible defaults for testing."""
    defaults = dict(
        air=3, earth=3, fire=3, water=3, void=3,
        attack=3, parry=3,
    )
    defaults.update(overrides)
    return Combatant(**defaults)


def setup_combat_pair(**attacker_kw):
    """Create an attacker/defender pair wired up for combat tests.

    Sets enemy references, attack_knack, attack_roll, and action
    state, mimicking what the Engine does before calling make_attack.
    """
    attacker = make_combatant(**attacker_kw)
    defender = make_combatant()
    attacker.enemy = defender
    defender.enemy = attacker
    attacker.attack_knack = "attack"
    attacker.attack_roll = 0
    defender.attack_roll = 0
    # Give them actions so parry decisions work.
    attacker.actions = [1, 3, 5]
    attacker.init_order = [1, 3, 5]
    attacker.phase = 1
    defender.actions = [2, 4, 6]
    defender.init_order = [2, 4, 6]
    defender.phase = 2
    return attacker, defender


# ── Event trigger system ─────────────────────────────────────────────


class TestTriggers:
    """Tests for the event dispatch and one-shot removal logic."""

    def test_handler_called(self) -> None:
        c = make_combatant()
        called = []
        c.events["pre_round"].append(lambda: called.append(1))
        c.triggers("pre_round")
        assert called == [1]

    def test_multiple_handlers(self) -> None:
        c = make_combatant()
        called = []
        c.events["pre_round"].append(lambda: called.append("a"))
        c.events["pre_round"].append(lambda: called.append("b"))
        c.triggers("pre_round")
        assert called == ["a", "b"]

    def test_one_shot_removed_on_truthy_return(self) -> None:
        """Handlers returning truthy are removed after firing."""
        c = make_combatant()
        c.events["post_defense"].append(lambda: True)
        assert len(c.events["post_defense"]) == 1
        c.triggers("post_defense")
        assert len(c.events["post_defense"]) == 0

    def test_persistent_handler_not_removed(self) -> None:
        """Handlers returning None/falsy stay registered."""
        c = make_combatant()
        c.events["pre_round"].append(lambda: None)
        c.triggers("pre_round")
        assert len(c.events["pre_round"]) == 1

    def test_args_forwarded(self) -> None:
        c = make_combatant()
        received = []
        c.events["wound_check"].append(
            lambda *args, **kwargs: received.append((args, kwargs))
        )
        c.triggers("wound_check", 10, 20, foo="bar")
        assert received == [((10, 20), {"foo": "bar"})]

    def test_no_handlers_is_noop(self) -> None:
        """Triggering an event with no handlers doesn't error."""
        c = make_combatant()
        c.triggers("pre_fight")  # No handlers registered.

    def test_one_shot_among_persistent(self) -> None:
        """Only the truthy-returning handler is removed; others stay."""
        c = make_combatant()
        persistent = lambda: None  # noqa: E731
        one_shot = lambda: True  # noqa: E731
        c.events["post_defense"].append(persistent)
        c.events["post_defense"].append(one_shot)
        c.triggers("post_defense")
        assert c.events["post_defense"] == [persistent]


# ── reset_tn ─────────────────────────────────────────────────────────


class TestResetTN:
    """Tests for TN initialization and the reset_tn one-shot."""

    def test_base_tn(self) -> None:
        """TN = 5 + 5 * parry skill."""
        c = make_combatant(parry=4)
        assert c.tn == 25

    def test_reset_tn_restores(self) -> None:
        c = make_combatant(parry=3)
        c.tn = 999
        c.reset_tn()
        assert c.tn == 20

    def test_reset_tn_returns_true(self) -> None:
        """Returns True so it auto-removes as a one-shot handler."""
        c = make_combatant()
        assert c.reset_tn() is True

    def test_reset_tn_as_one_shot_event(self) -> None:
        """When registered as a handler, reset_tn fires once and is
        removed."""
        c = make_combatant(parry=3)
        c.tn = 50
        c.events["post_defense"].append(c.reset_tn)
        c.triggers("post_defense")
        assert c.tn == 20
        # Should be removed after firing.
        assert c.reset_tn not in c.events["post_defense"]
        # Mutate again — no handler to fix it.
        c.tn = 50
        c.triggers("post_defense")
        assert c.tn == 50


# ── Double attack TN mutation symmetry ───────────────────────────────


class TestDoubleAttackTNMutation:
    """Tests that the double attack +20 TN raise is properly
    symmetric: datt_pre raises, datt_post restores."""

    def test_pre_raises_tn(self) -> None:
        attacker, defender = setup_combat_pair()
        attacker.attack_knack = "double_attack"
        original_tn = defender.tn
        attacker.datt_pre_trigger()
        assert defender.tn == original_tn + 20

    def test_post_restores_tn(self) -> None:
        attacker, defender = setup_combat_pair()
        attacker.attack_knack = "double_attack"
        original_tn = defender.tn
        attacker.datt_pre_trigger()
        attacker.datt_post_trigger()
        assert defender.tn == original_tn

    def test_noop_for_normal_attack(self) -> None:
        """Neither trigger modifies TN for non-double-attack knacks."""
        attacker, defender = setup_combat_pair()
        attacker.attack_knack = "attack"
        original_tn = defender.tn
        attacker.datt_pre_trigger()
        assert defender.tn == original_tn
        attacker.datt_post_trigger()
        assert defender.tn == original_tn

    def test_symmetry_through_event_system(self) -> None:
        """Firing pre_attack and post_attack events for a double
        attack leaves TN unchanged."""
        attacker, defender = setup_combat_pair()
        attacker.attack_knack = "double_attack"
        original_tn = defender.tn
        attacker.triggers("pre_attack")
        assert defender.tn == original_tn + 20
        attacker.triggers("post_attack")
        assert defender.tn == original_tn

    def test_symmetry_after_full_make_attack(self) -> None:
        """After a complete make_attack + event cycle for a double
        attack, the defender's TN is restored regardless of hit/miss.
        """
        attacker, defender = setup_combat_pair()
        attacker.attack_knack = "double_attack"
        attacker.double_attack = 3  # Skill level.
        original_tn = defender.tn

        # Force a miss to keep things simple.
        with patch.object(attacker, "xky", return_value=1):
            attacker.triggers("pre_attack")
            attacker.make_attack()
            attacker.triggers("post_attack")

        assert defender.tn == original_tn


# ── Double attack success trigger ────────────────────────────────────


class TestDoubleAttackSuccTrigger:
    """Tests for the bonus damage on double attack hits."""

    def test_adds_serious_and_damage_rolled(self) -> None:
        attacker, _ = setup_combat_pair()
        attacker.attack_knack = "double_attack"
        attacker.datt_succ_trigger()
        assert attacker.auto_once["serious"] == 1
        assert attacker.auto_once["damage_rolled"] == 4

    def test_noop_for_normal_attack(self) -> None:
        attacker, _ = setup_combat_pair()
        attacker.attack_knack = "attack"
        attacker.datt_succ_trigger()
        assert attacker.auto_once["serious"] == 0
        assert attacker.auto_once["damage_rolled"] == 0

    def test_fires_on_successful_attack_event(self) -> None:
        """The trigger is registered on 'successful_attack' and fires
        when the event dispatches."""
        attacker, defender = setup_combat_pair()
        attacker.attack_knack = "double_attack"
        attacker.triggers("successful_attack")
        assert attacker.auto_once["serious"] == 1
        assert attacker.auto_once["damage_rolled"] == 4


# ── Feint trigger ────────────────────────────────────────────────────


class TestFeintTrigger:
    """Tests for the feint success trigger: +1 VP and immediate
    action."""

    def test_gains_vp_and_action(self) -> None:
        attacker, _ = setup_combat_pair()
        attacker.attack_knack = "feint"
        attacker.phase = 3
        initial_vps = attacker.vps
        attacker.feint_trigger()
        assert attacker.vps == initial_vps + 1
        # Highest action (5) removed, phase 3 action inserted at front.
        assert attacker.actions[0] == 3

    def test_noop_for_normal_attack(self) -> None:
        attacker, _ = setup_combat_pair()
        attacker.attack_knack = "attack"
        initial_vps = attacker.vps
        attacker.feint_trigger()
        assert attacker.vps == initial_vps

    def test_noop_when_no_actions(self) -> None:
        """Feint trigger does nothing if there are no actions to
        replace."""
        attacker, _ = setup_combat_pair()
        attacker.attack_knack = "feint"
        attacker.actions = []
        initial_vps = attacker.vps
        attacker.feint_trigger()
        assert attacker.vps == initial_vps


# ── Lunge triggers and TN mutation ───────────────────────────────────


class TestLungeTriggers:
    """Tests for lunge_pre (TN drop) and lunge_succ (bonus damage)."""

    def test_lunge_pre_drops_own_tn(self) -> None:
        attacker, _ = setup_combat_pair()
        attacker.attack_knack = "lunge"
        original_tn = attacker.tn
        attacker.lunge_pre_trigger()
        assert attacker.tn == original_tn - 5

    def test_lunge_pre_registers_reset(self) -> None:
        """After lunge_pre, a reset_tn one-shot is added to
        post_defense."""
        attacker, _ = setup_combat_pair()
        attacker.attack_knack = "lunge"
        attacker.lunge_pre_trigger()
        assert attacker.reset_tn in attacker.events["post_defense"]

    def test_lunge_tn_restored_on_post_defense(self) -> None:
        """The lunge TN drop is restored when post_defense fires."""
        attacker, _ = setup_combat_pair()
        attacker.attack_knack = "lunge"
        original_tn = attacker.tn
        attacker.lunge_pre_trigger()
        assert attacker.tn == original_tn - 5
        attacker.triggers("post_defense")
        assert attacker.tn == original_tn

    def test_lunge_succ_adds_damage_rolled(self) -> None:
        attacker, _ = setup_combat_pair()
        attacker.attack_knack = "lunge"
        attacker.lunge_succ_trigger()
        assert attacker.auto_once["damage_rolled"] == 1

    def test_lunge_succ_noop_for_normal_attack(self) -> None:
        attacker, _ = setup_combat_pair()
        attacker.attack_knack = "attack"
        attacker.lunge_succ_trigger()
        assert attacker.auto_once["damage_rolled"] == 0

    def test_lunge_pre_noop_for_normal_attack(self) -> None:
        attacker, _ = setup_combat_pair()
        attacker.attack_knack = "attack"
        original_tn = attacker.tn
        attacker.lunge_pre_trigger()
        assert attacker.tn == original_tn


# ── Attack dice and probability ──────────────────────────────────────


class TestAttackDice:
    """Tests for att_dice and att_prob."""

    def test_att_dice_basic(self) -> None:
        """Attack dice = (Fire + skill)k(Fire)."""
        c = make_combatant(fire=4, attack=3)
        roll, keep = c.att_dice("attack")
        assert roll == 7  # 4 + 3
        assert keep == 4

    def test_att_dice_with_knack(self) -> None:
        """Knack skill uses getattr, so double_attack=2 gives
        (Fire+2)k(Fire)."""
        c = make_combatant(fire=4)
        c.double_attack = 2
        roll, keep = c.att_dice("double_attack")
        assert roll == 6  # 4 + 2
        assert keep == 4

    def test_att_dice_includes_extra(self) -> None:
        c = make_combatant(fire=3, attack=3)
        c.extra_dice["attack"][0] += 1
        c.extra_dice["attack"][1] += 1
        roll, keep = c.att_dice("attack")
        assert roll == 7  # 3 + 3 + 1
        assert keep == 4  # 3 + 1

    def test_att_prob_returns_float(self) -> None:
        c = make_combatant(fire=3, attack=3)
        p = c.att_prob("attack", 15)
        assert isinstance(p, float)
        assert 0.0 <= p <= 1.0

    def test_att_prob_higher_tn_lower_chance(self) -> None:
        c = make_combatant(fire=4, attack=4)
        p_low = c.att_prob("attack", 10)
        p_high = c.att_prob("attack", 30)
        assert p_low > p_high


# ── Attack bonus and VP spending ─────────────────────────────────────


class TestAttBonus:
    """Tests for att_bonus — applying static bonuses after the roll."""

    def test_no_bonuses(self) -> None:
        attacker, defender = setup_combat_pair()
        assert attacker.att_bonus(20, 15) == 0

    def test_always_bonus_applied(self) -> None:
        attacker, defender = setup_combat_pair()
        attacker.always["attack"] = 5
        result = attacker.att_bonus(20, 15)
        assert result >= 5

    def test_auto_once_consumed(self) -> None:
        attacker, defender = setup_combat_pair()
        attacker.auto_once["attack"] = 5
        result = attacker.att_bonus(20, 10)
        assert result >= 5
        assert attacker.auto_once["attack"] == 0

    def test_disc_spent_to_meet_tn(self) -> None:
        attacker, defender = setup_combat_pair()
        attacker.disc["attack"].append(10)
        # Roll of 12, TN of 20, need 8 more. Disc has 10.
        result = attacker.att_bonus(20, 12)
        assert result == 10
        assert attacker.disc["attack"] == []

    def test_disc_not_spent_if_already_hit(self) -> None:
        attacker, defender = setup_combat_pair()
        attacker.disc["attack"].append(10)
        # Roll of 25, TN of 20. Already hit, no disc needed.
        result = attacker.att_bonus(20, 25)
        assert result == 0
        assert attacker.disc["attack"] == [10]


class TestAttVps:
    """Tests for att_vps — pre-committing VPs to attack rolls."""

    def test_no_spend_when_already_likely(self) -> None:
        """If base probability is already above threshold, spend 0."""
        attacker, defender = setup_combat_pair(fire=5, attack=5)
        attacker.attack_knack = "attack"
        # Very low TN — should be easy to hit.
        vps = attacker.att_vps(10, 10, 5)
        assert vps == 0

    def test_spend_reduces_vp_pool(self) -> None:
        attacker, defender = setup_combat_pair(fire=2, attack=2, void=3)
        attacker.attack_knack = "attack"
        initial_vps = attacker.vps
        # Very high TN — may need VPs.
        vps = attacker.att_vps(40, 4, 2)
        if vps > 0:
            assert attacker.vps == initial_vps - vps

    def test_no_spend_when_hopeless(self) -> None:
        """If even max VPs can't reach the threshold, don't waste."""
        attacker, _ = setup_combat_pair(fire=2, attack=1, void=1)
        attacker.attack_knack = "attack"
        attacker.vps = 1
        vps = attacker.att_vps(100, 3, 2)
        assert vps == 0

    def test_vps_spent_event_fires(self) -> None:
        attacker, defender = setup_combat_pair(fire=2, attack=2, void=4)
        attacker.attack_knack = "attack"
        spent_events = []
        attacker.events["vps_spent"].append(
            lambda vps, roll_type: spent_events.append((vps, roll_type))
        )
        vps = attacker.att_vps(30, 4, 2)
        if vps > 0:
            assert len(spent_events) == 1
            assert spent_events[0][1] == "attack"


# ── make_attack ──────────────────────────────────────────────────────


class TestMakeAttack:
    """Tests for the full make_attack method."""

    def test_hit_returns_true(self) -> None:
        attacker, defender = setup_combat_pair()
        # Force a high roll that will beat the TN.
        with patch.object(attacker, "xky", return_value=100):
            result = attacker.make_attack()
        assert result is True

    def test_miss_returns_false(self) -> None:
        attacker, defender = setup_combat_pair()
        with patch.object(attacker, "xky", return_value=1):
            result = attacker.make_attack()
        assert result is False

    def test_attack_roll_stored(self) -> None:
        attacker, defender = setup_combat_pair()
        with patch.object(attacker, "xky", return_value=25):
            attacker.make_attack()
        assert attacker.attack_roll >= 25

    def test_feint_hit_returns_false(self) -> None:
        """Feints don't deal damage even on a hit — they return False
        so the engine skips the damage/parry sequence."""
        attacker, defender = setup_combat_pair()
        attacker.attack_knack = "feint"
        with patch.object(attacker, "xky", return_value=100):
            result = attacker.make_attack()
        assert result is False

    def test_successful_attack_event_on_hit(self) -> None:
        attacker, defender = setup_combat_pair()
        triggered = []
        attacker.events["successful_attack"].append(
            lambda: triggered.append(True)
        )
        with patch.object(attacker, "xky", return_value=100):
            attacker.make_attack()
        assert triggered

    def test_no_successful_attack_event_on_miss(self) -> None:
        attacker, defender = setup_combat_pair()
        triggered = []
        attacker.events["successful_attack"].append(
            lambda: triggered.append(True)
        )
        with patch.object(attacker, "xky", return_value=1):
            attacker.make_attack()
        assert not triggered

    def test_feint_hit_still_fires_successful_attack(self) -> None:
        """Even though feint returns False, the successful_attack event
        still fires (that's how feint_trigger grants VP + action)."""
        attacker, defender = setup_combat_pair()
        attacker.attack_knack = "feint"
        triggered = []
        attacker.events["successful_attack"].append(
            lambda: triggered.append(True)
        )
        with patch.object(attacker, "xky", return_value=100):
            attacker.make_attack()
        assert triggered

    def test_bonus_applied_to_roll(self) -> None:
        """Always bonuses should increase the attack_roll beyond the
        raw xky result."""
        attacker, defender = setup_combat_pair()
        attacker.always["attack"] = 10
        with patch.object(attacker, "xky", return_value=15):
            attacker.make_attack()
        assert attacker.attack_roll == 25


# ── Parry dice and bonus ─────────────────────────────────────────────


class TestParryDice:
    """Tests for parry_dice and parry_bonus."""

    def test_parry_dice_basic(self) -> None:
        """Parry dice = (Air + parry_skill)k(Air)."""
        c = make_combatant(air=4, parry=3)
        roll, keep = c.parry_dice
        assert roll == 7
        assert keep == 4

    def test_parry_bonus_includes_predeclare(self) -> None:
        c = make_combatant()
        c.predeclare_bonus = 5
        c.enemy = make_combatant()
        c.enemy.attack_knack = "attack"
        result = c.parry_bonus(30, 20)
        assert result >= 5
        # predeclare_bonus is consumed.
        assert c.predeclare_bonus == 0

    def test_parry_bonus_always(self) -> None:
        c = make_combatant()
        c.predeclare_bonus = 0
        c.enemy = make_combatant()
        c.always["parry"] = 5
        result = c.parry_bonus(30, 20)
        assert result >= 5

    def test_parry_bonus_disc_spent_to_succeed(self) -> None:
        c = make_combatant()
        c.predeclare_bonus = 0
        c.enemy = make_combatant()
        c.disc["parry"].append(10)
        # Roll 20 vs TN 25, need 5 more. Disc 10 is enough.
        result = c.parry_bonus(25, 20)
        assert result == 10
        assert c.disc["parry"] == []


# ── make_parry ───────────────────────────────────────────────────────


class TestMakeParry:
    """Tests for the full make_parry method."""

    def _setup_parry(self, defender_kw=None, attack_roll=20):
        """Wire up a defender ready to call make_parry."""
        defender = make_combatant(**(defender_kw or {}))
        attacker = make_combatant()
        defender.enemy = attacker
        defender.predeclare_bonus = 0
        attacker.attack_roll = attack_roll
        attacker.attack_knack = "attack"
        return defender, attacker

    def test_successful_parry(self) -> None:
        defender, attacker = self._setup_parry(
            {"air": 5, "parry": 5}, attack_roll=20,
        )
        with patch.object(defender, "xky", return_value=30):
            result = defender.make_parry()
        assert result is True

    def test_failed_parry(self) -> None:
        defender, attacker = self._setup_parry(
            {"air": 2, "parry": 2}, attack_roll=50,
        )
        with patch.object(defender, "xky", return_value=10):
            result = defender.make_parry()
        assert result is False

    def test_auto_success(self) -> None:
        """auto_success=True forces parry to succeed regardless of
        roll."""
        defender, attacker = self._setup_parry(attack_roll=100)
        with patch.object(defender, "xky", return_value=1):
            result = defender.make_parry(auto_success=True)
        assert result is True

    def test_successful_parry_event_fires(self) -> None:
        defender, attacker = self._setup_parry(
            {"air": 5, "parry": 5}, attack_roll=10,
        )
        triggered = []
        defender.events["successful_parry"].append(
            lambda: triggered.append(True)
        )
        with patch.object(defender, "xky", return_value=30):
            defender.make_parry()
        assert triggered

    def test_failed_parry_no_event(self) -> None:
        defender, attacker = self._setup_parry(
            {"air": 2, "parry": 2}, attack_roll=50,
        )
        triggered = []
        defender.events["successful_parry"].append(
            lambda: triggered.append(True)
        )
        with patch.object(defender, "xky", return_value=1):
            defender.make_parry()
        assert not triggered

    def test_parry_roll_stored(self) -> None:
        defender, attacker = self._setup_parry(attack_roll=20)
        with patch.object(defender, "xky", return_value=15):
            defender.make_parry()
        assert defender.parry_roll >= 15


# ── make_parry_for ───────────────────────────────────────────────────


class TestMakeParryFor:
    """Tests for parrying on behalf of an adjacent ally."""

    def test_raises_attack_roll_by_knack_skill(self) -> None:
        """When parrying for an ally, the attack_roll is temporarily
        raised by 5 * attacker's knack skill, then restored."""
        ally = make_combatant()
        defender = make_combatant(air=5, parry=5)
        attacker = make_combatant(attack=3)
        defender.enemy = attacker
        defender.predeclare_bonus = 0
        attacker.attack_roll = 20
        attacker.attack_knack = "attack"

        with patch.object(defender, "xky", return_value=50):
            defender.make_parry_for(ally, attacker)

        # attack_roll should be restored after the call.
        assert attacker.attack_roll == 20

    def test_attack_roll_raised_proportional_to_skill(self) -> None:
        """Higher attacker skill means a bigger temporary raise to
        attack_roll during the parry-for attempt."""
        ally = make_combatant()
        defender = make_combatant(air=3, parry=3)
        attacker = make_combatant(attack=5)
        defender.enemy = attacker
        defender.predeclare_bonus = 0
        attacker.attack_roll = 20
        attacker.attack_knack = "attack"

        # Track the TN passed to make_parry by capturing the
        # parry_vps call's tn argument.
        seen_tns = []
        original_parry_vps = defender.parry_vps

        def tracking_parry_vps(tn, roll, keep):
            seen_tns.append(tn)
            return original_parry_vps(tn, roll, keep)

        with patch.object(defender, "xky", return_value=100):
            with patch.object(
                defender, "parry_vps", side_effect=tracking_parry_vps,
            ):
                defender.make_parry_for(ally, attacker)

        # parry_vps should have seen the raised attack_roll.
        # attack_roll=20 + 5*attack(5) = 45.
        assert seen_tns[0] == 45
        # But the original attack_roll is restored.
        assert attacker.attack_roll == 20


# ── will_parry ───────────────────────────────────────────────────────


class TestWillParry:
    """Tests for the parry decision heuristics."""

    def test_predeclare_always_parries(self) -> None:
        _, defender = setup_combat_pair()
        defender.predeclare_bonus = 5
        result = defender.will_parry()
        assert result is True

    def test_no_actions_no_parry(self) -> None:
        _, defender = setup_combat_pair()
        defender.predeclare_bonus = 0
        defender.actions = []
        result = defender.will_parry()
        assert result is False

    def test_single_future_action_no_parry(self) -> None:
        """One action in a future phase and no second action means
        can't afford interrupt cost."""
        _, defender = setup_combat_pair()
        defender.predeclare_bonus = 0
        defender.phase = 2
        defender.actions = [5]  # Only one action, in the future.
        result = defender.will_parry()
        assert result is False

    def test_normal_parry_consumes_action(self) -> None:
        """Normal parry (action ready in current phase) pops one
        action die."""
        attacker, defender = setup_combat_pair()
        defender.predeclare_bonus = 0
        defender.phase = 2
        defender.actions = [2, 6]
        # Force projected damage to make parry worthwhile.
        with patch.object(
            defender, "projected_damage", side_effect=[10, 0]
        ):
            defender.sw_parry_threshold = 1
            result = defender.will_parry()
        if result:
            assert len(defender.actions) == 1

    def test_interrupt_consumes_two_actions(self) -> None:
        """Interrupt parry (out-of-turn) costs 2 action dice from the
        end."""
        attacker, defender = setup_combat_pair()
        defender.predeclare_bonus = 0
        defender.phase = 1
        defender.actions = [3, 5]  # Both in future phases.
        # Lethal damage to force parry.
        with patch.object(
            defender, "projected_damage", side_effect=[20, 0]
        ):
            defender.serious = defender.sw_to_kill - 1
            result = defender.will_parry()
        if result:
            assert defender.actions == []
            assert defender.interrupt == "interrupt "


# ── will_predeclare ──────────────────────────────────────────────────


class TestWillPredeclare:
    """Tests for the base predeclare logic."""

    def test_base_never_predeclares(self) -> None:
        c = make_combatant()
        assert c.will_predeclare() is False

    def test_sets_predeclare_bonus_to_zero(self) -> None:
        c = make_combatant()
        c.predeclare_bonus = 5
        c.will_predeclare()
        assert c.predeclare_bonus == 0


# ── next_damage / deal_damage ────────────────────────────────────────


class TestDamage:
    """Tests for next_damage and deal_damage."""

    def test_next_damage_extra_true(self) -> None:
        """With extra_damage, bonus rolled dice from exceeding TN are
        added."""
        attacker, _ = setup_combat_pair(fire=3)
        attacker.attack_roll = 30
        # TN=20, exceeded by 10 -> +2 extra rolled dice.
        roll, keep, serious = attacker.next_damage(20, True)
        base_roll, base_keep = attacker.damage_dice
        assert roll == base_roll + 2
        assert keep == base_keep
        assert serious == 0

    def test_next_damage_extra_false(self) -> None:
        """Without extra_damage (failed parry), no bonus dice from
        exceeding TN."""
        attacker, _ = setup_combat_pair(fire=3)
        attacker.attack_roll = 30
        roll, keep, serious = attacker.next_damage(20, False)
        base_roll, base_keep = attacker.damage_dice
        assert roll == base_roll
        assert keep == base_keep
        assert serious == 0

    def test_next_damage_with_datt_bonus(self) -> None:
        """Double attack adds +4 rolled and +1 serious via auto_once.
        """
        attacker, _ = setup_combat_pair(fire=3)
        attacker.attack_knack = "double_attack"
        attacker.attack_roll = 25
        attacker.auto_once["damage_rolled"] = 4
        attacker.auto_once["serious"] = 1
        roll, keep, serious = attacker.next_damage(20, True)
        base_roll, _ = attacker.damage_dice
        # +1 from exceeding TN by 5, +4 from double attack.
        assert roll == base_roll + 1 + 4
        assert serious == 1

    def test_deal_damage_returns_light_and_serious(self) -> None:
        attacker, _ = setup_combat_pair()
        attacker.attack_roll = 20
        with patch.object(attacker, "xky", return_value=15):
            light, serious = attacker.deal_damage(20)
        assert light == 15
        assert serious == 0

    def test_deal_damage_stores_last_damage_rolled(self) -> None:
        attacker, _ = setup_combat_pair()
        attacker.attack_roll = 20
        with patch.object(attacker, "xky", return_value=15):
            attacker.deal_damage(20)
        assert hasattr(attacker, "last_damage_rolled")

    def test_deal_damage_includes_auto_once_damage(self) -> None:
        """Flat damage from auto_once["damage"] is added to light."""
        attacker, _ = setup_combat_pair()
        attacker.attack_roll = 20
        attacker.auto_once["damage"] = 5
        with patch.object(attacker, "xky", return_value=15):
            light, _ = attacker.deal_damage(20)
        assert light == 20  # 15 + 5


# ── reset_damage in post_attack ──────────────────────────────────────


class TestResetDamageInEventCycle:
    """Tests that reset_damage fires on post_attack and cleans up
    damage auto_once bonuses."""

    def test_reset_damage_fires_on_post_attack(self) -> None:
        attacker, _ = setup_combat_pair()
        attacker.auto_once["damage_rolled"] = 4
        attacker.auto_once["damage_kept"] = 1
        attacker.auto_once["damage"] = 10
        attacker.triggers("post_attack")
        assert attacker.auto_once["damage_rolled"] == 0
        assert attacker.auto_once["damage_kept"] == 0
        assert attacker.auto_once["damage"] == 0

    def test_serious_not_cleared_by_reset_damage(self) -> None:
        """The 'serious' auto_once bonus is consumed in next_damage,
        not by reset_damage. Verify reset_damage doesn't touch it."""
        attacker, _ = setup_combat_pair()
        attacker.auto_once["serious"] = 1
        attacker.triggers("post_attack")
        # reset_damage only clears damage_rolled/kept/damage.
        assert attacker.auto_once["serious"] == 1


# ── Initiative ───────────────────────────────────────────────────────


class TestInitiative:
    """Tests for the initiative roll."""

    def test_actions_sorted_ascending(self) -> None:
        c = make_combatant(void=3)
        with patch("l7r.combatant.d10", side_effect=[7, 2, 9, 4]):
            c.initiative()
        # Roll 4, keep 3 (void=3). Sorted: [2, 4, 7, 9], keep 3.
        assert c.actions == [2, 4, 7]

    def test_init_order_is_copy(self) -> None:
        """init_order is a snapshot; modifying actions doesn't affect
        it."""
        c = make_combatant(void=2)
        with patch("l7r.combatant.d10", side_effect=[5, 3, 8]):
            c.initiative()
        original = c.init_order[:]
        c.actions.pop()
        assert c.init_order == original

    def test_keeps_void_lowest(self) -> None:
        """Keeps the lowest dice (for earliest action)."""
        c = make_combatant(void=2)
        with patch("l7r.combatant.d10", side_effect=[10, 1, 5]):
            c.initiative()
        assert c.actions == [1, 5]


# ── choose_action ────────────────────────────────────────────────────


class TestChooseAction:
    """Tests for the heuristic action selection."""

    def _make_enemy(self) -> Combatant:
        """Create an enemy combatant with the attributes att_target
        needs."""
        e = make_combatant()
        e.init_order = [5]
        e.actions = [5]
        return e

    def test_acts_when_action_ready(self) -> None:
        c = make_combatant()
        c.hold_one_action = False
        c.phase = 3
        c.actions = [3, 7]
        c.init_order = [3, 7]
        c.attackable = {self._make_enemy()}
        result = c.choose_action()
        assert result is not None
        knack, target = result
        assert knack in ("attack", "double_attack")

    def test_passes_when_no_ready_action(self) -> None:
        c = make_combatant()
        c.phase = 2
        c.actions = [5, 8]
        c.init_order = [5, 8]
        c.attackable = {self._make_enemy()}
        assert c.choose_action() is None

    def test_passes_when_no_actions(self) -> None:
        c = make_combatant()
        c.phase = 5
        c.actions = []
        c.init_order = []
        c.attackable = {self._make_enemy()}
        assert c.choose_action() is None

    def test_hold_one_action_for_parry(self) -> None:
        """With hold_one_action=True, won't spend last action unless
        phase 10 or a second action is ready."""
        c = make_combatant()
        c.hold_one_action = True
        c.phase = 3
        c.actions = [3]  # Only one action, ready now.
        c.init_order = [3]
        c.attackable = {self._make_enemy()}
        # Not phase 10, only 1 action -> hold it.
        assert c.choose_action() is None

    def test_spend_last_action_at_phase_10(self) -> None:
        """At phase 10, use-it-or-lose-it — even the last action."""
        c = make_combatant()
        c.hold_one_action = True
        c.phase = 10
        c.actions = [3]
        c.init_order = [3]
        c.attackable = {self._make_enemy()}
        assert c.choose_action() is not None

    def test_consumes_action_die(self) -> None:
        c = make_combatant()
        c.hold_one_action = False
        c.phase = 3
        c.actions = [3, 7]
        c.init_order = [3, 7]
        c.attackable = {self._make_enemy()}
        c.choose_action()
        assert c.actions == [7]

    def test_prefers_double_attack_when_close(self) -> None:
        """When double_attack probability is close to normal attack
        probability, prefer double attack for the bonus damage."""
        c = make_combatant(fire=5, attack=5)
        c.double_attack = 5
        c.hold_one_action = False
        c.phase = 3
        c.actions = [3, 7]
        c.init_order = [3, 7]
        c.attackable = {self._make_enemy()}
        # Force att_prob to return similar values.
        with patch.object(
            c, "att_prob", side_effect=lambda knack, tn: 0.8
        ):
            knack, _ = c.choose_action()
        assert knack == "double_attack"

    def test_prefers_normal_when_datt_much_worse(self) -> None:
        """When double attack probability drops significantly, stick
        with normal attack."""
        c = make_combatant(fire=3, attack=3)
        c.double_attack = 1
        c.hold_one_action = False
        c.phase = 3
        c.actions = [3, 7]
        c.init_order = [3, 7]
        c.attackable = {self._make_enemy()}
        # Normal = 0.8, double = 0.3. Gap = 0.5 >> threshold.
        with patch.object(c, "att_prob", side_effect=[0.3, 0.8]):
            knack, _ = c.choose_action()
        assert knack == "attack"


# ── Full pre_attack/post_attack cycle ────────────────────────────────


class TestFullEventCycle:
    """Integration tests verifying that a complete pre_attack ->
    make_attack -> post_attack cycle leaves no stale state."""

    def test_normal_attack_cycle(self) -> None:
        """Normal attack: no TN mutation, damage bonuses cleared."""
        attacker, defender = setup_combat_pair()
        original_tn = defender.tn

        attacker.triggers("pre_attack")
        with patch.object(attacker, "xky", return_value=25):
            attacker.make_attack()
        attacker.triggers("post_attack")

        assert defender.tn == original_tn
        assert attacker.auto_once["damage_rolled"] == 0
        assert attacker.auto_once["damage_kept"] == 0
        assert attacker.auto_once["damage"] == 0

    def test_double_attack_cycle_hit(self) -> None:
        """Double attack hit: TN raised +20 during attack, restored
        after. Damage bonuses set on hit, cleared on post_attack."""
        attacker, defender = setup_combat_pair()
        attacker.attack_knack = "double_attack"
        attacker.double_attack = 3
        original_tn = defender.tn

        attacker.triggers("pre_attack")
        assert defender.tn == original_tn + 20

        with patch.object(attacker, "xky", return_value=100):
            hit = attacker.make_attack()
        assert hit is True
        # successful_attack fired: bonus damage set.
        assert attacker.auto_once["serious"] == 1
        assert attacker.auto_once["damage_rolled"] == 4

        attacker.triggers("post_attack")
        assert defender.tn == original_tn
        assert attacker.auto_once["damage_rolled"] == 0

    def test_double_attack_cycle_miss(self) -> None:
        """Double attack miss: TN still restored, no damage bonuses.
        """
        attacker, defender = setup_combat_pair()
        attacker.attack_knack = "double_attack"
        attacker.double_attack = 3
        original_tn = defender.tn

        attacker.triggers("pre_attack")
        with patch.object(attacker, "xky", return_value=1):
            hit = attacker.make_attack()
        assert hit is False
        attacker.triggers("post_attack")

        assert defender.tn == original_tn
        assert attacker.auto_once["serious"] == 0

    def test_lunge_cycle(self) -> None:
        """Lunge: attacker TN drops -5 on pre_attack, restored on
        post_defense. Damage rolled bonus set on pre_attack."""
        attacker, defender = setup_combat_pair()
        attacker.attack_knack = "lunge"
        attacker.lunge = 2
        original_tn = attacker.tn

        attacker.triggers("pre_attack")
        assert attacker.tn == original_tn - 5
        assert attacker.auto_once["damage_rolled"] == 1

        # Simulate attack, then post_defense to trigger reset.
        with patch.object(attacker, "xky", return_value=100):
            attacker.make_attack()
        attacker.triggers("post_defense")
        assert attacker.tn == original_tn
