"""Tests for combat-relevant advantages and disadvantages.

Covers Strength of the Earth, Great Destiny, Permanent Wound,
Lucky, and Unlucky.
"""

from unittest.mock import patch

import pytest

from l7r.combatant import Combatant


def make_combatant(**overrides: int) -> Combatant:
    defaults = dict(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
    defaults.update(overrides)
    return Combatant(**defaults)


class TestStrengthOfTheEarth:
    """Strength of the Earth: free raise (+5) on wound checks."""

    def test_always_wound_check_bonus(self) -> None:
        c = make_combatant(strength_of_the_earth=True)
        assert c.always["wound_check"] >= 5

    def test_no_bonus_without_advantage(self) -> None:
        c = make_combatant()
        assert c.always["wound_check"] == 0

    def test_wc_bonus_includes_strength_of_earth(self) -> None:
        c = make_combatant(strength_of_the_earth=True)
        bonus = c.wc_bonus(light=20, check=10)
        assert bonus >= 5

    def test_wound_check_integration(self) -> None:
        """The +5 bonus can turn a failed wound check into a pass."""
        c_with = make_combatant(strength_of_the_earth=True, water=3, earth=5)
        c_without = make_combatant(water=3, earth=5)

        # Both roll 9 on the wound check against 10 light wounds.
        # With SotE: 9 + 5 = 14 >= 10 → pass, keep light wounds.
        # Without:   9 < 10 → fail, take serious wound(s).
        with patch.object(c_with, "xky", return_value=9):
            with patch.object(c_with, "wc_vps", return_value=0):
                c_with.wound_check(light=10)
        with patch.object(c_without, "xky", return_value=9):
            with patch.object(c_without, "wc_vps", return_value=0):
                c_without.wound_check(light=10)

        assert c_with.serious == 0
        assert c_with.light == 10
        assert c_without.serious >= 1
        assert c_without.light == 0

    def test_stacks_with_other_always_bonuses(self) -> None:
        """SotE stacks additively with other always wound_check bonuses."""
        c = make_combatant(strength_of_the_earth=True)
        c.always["wound_check"] += 5  # e.g. from a school R2T
        assert c.always["wound_check"] == 10


class TestGreatDestiny:
    """Great Destiny: one additional serious wound to kill."""

    def test_sw_to_kill_increased(self) -> None:
        c = make_combatant(earth=3, great_destiny=True)
        assert c.sw_to_kill == 7  # normally 6

    def test_sw_to_kill_without_advantage(self) -> None:
        c = make_combatant(earth=3)
        assert c.sw_to_kill == 6

    def test_stacks_with_extra_serious(self) -> None:
        c = make_combatant(earth=3, extra_serious=2, great_destiny=True)
        assert c.sw_to_kill == 9  # 2*3 + 2 + 1

    def test_not_dead_at_normal_threshold(self) -> None:
        """Character with Great Destiny survives at the normal kill threshold."""
        c = make_combatant(earth=3, great_destiny=True)
        with patch.object(c, "xky", return_value=1):
            c.wound_check(light=100)
        # Even with massive wounds, they need 7 serious to die, not 6.
        assert c.sw_to_kill == 7

    def test_dead_at_increased_threshold(self) -> None:
        c = make_combatant(earth=3, great_destiny=True)
        c.serious = 7
        c.dead = c.serious >= c.sw_to_kill
        assert c.dead is True

    def test_sw_to_cripple_unchanged(self) -> None:
        """Great Destiny does not affect the cripple threshold."""
        c = make_combatant(earth=3, great_destiny=True)
        assert c.sw_to_cripple == 3

    def test_near_death_decision_uses_new_threshold(self) -> None:
        """At sw_to_kill - 1 serious, the combatant should keep light wounds
        rather than voluntarily taking a serious wound."""
        c = make_combatant(earth=3, great_destiny=True, water=5)
        c.serious = 6  # one from death (sw_to_kill = 7)
        with patch.object(c, "xky", return_value=100):
            c.wound_check(light=20)
        # Should keep light wounds since one serious from death.
        assert c.serious == 6
        assert c.light == 20


class TestPermanentWound:
    """Permanent Wound: one fewer serious wound to kill."""

    def test_sw_to_kill_decreased(self) -> None:
        c = make_combatant(earth=3, permanent_wound=True)
        assert c.sw_to_kill == 5  # normally 6

    def test_dead_at_reduced_threshold(self) -> None:
        c = make_combatant(earth=3, permanent_wound=True)
        c.serious = 5
        c.dead = c.serious >= c.sw_to_kill
        assert c.dead is True

    def test_not_dead_below_reduced_threshold(self) -> None:
        c = make_combatant(earth=3, permanent_wound=True)
        c.serious = 4
        c.dead = c.serious >= c.sw_to_kill
        assert c.dead is False

    def test_sw_to_cripple_unchanged(self) -> None:
        c = make_combatant(earth=3, permanent_wound=True)
        assert c.sw_to_cripple == 3

    def test_wound_check_kills_at_reduced_threshold(self) -> None:
        """A combatant with Permanent Wound dies at 2*earth - 1."""
        c = make_combatant(earth=3, permanent_wound=True, water=2)
        c.serious = 4
        with patch.object(c, "xky", return_value=1):
            c.wound_check(light=50)
        assert c.dead is True


class TestMutualExclusivity:
    """Great Destiny and Permanent Wound cannot be taken together."""

    def test_both_raises_error(self) -> None:
        with pytest.raises(ValueError, match="mutually exclusive"):
            make_combatant(great_destiny=True, permanent_wound=True)

    def test_great_destiny_alone_ok(self) -> None:
        c = make_combatant(great_destiny=True)
        assert c.sw_to_kill == 7

    def test_permanent_wound_alone_ok(self) -> None:
        c = make_combatant(permanent_wound=True)
        assert c.sw_to_kill == 5


class TestUnlucky:
    """Unlucky: apply -5 penalty to wound check if it would cause 1+ extra SW."""

    def test_field_defaults_false(self) -> None:
        c = make_combatant()
        assert c.unlucky is False

    def test_penalty_applied_when_causes_extra_sw(self) -> None:
        """Unlucky -5 turns a pass into a fail → 1 extra SW."""
        c = make_combatant(unlucky=True, water=3, earth=3)
        # Roll 12 vs 10 light → passes (12 >= 10), sw=0.
        # Penalized: 12-5=7 < 10 → calc_serious(10,7)=ceil(3/10)=1.
        # 1 >= 0+1 → apply penalty.
        with patch.object(c, "xky", return_value=12):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=10)
        assert c.serious == 1
        assert c.light == 0
        assert c.unlucky_used is True

    def test_penalty_applied_when_worsens_failure(self) -> None:
        """Unlucky -5 pushes a failure across a 10-point threshold."""
        c = make_combatant(unlucky=True, water=3)
        # Roll 12 vs 20 light → fails: calc_serious(20,12)=ceil(8/10)=1 SW.
        # Penalized: 12-5=7 → calc_serious(20,7)=ceil(13/10)=2 SW.
        # 2 >= 1+1 → apply penalty.
        with patch.object(c, "xky", return_value=12):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=20)
        assert c.serious == 2

    def test_no_penalty_when_no_extra_sw(self) -> None:
        """-5 doesn't cross a threshold → penalty not applied."""
        c = make_combatant(unlucky=True, water=3)
        # Roll 16 vs 20 → fails: calc_serious(20,16)=ceil(4/10)=1 SW.
        # Penalized: 16-5=11 → calc_serious(20,11)=ceil(9/10)=1 SW.
        # 1 >= 1+1? No → keep original.
        with patch.object(c, "xky", return_value=16):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=20)
        assert c.serious == 1

    def test_no_penalty_without_unlucky(self) -> None:
        """Without unlucky, wound check behaves normally."""
        c = make_combatant(water=3)
        # Roll 12 vs 10 → passes, keeps light. No penalty applied.
        with patch.object(c, "xky", return_value=12):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=10)
        assert c.serious == 0
        assert c.light == 10

    def test_penalty_not_applied_when_both_pass(self) -> None:
        """If check-5 still passes, no extra SW, penalty skipped."""
        c = make_combatant(unlucky=True, water=3)
        # Roll 100 vs 10 → passes. Penalized: 95 >= 10 → still passes.
        # sw_from_wc = 0 (light kept), penalized_sw = 0. No change.
        with patch.object(c, "xky", return_value=100):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=10)
        assert c.serious == 0
        assert c.light == 10
        assert c.unlucky_used is False

    def test_not_applied_twice(self) -> None:
        """Unlucky can only be applied once per combat."""
        c = make_combatant(unlucky=True, water=3, earth=3)
        # First wound check: penalty triggers (12-5=7 < 10).
        with patch.object(c, "xky", return_value=12):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=10)
        assert c.serious == 1
        assert c.unlucky_used is True

        # Second wound check: same scenario, but unlucky already used.
        c.serious = 0
        c.light = 0
        with patch.object(c, "xky", return_value=12):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=10)
        # 12 >= 10 → passes, keeps light. No penalty applied.
        assert c.serious == 0
        assert c.light == 10


