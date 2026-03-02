"""Tests for wound check logic: calc_serious, avg_serious, wound_check,
wc_bonus, wc_vps, and the related properties (sw_to_cripple, sw_to_kill,
wc_threshold).
"""

from unittest.mock import patch

from l7r.combatant import Combatant


def make_combatant(**overrides: int) -> Combatant:
    """Create a minimal Combatant for testing wound logic in isolation."""
    defaults = dict(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
    defaults.update(overrides)
    return Combatant(**defaults)


class TestCombatantProperties:
    """Tests for the derived properties that feed into wound math."""

    def test_sw_to_cripple_equals_earth(self) -> None:
        c = make_combatant(earth=4)
        assert c.sw_to_cripple == 4

    def test_sw_to_kill_equals_twice_earth(self) -> None:
        c = make_combatant(earth=4)
        assert c.sw_to_kill == 8

    def test_sw_to_kill_includes_extra_serious(self) -> None:
        c = make_combatant(earth=3, extra_serious=2)
        assert c.sw_to_kill == 8  # 2*3 + 2

    def test_wc_threshold_returns_base(self) -> None:
        c = make_combatant()
        assert c.wc_threshold == c.base_wc_threshold


class TestCalcSerious:
    """Tests for calc_serious — the pure math of wound check failure."""

    def test_check_equals_light_no_serious(self) -> None:
        """Exactly meeting the wound check means 0 serious wounds."""
        c = make_combatant()
        assert c.calc_serious(20, 20) == 0

    def test_check_exceeds_light_no_serious(self) -> None:
        c = make_combatant()
        assert c.calc_serious(15, 20) == 0

    def test_fail_by_1_takes_1_serious(self) -> None:
        """Failing by any amount up to 10 gives 1 serious wound."""
        c = make_combatant()
        assert c.calc_serious(21, 20) == 1

    def test_fail_by_10_takes_1_serious(self) -> None:
        c = make_combatant()
        assert c.calc_serious(30, 20) == 1

    def test_fail_by_11_takes_2_serious(self) -> None:
        """Every full 10 points of failure adds another serious wound."""
        c = make_combatant()
        assert c.calc_serious(31, 20) == 2

    def test_fail_by_20_takes_2_serious(self) -> None:
        c = make_combatant()
        assert c.calc_serious(40, 20) == 2

    def test_fail_by_21_takes_3_serious(self) -> None:
        c = make_combatant()
        assert c.calc_serious(41, 20) == 3

    def test_zero_light_zero_check(self) -> None:
        c = make_combatant()
        assert c.calc_serious(0, 0) == 0

    def test_accepts_float_check(self) -> None:
        """calc_serious takes float check for average-based estimates."""
        c = make_combatant()
        # 25 light, 20.5 check -> difference of 4.5 -> ceil(4.5/10) = 1
        assert c.calc_serious(25, 20.5) == 1


class TestAvgSerious:
    """Tests for avg_serious — expected serious wounds per VP spending level.

    avg_serious now returns float values via Monte Carlo lookup, so
    assertions use inequality/approximate checks instead of exact ints.
    """

    def test_returns_list_for_each_vp_level(self) -> None:
        c = make_combatant(water=3, void=2)
        # void=2, no worldliness -> entries for 0, 1, 2 VPs.
        result = c.avg_serious(light=30, roll=4, keep=3)
        assert len(result) == 3
        assert result[0][0] == 0
        assert result[1][0] == 1
        assert result[2][0] == 2

    def test_more_vps_fewer_wounds(self) -> None:
        """Spending more VPs should result in equal or fewer expected wounds."""
        c = make_combatant(water=3, void=4)
        result = c.avg_serious(light=40, roll=4, keep=3)
        for i in range(1, len(result)):
            assert result[i][1] <= result[i - 1][1]

    def test_zero_light_zero_wounds(self) -> None:
        c = make_combatant(water=3, void=2)
        result = c.avg_serious(light=0, roll=4, keep=3)
        for vps, wounds in result:
            assert wounds == 0.0


class TestWcBonus:
    """Tests for wc_bonus — deciding which static bonuses to apply."""

    def test_no_bonuses_returns_zero(self) -> None:
        c = make_combatant()
        assert c.wc_bonus(light=20, check=15)[0] == 0

    def test_always_bonus_applied(self) -> None:
        c = make_combatant()
        c.always["wound_check"] = 5
        result, _mods = c.wc_bonus(light=20, check=10)
        assert result >= 5

    def test_auto_once_consumed(self) -> None:
        c = make_combatant()
        c.auto_once["wound_check"] = 5
        result, _mods = c.wc_bonus(light=20, check=10)
        assert result >= 5
        assert c.auto_once["wound_check"] == 0

    def test_desperate_spends_disc(self) -> None:
        """When one serious wound from death, spend disc bonuses to survive.
        needed = max(0, light - check - bonus). disc_bonus only spends when
        a subset can meet the needed amount."""
        c = make_combatant(earth=3)
        c.serious = c.sw_to_kill - 1  # One from death.
        c.disc["wound_check"].extend([5, 10])
        # light=25, check=10 -> needed=15. [5,10] sums to 15, exactly enough.
        result, _mods = c.wc_bonus(light=25, check=10)
        assert result == 15
        assert c.disc["wound_check"] == []

    def test_desperate_no_spend_when_disc_insufficient(self) -> None:
        """When desperate but disc bonuses can't reach the needed amount,
        disc_bonus returns 0 (doesn't waste partial bonuses)."""
        c = make_combatant(earth=3)
        c.serious = c.sw_to_kill - 1
        c.disc["wound_check"].extend([5, 5])
        # light=50, check=10 -> needed=40. [5,5] can't reach 40.
        result, _mods = c.wc_bonus(light=50, check=10)
        assert result == 0
        assert c.disc["wound_check"] == [5, 5]

    def test_not_desperate_conservative(self) -> None:
        """When not near death, only spend enough disc to cross a 10-point
        wound threshold. needed = max(0, light - check - bonus - 9), so the
        gap must exceed 9 before any disc is spent."""
        c = make_combatant(earth=5)
        c.serious = 0
        c.disc["wound_check"].extend([5, 5, 5, 5])
        # light=25, check=14 -> needed = max(0, 25-14-0-9) = 2.
        # Smallest sufficient subset from [5,5,5,5] is (5,).
        result, _mods = c.wc_bonus(light=25, check=14)
        assert result == 5

    def test_not_desperate_no_spend_when_gap_small(self) -> None:
        """With a gap of 9 or less (after the -9 adjustment), no disc is spent.
        light=15, check=14 -> needed = max(0, 15-14-0-9) = 0."""
        c = make_combatant(earth=5)
        c.disc["wound_check"].extend([5, 5])
        result, _mods = c.wc_bonus(light=15, check=14)
        assert result == 0
        assert c.disc["wound_check"] == [5, 5]


class TestWcVps:
    """Tests for wc_vps — deciding how many VPs to spend on wound checks."""

    def test_no_vps_returns_zero(self) -> None:
        c = make_combatant(void=3)
        c.vps = 0
        roll, keep = c.wc_dice
        assert c.wc_vps(light=20, roll=roll, keep=keep) == 0

    def test_spending_reduces_vp_pool(self) -> None:
        """If VPs are spent, c.vps should decrease."""
        c = make_combatant(water=2, void=3, earth=2)
        c.serious = c.sw_to_kill - 1  # Near death — will want to spend.
        initial_vps = c.vps
        roll, keep = c.wc_dice
        spent = c.wc_vps(light=50, roll=roll, keep=keep)
        if spent > 0:
            assert c.vps == initial_vps - spent

    def test_low_light_no_spend(self) -> None:
        """With very low light wounds, spending VPs is wasteful."""
        c = make_combatant(water=5, void=3)
        roll, keep = c.wc_dice
        spent = c.wc_vps(light=1, roll=roll, keep=keep)
        assert spent == 0


class TestWoundCheck:
    """Integration tests for the full wound_check method."""

    def test_successful_check_keeps_light(self) -> None:
        """When the wound check succeeds and light wounds are below threshold,
        light wounds accumulate."""
        c = make_combatant(water=5, earth=5)
        # Force a high roll to guarantee success.
        with patch.object(c, "xky", return_value=100):
            c.wound_check(light=5)
        assert c.light == 5
        assert c.serious == 0

    def test_light_accumulates(self) -> None:
        """Multiple successful wound checks accumulate light wounds."""
        c = make_combatant(water=5, earth=5)
        with patch.object(c, "xky", return_value=100):
            c.wound_check(light=3)
            c.wound_check(light=4)
        assert c.light == 7

    def test_failed_check_adds_serious(self) -> None:
        """Failing a wound check converts to serious wounds and clears light."""
        c = make_combatant(water=3, earth=3)
        with patch.object(c, "xky", return_value=1):
            c.wound_check(light=20)
        assert c.light == 0
        assert c.serious >= 1

    def test_failed_check_clears_light(self) -> None:
        """After a failed wound check, light wounds reset to 0."""
        c = make_combatant(water=3, earth=3)
        # Accumulate some light wounds first.
        with patch.object(c, "xky", return_value=100):
            c.wound_check(light=5)
        assert c.light == 5
        # Now fail a wound check.
        with patch.object(c, "xky", return_value=1):
            c.wound_check(light=10)
        assert c.light == 0

    def test_voluntary_serious_when_above_threshold(self) -> None:
        """When light wounds exceed the wc_threshold and check succeeds,
        voluntarily take 1 serious wound to reset light to 0."""
        c = make_combatant(water=5, earth=5)
        # base_wc_threshold is 15 by default. Give 20 light.
        with patch.object(c, "xky", return_value=100):
            c.wound_check(light=20)
        assert c.light == 0
        assert c.serious == 1

    def test_no_voluntary_serious_when_near_death(self) -> None:
        """When one serious wound from death, keep light wounds rather than
        voluntarily taking a serious wound."""
        c = make_combatant(water=5, earth=3)
        c.serious = c.sw_to_kill - 1
        with patch.object(c, "xky", return_value=100):
            c.wound_check(light=15)
        # Should keep light wounds to avoid dying.
        assert c.light == 15
        assert c.serious == c.sw_to_kill - 1

    def test_incoming_serious_added(self) -> None:
        """Bonus serious wounds (e.g. from double attack) are added directly."""
        c = make_combatant(water=5, earth=5)
        with patch.object(c, "xky", return_value=100):
            c.wound_check(light=3, serious=2)
        assert c.serious == 2
        assert c.light == 3

    def test_crippled_at_earth_serious(self) -> None:
        """Crippled flag set when serious wounds reach Earth ring."""
        c = make_combatant(water=5, earth=3)
        with patch.object(c, "xky", return_value=1):
            c.wound_check(light=50)
        assert c.crippled is True

    def test_dead_at_double_earth_serious(self) -> None:
        """Dead flag set when serious wounds reach 2 * Earth ring."""
        c = make_combatant(water=2, earth=2)
        # Pre-load some serious wounds.
        c.serious = 3
        with patch.object(c, "xky", return_value=1):
            c.wound_check(light=50)
        assert c.dead is True

    def test_wound_check_event_fires(self) -> None:
        """The 'wound_check' event is triggered during the check."""
        c = make_combatant(water=5, earth=5)
        triggered = []
        c.events["wound_check"].append(lambda *args, **kwargs: triggered.append(args))
        with patch.object(c, "xky", return_value=100):
            c.wound_check(light=10)
        assert len(triggered) == 1
        # Should receive (check_result, light_this_hit, light_total).
        check, light, light_total = triggered[0]
        assert light == 10

    def test_serious_from_large_failure(self) -> None:
        """Failing by 25 points: should take 3 serious wounds (ceil(25/10))."""
        c = make_combatant(water=3, earth=5)
        # Force exact check value.
        with patch.object(c, "xky", return_value=15):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=40)
        # 40 light, 15 check -> fail by 25 -> 3 serious.
        assert c.serious == 3
        assert c.light == 0

    def test_serious_taken_not_contaminated_by_nested_wc(self) -> None:
        """If a wound_check event trigger calls wound_check() on self,
        the outer record's serious_taken must not include the nested
        wound check's serious wounds."""
        c = make_combatant(water=3, earth=5)
        fired = False

        def nested_trigger(check: int, light: int, total: int) -> None:
            nonlocal fired
            if not fired:
                fired = True
                c.wound_check(10)

        c.events["wound_check"].append(nested_trigger)

        # Force all wound checks to fail with check=1.
        with patch.object(c, "xky", return_value=1):
            with patch.object(c, "wc_vps", return_value=0):
                rec = c.wound_check(light=20)

        # The outer wound check: 20 light, check=1, fail by 19 -> 2 SW.
        # The nested wound check also fails, but its SW should NOT
        # appear in the outer record's serious_taken.
        assert rec.serious_taken == 2
