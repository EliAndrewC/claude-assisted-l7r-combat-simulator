"""Tests for the Monte Carlo wound estimation: expected_serious(),
the updated avg_serious() returning floats, and projected_damage()
returning floats.
"""

from l7r.combatant import Combatant


def make_combatant(**overrides: int) -> Combatant:
    """Create a minimal Combatant for testing wound estimation."""
    defaults = dict(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
    defaults.update(overrides)
    return Combatant(**defaults)


class TestExpectedSerious:
    """Tests for the expected_serious() Monte Carlo lookup method."""

    def test_zero_light_returns_zero(self) -> None:
        """No light wounds means no serious wounds regardless of pool."""
        c = make_combatant(water=3)
        assert c.expected_serious(0, 4, 3) == 0.0

    def test_high_light_low_pool_returns_positive(self) -> None:
        """High light wounds with a weak wound check pool should yield
        positive expected serious wounds."""
        c = make_combatant(water=2)
        result = c.expected_serious(50, 3, 2)
        assert result > 0.0

    def test_higher_pool_fewer_serious(self) -> None:
        """A larger wound check pool should produce fewer or equal
        expected serious wounds (monotonicity in pool size)."""
        c = make_combatant(water=3)
        sw_weak = c.expected_serious(40, 3, 2)
        sw_strong = c.expected_serious(40, 6, 4)
        assert sw_strong <= sw_weak

    def test_returns_float(self) -> None:
        """expected_serious should return a float, not an int."""
        c = make_combatant(water=3)
        result = c.expected_serious(30, 4, 3)
        assert isinstance(result, float)

    def test_overflow_pool_handled(self) -> None:
        """Overflow pools (e.g. 11k2) are converted via actual_xky
        before table lookup. 11k2 -> 10k3 with bonus 0."""
        c = make_combatant(water=3)
        # 11k2 should give the same result as 10k3 (after overflow)
        sw_overflow = c.expected_serious(40, 11, 2)
        sw_direct = c.expected_serious(40, 10, 3)
        assert sw_overflow == sw_direct

    def test_higher_light_more_serious(self) -> None:
        """More light wounds should produce more expected serious wounds."""
        c = make_combatant(water=3)
        sw_low = c.expected_serious(20, 4, 3)
        sw_high = c.expected_serious(60, 4, 3)
        assert sw_high >= sw_low


class TestAvgSeriousFloat:
    """Tests for the updated avg_serious() that now returns float values."""

    def test_returns_float_values(self) -> None:
        """Second element of each entry should be a float, not int."""
        c = make_combatant(water=3, void=2)
        result = c.avg_serious(light=30, roll=4, keep=3)
        for vps, sw in result:
            assert isinstance(sw, float), f"Expected float, got {type(sw)} for vps={vps}"

    def test_more_vps_fewer_wounds(self) -> None:
        """Spending more VPs should result in equal or fewer expected wounds."""
        c = make_combatant(water=3, void=4)
        result = c.avg_serious(light=40, roll=4, keep=3)
        for i in range(1, len(result)):
            assert result[i][1] <= result[i - 1][1]

    def test_list_length_matches_spendable_vps(self) -> None:
        """Should have one entry per spendable VP level."""
        c = make_combatant(water=3, void=2)
        result = c.avg_serious(light=30, roll=4, keep=3)
        assert len(result) == len(c.spendable_vps)

    def test_zero_light_zero_wounds(self) -> None:
        """Zero light wounds should yield zero expected serious wounds."""
        c = make_combatant(water=3, void=2)
        result = c.avg_serious(light=0, roll=4, keep=3)
        for vps, wounds in result:
            assert wounds == 0.0


class TestProjectedDamageFloat:
    """Tests for projected_damage() now returning float."""

    def _setup(self, **kw):
        defender = make_combatant(**kw)
        attacker = make_combatant(fire=4)
        defender.enemy = attacker
        attacker.enemy = defender
        attacker.attack_knack = "attack"
        attacker.attack_roll = 30
        defender.actions = [2, 4]
        defender.init_order = [2, 4]
        defender.phase = 2
        attacker.actions = [1, 3]
        attacker.init_order = [1, 3]
        attacker.phase = 1
        return defender, attacker

    def test_returns_float(self) -> None:
        """projected_damage should return a float."""
        defender, attacker = self._setup(water=3, earth=3)
        result = defender.projected_damage(attacker, True)
        assert isinstance(result, float)

    def test_extra_damage_greater_or_equal(self) -> None:
        """Extra damage True should yield >= extra damage False."""
        defender, attacker = self._setup(water=3, earth=3)
        extra = defender.projected_damage(attacker, True)
        base = defender.projected_damage(attacker, False)
        assert extra >= base
