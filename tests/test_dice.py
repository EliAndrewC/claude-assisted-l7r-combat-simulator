"""Tests for the dice rolling primitives."""

from unittest.mock import patch

from l7r.dice import actual_xky, avg, d10, xky


class TestD10:
    """Tests for the single d10 roll function."""

    def test_no_reroll_range(self) -> None:
        """Without rerolling, results must be 1-10."""
        results = set()
        for _ in range(5000):
            result = d10(reroll=False)
            assert 1 <= result <= 10
            results.add(result)
        # With 5000 rolls, we should see all 10 faces.
        assert results == set(range(1, 11))

    def test_no_reroll_10_stays_10(self) -> None:
        """Without rerolling, a 10 is just 10 — no explosion."""
        with patch("l7r.dice.randrange", return_value=10):
            assert d10(reroll=False) == 10

    def test_reroll_non_10(self) -> None:
        """With rerolling enabled, a non-10 result is returned as-is."""
        with patch("l7r.dice.randrange", return_value=7):
            assert d10(reroll=True) == 7

    def test_reroll_explodes_once(self) -> None:
        """A 10 followed by a non-10 sums both rolls."""
        with patch("l7r.dice.randrange", side_effect=[10, 6]):
            assert d10(reroll=True) == 16

    def test_reroll_explodes_multiple(self) -> None:
        """Multiple 10s chain: 10+10+3 = 23."""
        with patch("l7r.dice.randrange", side_effect=[10, 10, 3]):
            assert d10(reroll=True) == 23

    def test_reroll_explodes_then_10_stops(self) -> None:
        """Explosion stops when the die finally shows non-10.
        10+10+10+1 = 31."""
        with patch("l7r.dice.randrange", side_effect=[10, 10, 10, 1]):
            assert d10(reroll=True) == 31

    def test_default_is_reroll(self) -> None:
        """The default behavior is to reroll 10s."""
        with patch("l7r.dice.randrange", side_effect=[10, 5]):
            assert d10() == 15


class TestActualXkY:
    """Tests for the overflow/capping rules."""

    def test_no_overflow(self) -> None:
        """Pools within 10k10 pass through unchanged."""
        assert actual_xky(5, 3) == (5, 3, 0)
        assert actual_xky(10, 10) == (10, 10, 0)
        assert actual_xky(1, 1) == (1, 1, 0)

    def test_rolled_overflow_converts_to_kept(self) -> None:
        """Rolled dice above 10 become extra kept dice.
        12k4 -> 10k6, 15k3 -> 10k8."""
        assert actual_xky(12, 4) == (10, 6, 0)
        assert actual_xky(15, 3) == (10, 8, 0)

    def test_kept_overflow_converts_to_bonus(self) -> None:
        """Kept dice above 10 become +2 bonus each.
        10k12 -> 10k10+4."""
        assert actual_xky(10, 12) == (10, 10, 2)

    def test_both_overflows_chain(self) -> None:
        """Rolled overflow can push kept past 10 too.
        14k8 -> 10k12 -> 10k10+4."""
        assert actual_xky(14, 8) == (10, 10, 2)

    def test_extreme_overflow(self) -> None:
        """Very large pools: 20k5 -> 10k15 -> 10k10+10."""
        assert actual_xky(20, 5) == (10, 10, 5)

    def test_rolled_equals_11(self) -> None:
        """Edge case: exactly 1 over the cap. 11k3 -> 10k4."""
        assert actual_xky(11, 3) == (10, 4, 0)

    def test_kept_equals_11(self) -> None:
        """Edge case: kept exactly 1 over. 10k11 -> 10k10+2."""
        assert actual_xky(10, 11) == (10, 10, 1)


class TestXkY:
    """Tests for the full XkY dice roll."""

    def test_keeps_highest(self) -> None:
        """Rolling 3k2 with dice [2, 8, 5] should keep the 2 highest: 8+5=13."""
        with patch("l7r.dice.d10", side_effect=[2, 8, 5]):
            assert xky(3, 2) == 13

    def test_1k1(self) -> None:
        """Rolling 1k1 is just one die."""
        with patch("l7r.dice.d10", return_value=7):
            assert xky(1, 1) == 7

    def test_keeps_all_when_keep_equals_roll(self) -> None:
        """3k3 keeps everything: 4+6+3=13."""
        with patch("l7r.dice.d10", side_effect=[4, 6, 3]):
            assert xky(3, 3) == 13

    def test_overflow_adds_bonus(self) -> None:
        """12k4 overflows to 10k6+0. The bonus comes from actual_xky.
        With 10 dice [1,2,3,4,5,6,7,8,9,10], keep top 6: 5+6+7+8+9+10=45."""
        with patch("l7r.dice.d10", side_effect=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]):
            assert xky(12, 4) == 45

    def test_reroll_passed_to_d10(self) -> None:
        """The reroll flag is forwarded to d10."""
        with patch("l7r.dice.d10", return_value=5) as mock_d10:
            xky(2, 1, reroll=False)
            for call in mock_d10.call_args_list:
                assert call.args[0] is False

    def test_reroll_default_is_true(self) -> None:
        """xky defaults to rerolling 10s."""
        with patch("l7r.dice.d10", return_value=5) as mock_d10:
            xky(2, 1)
            for call in mock_d10.call_args_list:
                assert call.args[0] is True

    def test_statistical_sanity_2k1(self) -> None:
        """2k1 with rerolls: average should be roughly 7.0-8.0
        (the expected value of max(d10, d10) with exploding dice)."""
        total = sum(xky(2, 1) for _ in range(10000))
        average = total / 10000
        assert 6.5 < average < 9.0

    def test_statistical_sanity_no_reroll_lower(self) -> None:
        """Without rerolls, the average of 2k1 should be noticeably lower
        than with rerolls, since 10s don't explode."""
        avg_reroll = sum(xky(2, 1, True) for _ in range(10000)) / 10000
        avg_no_reroll = sum(xky(2, 1, False) for _ in range(10000)) / 10000
        assert avg_no_reroll < avg_reroll


class TestAvg:
    """Tests for the average lookup/estimation function."""

    def test_known_value_from_probability_table(self) -> None:
        """For pools within the table (<=10k10), avg() returns the
        pre-computed value from the probability table."""
        result = avg(True, 5, 3)
        # The probability table stores averages; should be a reasonable number.
        assert isinstance(result, (int, float))
        assert result > 0

    def test_no_reroll_lower_than_reroll(self) -> None:
        """No-reroll averages should be lower than reroll averages for
        the same pool, since 10s don't explode."""
        reroll_avg = avg(True, 5, 3)
        no_reroll_avg = avg(False, 5, 3)
        assert no_reroll_avg < reroll_avg

    def test_more_dice_higher_average(self) -> None:
        """More rolled dice (same kept) should give a higher average."""
        assert avg(True, 3, 2) < avg(True, 6, 2)

    def test_more_kept_higher_average(self) -> None:
        """More kept dice (same rolled) should give a higher average."""
        assert avg(True, 6, 2) < avg(True, 6, 4)

    def test_overflow_estimation(self) -> None:
        """For pools beyond 10k10, avg() estimates using the formula
        61 + 2*(roll+keep-20). 12k11 -> 61 + 2*(12+11-20) = 67."""
        result = avg(True, 12, 11)
        assert result == 67.0

    def test_overflow_estimation_large(self) -> None:
        """15k15 -> 61 + 2*(15+15-20) = 81."""
        result = avg(True, 15, 15)
        assert result == 81.0
