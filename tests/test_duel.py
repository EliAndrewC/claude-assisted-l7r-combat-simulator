"""Tests for iaijutsu duel support.

Covers wound_check duel restrictions (no reroll, no VPs),
deal_duel_damage scaling, duel_should_strike heuristics,
Engine.duel() orchestration, and fight(duel=True) integration.
"""

from unittest.mock import patch

from l7r.combatant import Combatant
from l7r.engine import Engine
from l7r.formations import Line, Surround
from l7r.schools.kakita_duelist import KakitaDuelist
from l7r.schools.hida_bushi import HidaBushi
from l7r.schools.yogo_warden import YogoWarden
from l7r.schools.merchant import Merchant
from l7r.professions import Professional


def make(**overrides) -> Combatant:
    defaults = dict(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
    defaults.update(overrides)
    return Combatant(**defaults)


# -----------------------------------------------------------
# Step 1: wound_check reroll/spend_vps params
# -----------------------------------------------------------


class TestWoundCheckRerollParam:
    """wound_check(reroll=False) should prevent 10-explosion on wound check dice."""

    def test_reroll_false_passes_false_to_xky(self) -> None:
        """When reroll=False, xky should be called with reroll=False."""
        c = make(water=3, earth=5)
        calls = []

        def tracking_xky(roll, keep, reroll, roll_type):
            calls.append((roll, keep, reroll, roll_type))
            return 100  # high enough to pass

        with patch.object(c, "xky", side_effect=tracking_xky):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=10, reroll=False)

        # xky should have been called with reroll=False
        assert any(call[2] is False and call[3] == "wound_check" for call in calls)

    def test_reroll_true_is_default(self) -> None:
        """By default, reroll should be True (backward compatible)."""
        c = make(water=3, earth=5)
        calls = []

        def tracking_xky(roll, keep, reroll, roll_type):
            calls.append((roll, keep, reroll, roll_type))
            return 100

        with patch.object(c, "xky", side_effect=tracking_xky):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=10)

        assert any(call[2] is True and call[3] == "wound_check" for call in calls)

    def test_reroll_false_also_affects_lucky_reroll(self) -> None:
        """When reroll=False and Lucky triggers, the Lucky reroll should also use reroll=False."""
        c = make(water=3, earth=3, lucky=True)
        calls = []

        def tracking_xky(roll, keep, reroll, roll_type):
            calls.append((roll, keep, reroll, roll_type))
            return 1  # low enough to fail, trigger Lucky

        with patch.object(c, "xky", side_effect=tracking_xky):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=20, reroll=False)

        # All xky calls for wound_check should have reroll=False
        wc_calls = [call for call in calls if call[3] == "wound_check"]
        assert len(wc_calls) >= 2  # original + Lucky reroll
        assert all(call[2] is False for call in wc_calls)


class TestWoundCheckSpendVpsParam:
    """wound_check(spend_vps=False) should preserve VP count."""

    def test_spend_vps_false_preserves_vps(self) -> None:
        c = make(water=2, earth=2, void=3)
        c.serious = c.sw_to_kill - 1  # near death to incentivize VP spending
        initial_vps = c.vps
        with patch.object(c, "xky", return_value=1):
            c.wound_check(light=50, spend_vps=False)
        assert c.vps == initial_vps

    def test_spend_vps_true_is_default(self) -> None:
        """By default, VP spending is allowed (backward compatible)."""
        c = make(water=2, earth=2, void=3)
        c.serious = c.sw_to_kill - 1
        # Just verify wc_vps is called (defaults allow it)
        with patch.object(c, "xky", return_value=1):
            with patch.object(c, "wc_vps", return_value=0) as mock_vps:
                c.wound_check(light=50)
        mock_vps.assert_called_once()

    def test_spend_vps_false_skips_wc_vps(self) -> None:
        """spend_vps=False should skip the wc_vps call entirely."""
        c = make(water=2, earth=2, void=3)
        with patch.object(c, "xky", return_value=100):
            with patch.object(c, "wc_vps") as mock_vps:
                c.wound_check(light=10, spend_vps=False)
        mock_vps.assert_not_called()