class TestLucky:
    """Lucky: may reroll one failed wound check per combat."""

    def test_field_defaults(self) -> None:
        c = make_combatant()
        assert c.lucky is False
        assert c.lucky_used is False

    def test_reroll_when_above_threshold(self) -> None:
        """Lucky triggers when check fails, SW >= threshold, and
        expected reroll is better."""
        c = make_combatant(lucky=True, water=2, earth=3, lucky_wc_threshold=1)
        # First roll fails (5 < 10): calc_serious(10, 5) = 1 SW.
        # 1 >= threshold(1) and expected(0.3) < 1 → use Lucky.
        # Reroll 100 passes → keep light wounds.
        with patch.object(c, "xky", side_effect=[5, 100]):
            with patch.object(c, "wc_vps", return_value=0):
                with patch.object(c, "expected_serious", return_value=0.3):
                    c.wound_check(light=10)
        assert c.lucky_used is True
        assert c.serious == 0
        assert c.light == 10

    def test_no_reroll_below_threshold(self) -> None:
        """SW from failed check < threshold → don't use Lucky."""
        c = make_combatant(lucky=True, water=2, lucky_wc_threshold=3)
        # Fails with ceil((20-15)/10) = 1 SW, but threshold is 3.
        with patch.object(c, "xky", return_value=15):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=20)
        assert c.lucky_used is False
        assert c.serious == 1

    def test_no_reroll_when_already_used(self) -> None:
        """Lucky can only be used once per combat."""
        c = make_combatant(lucky=True, water=2, lucky_wc_threshold=1)
        c.lucky_used = True
        with patch.object(c, "xky", return_value=5):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=20)
        assert c.serious >= 1

    def test_no_reroll_when_expected_not_better(self) -> None:
        """Expected reroll >= actual SW → don't waste Lucky."""
        c = make_combatant(lucky=True, water=2, lucky_wc_threshold=1)
        # Fails: calc_serious(20, 5) = 2 SW.
        # expected(3.0) < 2? No → don't reroll.
        with patch.object(c, "xky", return_value=5):
            with patch.object(c, "wc_vps", return_value=0):
                with patch.object(c, "expected_serious", return_value=3.0):
                    c.wound_check(light=20)
        assert c.lucky_used is False
        assert c.serious == 2

    def test_lucky_does_not_trigger_on_passed_check(self) -> None:
        """Lucky only triggers on failed wound checks."""
        c = make_combatant(lucky=True, water=3, lucky_wc_threshold=1)
        # Check passes (100 >= 10), voluntary SW taken (light > threshold).
        # Lucky should not trigger since the check succeeded.
        with patch.object(c, "xky", return_value=100):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=20)
        assert c.lucky_used is False

    def test_lucky_used_persists_across_wound_checks(self) -> None:
        """Once Lucky is spent, it stays spent for subsequent checks."""
        c = make_combatant(lucky=True, water=3, earth=3, lucky_wc_threshold=1)
        # First wound check: fails, Lucky rerolls to a pass.
        with patch.object(c, "xky", side_effect=[5, 100]):
            with patch.object(c, "wc_vps", return_value=0):
                with patch.object(c, "expected_serious", return_value=0.3):
                    c.wound_check(light=10)
        assert c.lucky_used is True
        assert c.serious == 0

        # Second wound check: fails, but Lucky already used.
        c.light = 0
        with patch.object(c, "xky", return_value=5):
            with patch.object(c, "wc_vps", return_value=0):
                c.wound_check(light=10)
        assert c.serious == 1
