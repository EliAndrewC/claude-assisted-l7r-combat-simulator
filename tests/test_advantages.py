"""Tests for combat-relevant advantages and disadvantages.

Covers Strength of the Earth, Great Destiny, and Permanent Wound.
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