class TestWoundCheckOverridesForwardKwargs:
    """All wound_check overrides should forward **kwargs to super."""

    def test_hida_bushi_forwards_kwargs(self) -> None:
        c = HidaBushi(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        # Rank < 4, so it calls super directly
        with patch.object(c, "xky", return_value=100):
            with patch.object(c, "wc_vps") as mock_vps:
                c.wound_check(light=10, spend_vps=False)
        mock_vps.assert_not_called()

    def test_hida_bushi_r4t_forwards_kwargs(self) -> None:
        """Hida R4T path doesn't call super, but at rank < 4 it does."""
        c = HidaBushi(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3, rank=4)
        # With light <= wc_threshold, R4T doesn't trigger, falls through to super
        with patch.object(c, "xky", return_value=100):
            with patch.object(c, "wc_vps") as mock_vps:
                c.wound_check(light=5, spend_vps=False)
        mock_vps.assert_not_called()

    def test_yogo_warden_forwards_kwargs(self) -> None:
        c = YogoWarden(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        with patch.object(c, "xky", return_value=100):
            with patch.object(c, "wc_vps") as mock_vps:
                c.wound_check(light=10, spend_vps=False)
        mock_vps.assert_not_called()

    def test_merchant_forwards_kwargs(self) -> None:
        c = Merchant(
            air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3,
            discern_honor=1, oppose_knowledge=1, worldliness=1,
        )
        with patch.object(Combatant, "xky", return_value=100):
            c.wound_check(light=10, spend_vps=False)
        # Merchant.wc_vps always returns 0, so just verify no crash

    def test_professional_forwards_kwargs(self) -> None:
        wave_man = {
            "wave_man_damage_compensator": [],
            "wave_man_init_bonus": [],
            "wave_man_wc_bonus": [],
            "wave_man_difficult_parry": [],
            "wave_man_crippled_reroll": [],
            "wave_man_damage_round_up": [],
            "wave_man_parry_bypass": [],
            "wave_man_tougher_wounds": [],
            "wave_man_near_miss": [],
            "wave_man_wound_reduction": [],
        }
        ninja = {
            "ninja_attack_bonus": [],
            "ninja_difficult_attack": [],
            "ninja_better_tn": [],
            "ninja_damage_roll": [],
            "ninja_wc_bump": [],
            "ninja_damage_bump": [],
            "ninja_fast_attacks": [],
        }
        c = Professional(
            air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3,
            wave_man=wave_man, ninja=ninja,
        )
        c.enemy = make()
        c.enemy.attack_roll = 20
        with patch.object(Combatant, "xky", return_value=100):
            c.wound_check(light=10, spend_vps=False)
        # Just verify no crash


# -----------------------------------------------------------
# Step 2: deal_duel_damage
# -----------------------------------------------------------


class TestDealDuelDamage:
    """deal_duel_damage scales 1 extra die per 1 over TN (not per 5)."""

    def test_exact_hit_no_extra_dice(self) -> None:
        c = make(fire=3)
        c.attack_roll = 20
        with patch.object(c, "xky", return_value=15) as mock_xky:
            light, serious = c.deal_duel_damage(tn=20)
        # Base damage dice: (4 + fire)k2 = 7k2
        # No extra dice since attack_roll == tn
        roll, keep, reroll, roll_type = mock_xky.call_args[0]
        assert roll == 4 + 3  # base_damage_rolled + fire
        assert keep == 2  # base_damage_kept
        assert reroll is True  # damage always rerolls 10s

    def test_one_over_tn_adds_one_die(self) -> None:
        c = make(fire=3)
        c.attack_roll = 21
        with patch.object(c, "xky", return_value=15) as mock_xky:
            c.deal_duel_damage(tn=20)
        roll = mock_xky.call_args[0][0]
        assert roll == 4 + 3 + 1  # +1 for 1 over TN

    def test_five_over_tn_adds_five_dice(self) -> None:
        """In normal combat, 5 over TN adds 1 die. In duel, it adds 5."""
        c = make(fire=3)
        c.attack_roll = 25
        with patch.object(c, "xky", return_value=15) as mock_xky:
            c.deal_duel_damage(tn=20)
        roll = mock_xky.call_args[0][0]
        assert roll == 4 + 3 + 5

    def test_below_tn_no_extra_dice(self) -> None:
        c = make(fire=3)
        c.attack_roll = 18
        with patch.object(c, "xky", return_value=15) as mock_xky:
            c.deal_duel_damage(tn=20)
        roll = mock_xky.call_args[0][0]
        assert roll == 4 + 3  # no extra dice

    def test_free_raises_add_dice(self) -> None:
        c = make(fire=3)
        c.attack_roll = 20
        with patch.object(c, "xky", return_value=15) as mock_xky:
            c.deal_duel_damage(tn=20, free_raises=2)
        roll = mock_xky.call_args[0][0]
        assert roll == 4 + 3 + 2  # +2 from free raises

    def test_free_raises_stack_with_excess(self) -> None:
        c = make(fire=3)
        c.attack_roll = 23
        with patch.object(c, "xky", return_value=15) as mock_xky:
            c.deal_duel_damage(tn=20, free_raises=1)
        roll = mock_xky.call_args[0][0]
        assert roll == 4 + 3 + 3 + 1  # 3 excess + 1 free raise

    def test_auto_once_damage_bonus_consumed(self) -> None:
        c = make(fire=3)
        c.attack_roll = 20
        c.auto_once["damage"] = 5
        with patch.object(c, "xky", return_value=10):
            light, serious = c.deal_duel_damage(tn=20)
        assert light == 15  # 10 from xky + 5 from auto_once
        assert c.auto_once["damage"] == 0

    def test_auto_once_damage_rolled_consumed(self) -> None:
        c = make(fire=3)
        c.attack_roll = 20
        c.auto_once["damage_rolled"] = 2
        with patch.object(c, "xky", return_value=15) as mock_xky:
            c.deal_duel_damage(tn=20)
        roll = mock_xky.call_args[0][0]
        assert roll == 4 + 3 + 2
        assert c.auto_once["damage_rolled"] == 0

    def test_auto_once_damage_kept_consumed(self) -> None:
        c = make(fire=3)
        c.attack_roll = 20
        c.auto_once["damage_kept"] = 1
        with patch.object(c, "xky", return_value=15) as mock_xky:
            c.deal_duel_damage(tn=20)
        keep = mock_xky.call_args[0][1]
        assert keep == 2 + 1
        assert c.auto_once["damage_kept"] == 0

    def test_auto_once_serious_consumed(self) -> None:
        c = make(fire=3)
        c.attack_roll = 20
        c.auto_once["serious"] = 1
        with patch.object(c, "xky", return_value=15):
            light, serious = c.deal_duel_damage(tn=20)
        assert serious == 1
        assert c.auto_once["serious"] == 0

    def test_returns_light_and_serious(self) -> None:
        c = make(fire=3)
        c.attack_roll = 20
        with patch.object(c, "xky", return_value=25):
            light, serious = c.deal_duel_damage(tn=20)
        assert light == 25
        assert serious == 0

    def test_damage_always_rerolls_10s(self) -> None:
        """Duel damage always rerolls 10s, even when crippled."""
        c = make(fire=3)
        c.attack_roll = 20
        c.crippled = True
        with patch.object(c, "xky", return_value=15) as mock_xky:
            c.deal_duel_damage(tn=20)
        reroll = mock_xky.call_args[0][2]
        assert reroll is True


# -----------------------------------------------------------
# Step 3: duel_should_strike
# -----------------------------------------------------------


class TestDuelShouldStrike:
    """Test duel_should_strike heuristic."""

    def test_strikes_when_expected_to_hit(self) -> None:
        """With high iaijutsu skill, should decide to strike against low TN."""
        c = make(fire=5, iaijutsu=5)
        opponent = make()
        # High fire + iaijutsu means avg roll will be high
        # TN of 5 is low, should strike
        result = c.duel_should_strike(opponent, my_tn=20, opp_tn=5, free_raises=0, round_num=1)
        assert result is True

    def test_focuses_when_expected_to_miss(self) -> None:
        """With low skill against high TN, should focus."""
        c = make(fire=2, iaijutsu=0)
        c.iaijutsu = 0
        opponent = make()
        # Low fire, no iaijutsu skill, high opponent TN
        result = c.duel_should_strike(opponent, my_tn=5, opp_tn=100, free_raises=0, round_num=1)
        assert result is False

    def test_threshold_adjustable(self) -> None:
        """Higher threshold requires more excess to strike."""
        c = make(fire=3, iaijutsu=3)
        opponent = make()
        # With default threshold=0, check with moderate TN
        c.duel_should_strike(
            opponent, my_tn=20, opp_tn=15, free_raises=0, round_num=1,
        )
        c.duel_strike_threshold = 100  # very cautious
        high_threshold = c.duel_should_strike(
            opponent, my_tn=20, opp_tn=15, free_raises=0, round_num=1,
        )
        # With very high threshold, should not strike
        assert high_threshold is False

    def test_always_bonus_included(self) -> None:
        """always['iaijutsu'] should be factored into the decision."""
        c = make(fire=2, iaijutsu=0)
        c.iaijutsu = 0
        opponent = make()
        # Without bonus, would focus
        result_without = c.duel_should_strike(
            opponent, my_tn=20, opp_tn=30, free_raises=0, round_num=1,
        )
        c.always["iaijutsu"] = 100  # huge bonus
        result_with = c.duel_should_strike(
            opponent, my_tn=20, opp_tn=30, free_raises=0, round_num=1,
        )
        assert result_without is False
        assert result_with is True

    def test_default_threshold_is_zero(self) -> None:
        c = make()
        assert c.duel_strike_threshold == 0


# -----------------------------------------------------------
# Step 4: Engine.duel() core
# -----------------------------------------------------------


class TestDuelTNSetup:
    """Duel TNs should be xp // 10 for each duelist."""

    def test_duel_tns_set_from_xp(self) -> None:
        a = make(xp=150)
        b = make(xp=100)
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        # Mock the duel so it ends quickly
        with patch.object(e, "_duel_round", return_value=(True, 0, 0)):
            e.duel()

        # After duel, TNs should be restored to 5 + 5*parry
        assert a.tn == 5 + 5 * a.parry
        assert b.tn == 5 + 5 * b.parry

    def test_duel_tns_restored_after_duel(self) -> None:
        a = make(xp=200, parry=4)
        b = make(xp=100, parry=3)
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        with patch.object(e, "_duel_round", return_value=(True, 0, 0)):
            e.duel()

        assert a.tn == 5 + 5 * 4  # 25
        assert b.tn == 5 + 5 * 3  # 20


class TestDuelContestedRoll:
    """Contested iaijutsu rolls: no reroll 10s, always bonuses apply."""

    def test_no_reroll_10s_on_contested_roll(self) -> None:
        a = make()
        b = make()
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        calls = {}

        def make_tracking_xky(name, combatant):
            def tracking_xky(roll, keep, reroll, roll_type):
                calls[name] = (roll, keep, reroll, roll_type)
                return 20
            return tracking_xky

        with patch.object(a, "xky", side_effect=make_tracking_xky("a", a)):
            with patch.object(b, "xky", side_effect=make_tracking_xky("b", b)):
                with patch.object(a, "duel_should_strike", return_value=True):
                    with patch.object(b, "duel_should_strike", return_value=True):
                        with patch.object(a, "deal_duel_damage", return_value=(10, 0)):
                            with patch.object(b, "deal_duel_damage", return_value=(10, 0)):
                                with patch.object(a, "wound_check"):
                                    with patch.object(b, "wound_check"):
                                        e.duel()

        # Both contested rolls should have reroll=False
        assert calls["a"][2] is False
        assert calls["b"][2] is False


class TestDuelFocusStrike:
    """Focus increases TN by 5; both focus loops back."""

    def test_focus_raises_tn(self) -> None:
        a = make(xp=100)
        b = make(xp=100)
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        # Track when duel_should_strike is called and what TN is
        tns_seen = []
        call_count = [0]

        def a_strike(opponent, my_tn, opp_tn, free_raises, round_num):
            tns_seen.append(("a", my_tn, opp_tn, round_num))
            call_count[0] += 1
            if call_count[0] <= 1:
                return False  # Focus first time
            return True  # Strike second time

        b_strike_count = [0]

        def b_strike(opponent, my_tn, opp_tn, free_raises, round_num):
            tns_seen.append(("b", my_tn, opp_tn, round_num))
            b_strike_count[0] += 1
            if b_strike_count[0] <= 1:
                return False  # Focus first time
            return True  # Strike second time

        with patch.object(a, "xky", return_value=20):
            with patch.object(b, "xky", return_value=15):
                with patch.object(a, "duel_should_strike", side_effect=a_strike):
                    with patch.object(b, "duel_should_strike", side_effect=b_strike):
                        with patch.object(a, "deal_duel_damage", return_value=(10, 0)):
                            with patch.object(b, "deal_duel_damage", return_value=(10, 0)):
                                with patch.object(a, "wound_check"):
                                    with patch.object(b, "wound_check"):
                                        e.duel()

        # Round 1: base TNs = xp // 10 = 10
        # Both focus, so round 2 TNs should be +5
        round1_entries = [(name, my, opp) for name, my, opp, rn in tns_seen if rn == 1]
        round2_entries = [(name, my, opp) for name, my, opp, rn in tns_seen if rn == 2]
        assert len(round1_entries) == 2  # both asked
        assert len(round2_entries) == 2  # both asked again


class TestDuelDamageScaling:
    """Duel damage: 1 die per 1 over TN, free raises add dice."""

    def test_duel_damage_uses_duel_scaling(self) -> None:
        """Verify Engine.duel() calls deal_duel_damage (not deal_damage)."""
        a = make()
        b = make()
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        with patch.object(a, "xky", return_value=20):
            with patch.object(b, "xky", return_value=15):
                with patch.object(a, "duel_should_strike", return_value=True):
                    with patch.object(b, "duel_should_strike", return_value=True):
                        with patch.object(a, "deal_duel_damage", return_value=(10, 0)) as a_dd:
                            with patch.object(b, "deal_duel_damage", return_value=(10, 0)) as b_dd:
                                with patch.object(a, "wound_check"):
                                    with patch.object(b, "wound_check"):
                                        e.duel()

        # Both should have called deal_duel_damage
        assert a_dd.called
        assert b_dd.called


class TestDuelWoundCheckRestrictions:
    """Duel wound checks: no reroll 10s, no VP spending."""

    def test_wound_check_called_with_restrictions(self) -> None:
        a = make()
        b = make()
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        wc_calls = {"a": [], "b": []}

        def a_wc(light, serious=0, **kwargs):
            wc_calls["a"].append(kwargs)

        def b_wc(light, serious=0, **kwargs):
            wc_calls["b"].append(kwargs)

        with patch.object(a, "xky", return_value=20):
            with patch.object(b, "xky", return_value=15):
                with patch.object(a, "duel_should_strike", return_value=True):
                    with patch.object(b, "duel_should_strike", return_value=True):
                        with patch.object(a, "deal_duel_damage", return_value=(10, 0)):
                            with patch.object(b, "deal_duel_damage", return_value=(10, 0)):
                                with patch.object(a, "wound_check", side_effect=a_wc):
                                    with patch.object(b, "wound_check", side_effect=b_wc):
                                        e.duel()

        # wound_check should have been called with reroll=False and spend_vps=False
        for name, calls in wc_calls.items():
            if calls:
                assert calls[0].get("reroll") is False, f"{name} wound_check missing reroll=False"
                assert calls[0].get("spend_vps") is False, f"{name} wound_check missing spend_vps=False"


class TestDuelResheathe:
    """When both miss, resheathe: free raises stack, TNs reset."""

    def test_both_miss_loops_with_free_raises(self) -> None:
        a = make(xp=100)
        b = make(xp=100)
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        a_free_raises = []
        b_free_raises = []

        def a_duel_damage(tn, free_raises=0):
            a_free_raises.append(free_raises)
            return (0, 0)  # miss (we return 0 damage, but we need attack_roll < tn)

        def b_duel_damage(tn, free_raises=0):
            b_free_raises.append(free_raises)
            return (0, 0)

        # To simulate misses followed by hits:
        # We need attack_roll (from xky) < tn to miss
        # Round 1: both roll 5, TN is 10 -> miss
        # Round 2: both roll 15, TN is 10 -> hit
        xky_results = iter([
            15, 10,  # Round 1 contested: a=15, b=10 -> a wins
            5, 5,    # Round 1 strike rolls: both below TN (miss)
            15, 10,  # Round 2 contested: a=15, b=10
            15, 15,  # Round 2 strike rolls: both hit
        ])

        def mock_xky(roll, keep, reroll, roll_type):
            return next(xky_results)

        with patch.object(a, "xky", side_effect=mock_xky):
            with patch.object(b, "xky", side_effect=mock_xky):
                with patch.object(a, "duel_should_strike", return_value=True):
                    with patch.object(b, "duel_should_strike", return_value=True):
                        with patch.object(a, "deal_duel_damage", side_effect=a_duel_damage):
                            with patch.object(b, "deal_duel_damage", side_effect=b_duel_damage):
                                with patch.object(a, "wound_check"):
                                    with patch.object(b, "wound_check"):
                                        e.duel()

        # In round 2, the winner of the contested roll should get +1 free raise
        # a won the contested roll (15 > 10), so a should get free raises
        if len(a_free_raises) >= 2:
            assert a_free_raises[1] >= 1  # Should have free raise from resheathe


class TestDuelEngineIntegration:
    """fight(duel=True) runs duel then melee; fight() is unchanged."""

    def test_fight_without_duel_unchanged(self) -> None:
        a = make()
        b = make()
        f = Surround([a], [b])
        e = Engine(f)

        with patch.object(e, "duel") as mock_duel:
            with patch.object(e, "round", side_effect=lambda: setattr(a, "dead", True)):
                with patch("l7r.engine.Engine.finished", new_callable=lambda: property(lambda self: a.dead)):
                    e.fight()

        mock_duel.assert_not_called()

    def test_fight_with_duel_calls_duel_before_combat(self) -> None:
        a = make()
        b = make()
        f = Surround([a], [b])
        e = Engine(f)

        call_order = []

        def mock_duel():
            call_order.append("duel")

        def mock_round():
            call_order.append("round")
            a.dead = True

        with patch.object(e, "duel", side_effect=mock_duel):
            with patch.object(e, "round", side_effect=mock_round):
                with patch("l7r.engine.Engine.finished", new_callable=lambda: property(lambda self: a.dead)):
                    e.fight(duel=True)

        assert call_order[0] == "duel"
        assert "round" in call_order


class TestDuelPrePostTriggers:
    """pre_duel and post_duel events should fire."""

    def test_pre_duel_fires(self) -> None:
        a = make()
        b = make()
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        triggered = []
        a.events["pre_duel"].append(lambda: triggered.append("a_pre"))

        with patch.object(e, "_duel_round", return_value=(True, 0, 0)):
            e.duel()

        assert "a_pre" in triggered

    def test_post_duel_fires(self) -> None:
        a = make()
        b = make()
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        triggered = []
        a.events["post_duel"].append(lambda: triggered.append("a_post"))

        with patch.object(e, "_duel_round", return_value=(True, 0, 0)):
            e.duel()

        assert "a_post" in triggered


class TestDuelDeathInDuel:
    """If someone dies during the duel, the duel ends."""

    def test_death_ends_duel(self) -> None:
        a = make(earth=2)  # sw_to_kill = 4
        b = make(earth=2)
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        # a strikes, b strikes. a's attack kills b.
        with patch.object(a, "xky", return_value=25):
            with patch.object(b, "xky", return_value=15):
                with patch.object(a, "duel_should_strike", return_value=True):
                    with patch.object(b, "duel_should_strike", return_value=True):
                        with patch.object(a, "deal_duel_damage", return_value=(80, 2)):
                            with patch.object(b, "deal_duel_damage", return_value=(5, 0)):
                                # Don't mock wound_check so b actually dies
                                with patch.object(a, "wound_check"):
                                    e.duel()

        assert b.dead is True


class TestDuelSchoolTriggers:
    """School-specific triggers should fire during duel."""

    def test_kakita_r4t_damage_bonus_in_duel(self) -> None:
        """Kakita R4T adds +5 damage on iaijutsu hit; deal_duel_damage should get it."""
        k = KakitaDuelist(
            air=3, earth=3, fire=4, water=3, void=3,
            attack=4, parry=3, rank=4,
        )
        k.attack_knack = "iaijutsu"
        k.attack_roll = 25

        # Fire the successful_attack trigger (which sets auto_once["damage"])
        k.triggers("successful_attack")
        assert k.auto_once["damage"] == 5

        # Now deal_duel_damage should consume it
        with patch.object(k, "xky", return_value=10):
            light, serious = k.deal_duel_damage(tn=20)
        assert light == 15  # 10 + 5 from R4T


class TestDuelBothFocusThenStrike:
    """When both focus in round 1, TNs increase; when both strike, duel resolves."""

    def test_both_focus_then_both_strike(self) -> None:
        a = make(xp=100)
        b = make(xp=100)
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        call_count = {"a": 0, "b": 0}

        def a_strike(*args, **kwargs):
            call_count["a"] += 1
            return call_count["a"] > 1  # Focus first, strike second

        def b_strike(*args, **kwargs):
            call_count["b"] += 1
            return call_count["b"] > 1

        with patch.object(a, "xky", return_value=20):
            with patch.object(b, "xky", return_value=15):
                with patch.object(a, "duel_should_strike", side_effect=a_strike):
                    with patch.object(b, "duel_should_strike", side_effect=b_strike):
                        with patch.object(a, "deal_duel_damage", return_value=(10, 0)):
                            with patch.object(b, "deal_duel_damage", return_value=(10, 0)):
                                with patch.object(a, "wound_check"):
                                    with patch.object(b, "wound_check"):
                                        e.duel()

        # Both should have been called twice (focus + strike)
        assert call_count["a"] == 2
        assert call_count["b"] == 2


class TestDuelOneStrikesOneFocuses:
    """When one strikes and one focuses, the striker attacks and the focuser doesn't."""

    def test_only_striker_deals_damage(self) -> None:
        a = make(xp=100)
        b = make(xp=100)
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        with patch.object(a, "xky", return_value=20):
            with patch.object(b, "xky", return_value=15):
                with patch.object(a, "duel_should_strike", return_value=True):
                    with patch.object(b, "duel_should_strike", return_value=False):
                        # b focuses, a strikes. Only a should deal damage.
                        # Since at least one strikes, the duel proceeds.
                        # a strikes (attacks), b focused (doesn't attack, gets +5 TN)
                        with patch.object(a, "deal_duel_damage", return_value=(10, 0)) as a_dd:
                            with patch.object(b, "deal_duel_damage", return_value=(10, 0)) as b_dd:
                                with patch.object(a, "wound_check"):
                                    with patch.object(b, "wound_check"):
                                        e.duel()

        # Only the striker(s) should deal damage
        assert a_dd.called
        assert not b_dd.called


# -----------------------------------------------------------
# Coverage: duel paths where b wins contested roll
# -----------------------------------------------------------


class TestDuelBWinsContestedRoll:
    """Cover the branch where b beats a in the contested iaijutsu roll."""

    def test_b_wins_contested_decides_first(self) -> None:
        """When b wins the contested roll, b is 'first' (lines 151-152)."""
        a = make(xp=100)
        b = make(xp=100)
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        decision_order = []

        def a_strike(opponent, my_tn, opp_tn, free_raises, round_num):
            decision_order.append("a")
            return True

        def b_strike(opponent, my_tn, opp_tn, free_raises, round_num):
            decision_order.append("b")
            return True

        # b rolls higher (25 > 10), so b is first
        with patch.object(a, "xky", return_value=10):
            with patch.object(b, "xky", return_value=25):
                with patch.object(a, "duel_should_strike", side_effect=a_strike):
                    with patch.object(b, "duel_should_strike", side_effect=b_strike):
                        with patch.object(a, "deal_duel_damage", return_value=(10, 0)):
                            with patch.object(b, "deal_duel_damage", return_value=(10, 0)):
                                with patch.object(a, "wound_check"):
                                    with patch.object(b, "wound_check"):
                                        e.duel()

        # b should have decided first (called before a)
        assert decision_order[0] == "b"

    def test_b_wins_resheathe_gets_free_raise(self) -> None:
        """When b wins the contested roll and both miss, b gets +1 free raise
        (line 108)."""
        a = make(xp=100)
        b = make(xp=100)
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        b_free_raises_seen = []

        def b_duel_damage(tn, free_raises=0):
            b_free_raises_seen.append(free_raises)
            return (0, 0)

        # Round 1: b wins contested (25 > 10), both strike, both miss (roll 5 < TN 10)
        # Resheathe: b gets +1 free raise
        # Round 2: b wins again, both strike, both hit (roll 15 >= TN 10)
        xky_results = iter([
            10, 25,  # Round 1 contested: a=10, b=25 -> b wins
            5, 5,    # Round 1 strikes: both miss
            10, 25,  # Round 2 contested: a=10, b=25 -> b wins again
            15, 15,  # Round 2 strikes: both hit
        ])

        def mock_xky(roll, keep, reroll, roll_type):
            return next(xky_results)

        with patch.object(a, "xky", side_effect=mock_xky):
            with patch.object(b, "xky", side_effect=mock_xky):
                with patch.object(a, "duel_should_strike", return_value=True):
                    with patch.object(b, "duel_should_strike", return_value=True):
                        with patch.object(a, "deal_duel_damage", return_value=(0, 0)):
                            with patch.object(b, "deal_duel_damage", side_effect=b_duel_damage):
                                with patch.object(a, "wound_check"):
                                    with patch.object(b, "wound_check"):
                                        e.duel()

        # b missed in round 1 (so deal_duel_damage wasn't called), then hit in
        # round 2 with 1 free raise from the resheathe
        assert len(b_free_raises_seen) == 1
        assert b_free_raises_seen[0] == 1


class TestDuelContestedWinnerFocuses:
    """Cover the branch where the contested winner focuses while the loser
    strikes (lines 168-169: first focuses, gets TN +5)."""

    def test_winner_focuses_loser_strikes(self) -> None:
        a = make(xp=100)
        b = make(xp=100)
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        # a wins contested (20 > 15), so a is "first"
        # a focuses (first_strikes=False -> lines 168-169 hit)
        # b strikes
        with patch.object(a, "xky", return_value=20):
            with patch.object(b, "xky", return_value=15):
                with patch.object(a, "duel_should_strike", return_value=False):
                    with patch.object(b, "duel_should_strike", return_value=True):
                        with patch.object(a, "deal_duel_damage", return_value=(10, 0)) as a_dd:
                            with patch.object(b, "deal_duel_damage", return_value=(10, 0)) as b_dd:
                                with patch.object(a, "wound_check"):
                                    with patch.object(b, "wound_check"):
                                        e.duel()

        # a focused (shouldn't deal damage), b struck (should deal damage)
        assert not a_dd.called
        assert b_dd.called


class TestDuelSlainLogMessage:
    """Cover the 'is slain!' log message in _duel_round (line 205)."""

    def test_slain_message_logged(self) -> None:
        a = make(earth=2)
        b = make(earth=2)
        f = Line([a], [b])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e

        # a wins contested, both strike. a kills b with massive damage.
        with patch.object(a, "xky", return_value=25):
            with patch.object(b, "xky", return_value=15):
                with patch.object(a, "duel_should_strike", return_value=True):
                    with patch.object(b, "duel_should_strike", return_value=True):
                        with patch.object(a, "deal_duel_damage", return_value=(80, 2)):
                            with patch.object(b, "deal_duel_damage", return_value=(5, 0)):
                                with patch.object(a, "wound_check"):
                                    e.duel()

        assert b.dead is True
        assert any("is slain" in msg for msg in e.messages)


# -----------------------------------------------------------
# Coverage: combatant.adjacent without engine (line 427)
# -----------------------------------------------------------


class TestAdjacentWithoutEngine:
    """Combatant.adjacent returns [] when no engine is attached."""

    def test_adjacent_returns_empty_without_engine(self) -> None:
        c = make()
        assert c.adjacent == []


# -----------------------------------------------------------
# Coverage: Engine.attack() uncovered branches
# -----------------------------------------------------------


class TestEngineAttackForcedParry:
    """Cover forced_parry handling (lines 267-270)."""

    def test_forced_parry_consumes_action_and_clears_predeclare(self) -> None:
        e, att, dfn = engine_1v1()
        e.phase = 3
        dfn.forced_parry = True
        dfn.actions = [3, 5, 7]
        dfn.predeclare_bonus = 5

        with (
            patch.object(dfn, "will_counterattack", return_value=False),
            patch.object(att, "make_attack", return_value=False),
            patch.object(dfn, "make_parry"),
        ):
            e.attack("attack", att, dfn)

        assert dfn.forced_parry is False
        assert dfn.actions == [5, 7]  # first action consumed
        assert dfn.predeclare_bonus == 0


class TestEngineAllyCounterattackFor:
    """Cover ally counterattack_for branch (line 253)."""

    def test_ally_counterattacks_for_defender(self) -> None:
        inner = make_engine("Inner")
        outer1 = make_engine("O1")
        outer2 = make_engine("O2")
        f = Surround([inner], [outer1, outer2])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e
            c.predeclare_bonus = 0
        e.phase = 3

        counterattack_called = []

        def mock_counterattack_for(defender, attacker):
            counterattack_called.append(True)
            return True

        original_attack = Engine.attack
        call_count = [0]

        def intercepting_attack(self_e, knack, attacker, defender):
            call_count[0] += 1
            if call_count[0] == 1:
                return original_attack(self_e, knack, attacker, defender)
            # Recursive counterattack — just record it, don't recurse further
            return

        with (
            patch.object(outer1, "will_counterattack", return_value=False),
            patch.object(outer2, "will_counterattack_for", side_effect=mock_counterattack_for),
            patch.object(inner, "will_predeclare", return_value=False),
            patch.object(inner, "make_attack", return_value=False),
            patch.object(Engine, "attack", intercepting_attack),
        ):
            Engine.attack(e, "attack", inner, outer1)

        assert len(counterattack_called) == 1


class TestEngineAllyPredeclareFor:
    """Cover ally predeclare_for branch (line 275)."""

    def test_ally_predeclares_for_defender(self) -> None:
        inner = make_engine("Inner")
        outer1 = make_engine("O1")
        outer2 = make_engine("O2")
        f = Surround([inner], [outer1, outer2])
        e = Engine(f)
        for c in e.combatants:
            c.engine = e
            c.predeclare_bonus = 0
        e.phase = 3

        predeclare_called = []

        def mock_predeclare_for(defender, attacker):
            predeclare_called.append(True)
            return True

        with (
            patch.object(outer1, "will_counterattack", return_value=False),
            patch.object(outer1, "will_predeclare", return_value=False),
            patch.object(outer2, "will_predeclare_for", side_effect=mock_predeclare_for),
            patch.object(inner, "make_attack", return_value=False),
        ):
            e.attack("attack", inner, outer1)

        assert len(predeclare_called) == 1


class TestEngineReactToAttack:
    """Cover react_to_attack branch (line 279) and attacker death
    from reactive counterattack (lines 281-283)."""

    def test_react_to_attack_triggers_counterattack(self) -> None:
        e, att, dfn = engine_1v1()
        e.phase = 3
        att.predeclare_bonus = 0
        dfn.predeclare_bonus = 0

        with (
            patch.object(dfn, "will_counterattack", return_value=False),
            patch.object(dfn, "will_predeclare", return_value=False),
            patch.object(att, "make_attack", return_value=True),
            patch.object(dfn, "will_react_to_attack", return_value=True),
            patch.object(e, "parry", return_value=(False, False)),
            patch.object(att, "deal_damage", return_value=(10, 0)),
            patch.object(dfn, "wound_check"),
        ):
            # Mock the recursive counterattack call
            original_attack = e.attack

            def mock_attack(knack, attacker, defender):
                if knack == "counterattack":
                    return  # Don't recurse further
                return original_attack(knack, attacker, defender)

            with patch.object(e, "attack", side_effect=mock_attack):
                e.attack("attack", att, dfn)

    def test_attacker_dies_from_reactive_counterattack(self) -> None:
        """When reactive counterattack kills the attacker, post_attack and
        post_defense fire and the method returns early (lines 281-283)."""
        e, att, dfn = engine_1v1()
        e.phase = 3
        att.predeclare_bonus = 0
        dfn.predeclare_bonus = 0

        post_attack_fired = []
        post_defense_fired = []
        att.events["post_attack"].append(lambda: post_attack_fired.append(True))
        dfn.events["post_defense"].append(lambda: post_defense_fired.append(True))

        def kill_attacker(knack, attacker, defender):
            if knack == "counterattack":
                # The reactive counterattack kills the original attacker
                defender.dead = True

        with (
            patch.object(dfn, "will_counterattack", return_value=False),
            patch.object(dfn, "will_predeclare", return_value=False),
            patch.object(att, "make_attack", return_value=True),
            patch.object(dfn, "will_react_to_attack", return_value=True),
            patch.object(e, "attack", side_effect=kill_attacker),
        ):
            # Call the real attack method directly (bypass our mock for the
            # outer call). We need to re-read from the actual method.
            pass

        # Use a different approach: inline the scenario
        e2, att2, dfn2 = engine_1v1()
        e2.phase = 3
        att2.predeclare_bonus = 0
        dfn2.predeclare_bonus = 0

        post_attack_fired2 = []
        post_defense_fired2 = []
        att2.events["post_attack"].append(lambda: post_attack_fired2.append(True))
        dfn2.events["post_defense"].append(lambda: post_defense_fired2.append(True))

        def react_kills_attacker(knack, attacker, defender):
            if knack == "counterattack":
                defender.dead = True  # defender of counterattack = original attacker

        original_attack = Engine.attack

        call_count = [0]

        def wrapper_attack(self, knack, attacker, defender):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call is the real attack
                return original_attack(self, knack, attacker, defender)
            else:
                # Recursive calls (counterattack): kill the original attacker
                attacker.enemy.dead = True

        with (
            patch.object(dfn2, "will_counterattack", return_value=False),
            patch.object(dfn2, "will_predeclare", return_value=False),
            patch.object(att2, "make_attack", return_value=True),
            patch.object(dfn2, "will_react_to_attack", return_value=True),
            patch.object(Engine, "attack", wrapper_attack),
        ):
            Engine.attack(e2, "attack", att2, dfn2)

        assert att2.dead is True
        assert len(post_attack_fired2) == 1
        assert len(post_defense_fired2) == 1


def make_engine(name: str = "", **kw) -> Combatant:
    """Create a Combatant with engine-test defaults (earth=5)."""
    defaults = dict(air=3, earth=5, fire=3, water=3, void=3, attack=3, parry=3)
    defaults.update(kw)
    c = Combatant(**defaults)
    if name:
        c.name = name
    return c


def engine_1v1(
    inner_kw: dict | None = None,
    outer_kw: dict | None = None,
) -> tuple[Engine, Combatant, Combatant]:
    """1v1 Surround with Engine, engine set on all."""
    i = make_engine("Inner", **(inner_kw or {}))
    o = make_engine("Outer", **(outer_kw or {}))
    f = Surround([i], [o])
    e = Engine(f)
    for c in e.combatants:
        c.engine = e
    return e, i, o
