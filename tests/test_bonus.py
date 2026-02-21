"""Tests for the bonus pool system on Combatant.

Tests the four bonus categories (always, auto_once, disc, multi) and the
methods that query and consume them: auto_once_bonus, disc_bonuses,
disc_bonus, use_disc_bonuses, max_bonus.
"""

from l7r.combatant import Combatant, all_subsets


def make_combatant(**overrides: int) -> Combatant:
    """Create a minimal Combatant for testing bonus logic in isolation."""
    defaults = dict(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
    defaults.update(overrides)
    return Combatant(**defaults)


class TestAllSubsets:
    """Tests for the all_subsets helper used by disc_bonus."""

    def test_single_element(self) -> None:
        assert all_subsets([5]) == [(5,)]

    def test_two_elements(self) -> None:
        result = all_subsets([5, 10])
        assert (5,) in result
        assert (10,) in result
        assert (5, 10) in result
        assert len(result) == 3

    def test_three_elements(self) -> None:
        result = all_subsets([1, 2, 3])
        # 3 singles + 3 pairs + 1 triple = 7
        assert len(result) == 7

    def test_empty(self) -> None:
        assert all_subsets([]) == []


class TestAlwaysBonus:
    """Tests for the 'always' bonus pool — permanent bonuses per roll type."""

    def test_defaults_to_zero(self) -> None:
        c = make_combatant()
        assert c.always["attack"] == 0
        assert c.always["parry"] == 0

    def test_set_and_read(self) -> None:
        c = make_combatant()
        c.always["attack"] = 5
        assert c.always["attack"] == 5

    def test_persists_across_reads(self) -> None:
        """Always bonuses are never consumed — they apply every time."""
        c = make_combatant()
        c.always["wound_check"] = 10
        assert c.always["wound_check"] == 10
        assert c.always["wound_check"] == 10

    def test_different_roll_types_independent(self) -> None:
        c = make_combatant()
        c.always["attack"] = 5
        c.always["parry"] = 10
        assert c.always["attack"] == 5
        assert c.always["parry"] == 10


class TestAutoOnce:
    """Tests for the 'auto_once' bonus pool — one-shot bonuses."""

    def test_defaults_to_zero(self) -> None:
        c = make_combatant()
        assert c.auto_once["attack"] == 0

    def test_set_and_consume(self) -> None:
        """auto_once_bonus() returns the value and resets it to 0."""
        c = make_combatant()
        c.auto_once["attack"] = 5
        assert c.auto_once_bonus("attack") == 5
        assert c.auto_once["attack"] == 0

    def test_consume_when_zero(self) -> None:
        c = make_combatant()
        assert c.auto_once_bonus("attack") == 0

    def test_second_read_is_zero(self) -> None:
        c = make_combatant()
        c.auto_once["damage"] = 8
        c.auto_once_bonus("damage")
        assert c.auto_once_bonus("damage") == 0

    def test_different_keys_independent(self) -> None:
        c = make_combatant()
        c.auto_once["damage_rolled"] = 4
        c.auto_once["damage_kept"] = 1
        assert c.auto_once_bonus("damage_rolled") == 4
        assert c.auto_once["damage_kept"] == 1


class TestResetDamage:
    """Tests for reset_damage(), which clears auto_once damage bonuses."""

    def test_clears_damage_auto_once(self) -> None:
        c = make_combatant()
        c.auto_once["damage_rolled"] = 4
        c.auto_once["damage_kept"] = 1
        c.auto_once["damage"] = 10
        c.reset_damage()
        assert c.auto_once["damage_rolled"] == 0
        assert c.auto_once["damage_kept"] == 0
        assert c.auto_once["damage"] == 0

    def test_does_not_clear_other_keys(self) -> None:
        c = make_combatant()
        c.auto_once["attack"] = 5
        c.auto_once["serious"] = 1
        c.reset_damage()
        assert c.auto_once["attack"] == 5
        assert c.auto_once["serious"] == 1


class TestDiscBonuses:
    """Tests for discretionary bonus queries and consumption."""

    def test_empty_by_default(self) -> None:
        c = make_combatant()
        assert c.disc_bonuses("attack") == []

    def test_disc_only(self) -> None:
        c = make_combatant()
        c.disc["attack"].extend([5, 5, 10])
        assert sorted(c.disc_bonuses("attack")) == [5, 5, 10]

    def test_multi_included(self) -> None:
        """disc_bonuses() includes both disc and multi pools."""
        c = make_combatant()
        c.disc["attack"].append(5)
        shared = [10]
        c.multi["attack"].append(shared)
        result = sorted(c.disc_bonuses("attack"))
        assert result == [5, 10]

    def test_multi_shared_across_types(self) -> None:
        """The same list object in multi can appear under
        multiple roll types."""
        c = make_combatant()
        shared = [5]
        c.multi["attack"].append(shared)
        c.multi["double_attack"].append(shared)
        assert c.disc_bonuses("attack") == [5]
        assert c.disc_bonuses("double_attack") == [5]

    def test_disc_bonuses_returns_copy(self) -> None:
        """disc_bonuses() deepcopies disc so consuming doesn't mutate it."""
        c = make_combatant()
        c.disc["attack"].extend([5, 10])
        result = c.disc_bonuses("attack")
        result.pop()
        # Original disc list should be unaffected.
        assert len(c.disc["attack"]) == 2


class TestUseDiscBonuses:
    """Tests for consuming specific discretionary bonuses."""

    def test_consume_from_disc(self) -> None:
        c = make_combatant()
        c.disc["attack"].extend([5, 10])
        c.use_disc_bonuses("attack", (5,))
        assert c.disc["attack"] == [10]

    def test_consume_from_multi(self) -> None:
        c = make_combatant()
        shared = [10]
        c.multi["attack"].append(shared)
        c.use_disc_bonuses("attack", (10,))
        assert shared == []

    def test_consume_shared_multi_depletes_both_types(self) -> None:
        """Using a shared multi bonus depletes it for all roll types."""
        c = make_combatant()
        shared = [5]
        c.multi["attack"].append(shared)
        c.multi["double_attack"].append(shared)
        c.use_disc_bonuses("attack", (5,))
        assert c.disc_bonuses("double_attack") == []

    def test_consume_prefers_disc_over_multi(self) -> None:
        """When both disc and multi have the same value,
        disc is consumed first."""
        c = make_combatant()
        c.disc["attack"].append(5)
        shared = [5]
        c.multi["attack"].append(shared)
        c.use_disc_bonuses("attack", (5,))
        # disc should be consumed first (it comes first in the lookup list).
        assert c.disc["attack"] == []
        assert shared == [5]


class TestDiscBonus:
    """Tests for disc_bonus() — find cheapest subset and spend it."""

    def test_zero_needed_returns_zero(self) -> None:
        c = make_combatant()
        c.disc["attack"].extend([5, 10])
        result = c.disc_bonus("attack", 0)
        assert result == 0
        # Nothing should be consumed.
        assert len(c.disc["attack"]) == 2

    def test_exact_match(self) -> None:
        """If a single bonus exactly matches, use it."""
        c = make_combatant()
        c.disc["attack"].extend([5, 10])
        result = c.disc_bonus("attack", 5)
        assert result == 5
        assert c.disc["attack"] == [10]

    def test_picks_cheapest_sufficient(self) -> None:
        """Given [5, 10], needing 6 should pick 10 (the only one big enough)."""
        c = make_combatant()
        c.disc["attack"].extend([5, 10])
        result = c.disc_bonus("attack", 6)
        assert result == 10
        assert c.disc["attack"] == [5]

    def test_combines_when_single_not_enough(self) -> None:
        """Given [5, 5], needing 8 should combine both for 10."""
        c = make_combatant()
        c.disc["attack"].extend([5, 5])
        result = c.disc_bonus("attack", 8)
        assert result == 10
        assert c.disc["attack"] == []

    def test_nothing_available_returns_zero(self) -> None:
        c = make_combatant()
        result = c.disc_bonus("attack", 5)
        assert result == 0

    def test_not_enough_uses_best_available(self) -> None:
        """If we can't meet the target, disc_bonus uses the best subset it can
        find (the min of the 'enough' list is empty, so falls through to
        empty best and returns 0)."""
        c = make_combatant()
        c.disc["attack"].append(3)
        result = c.disc_bonus("attack", 10)
        # When no subset is enough, best = [] -> sum([]) = 0.
        assert result == 0


class TestMaxBonus:
    """Tests for max_bonus() — theoretical maximum from all bonus pools."""

    def test_empty_pools(self) -> None:
        c = make_combatant()
        assert c.max_bonus("attack") == 0

    def test_always_only(self) -> None:
        c = make_combatant()
        c.always["attack"] = 5
        assert c.max_bonus("attack") == 5

    def test_auto_once_only(self) -> None:
        c = make_combatant()
        c.auto_once["attack"] = 3
        assert c.max_bonus("attack") == 3

    def test_disc_only(self) -> None:
        c = make_combatant()
        c.disc["attack"].extend([5, 10])
        assert c.max_bonus("attack") == 15

    def test_all_pools_combined(self) -> None:
        c = make_combatant()
        c.always["attack"] = 5
        c.auto_once["attack"] = 3
        c.disc["attack"].append(10)
        shared = [5]
        c.multi["attack"].append(shared)
        assert c.max_bonus("attack") == 23

    def test_does_not_consume(self) -> None:
        """max_bonus is read-only — it shouldn't deplete any pool."""
        c = make_combatant()
        c.always["attack"] = 5
        c.auto_once["attack"] = 3
        c.disc["attack"].append(10)
        c.max_bonus("attack")
        assert c.always["attack"] == 5
        assert c.auto_once["attack"] == 3
        assert c.disc["attack"] == [10]


class TestExtraDice:
    """Tests for the extra_dice system and its effect on
    dice pool calculations."""

    def test_default_extra_dice_zero(self) -> None:
        c = make_combatant()
        assert c.extra_dice["attack"] == [0, 0]
        assert c.extra_dice["parry"] == [0, 0]

    def test_att_dice_includes_extra(self) -> None:
        c = make_combatant(fire=4, attack=3)
        c.extra_dice["attack"][0] += 1  # +1 rolled
        roll, keep = c.att_dice("attack")
        # fire + attack + extra_rolled = 4 + 3 + 1 = 8 rolled
        # fire + extra_kept = 4 + 0 = 4 kept
        assert roll == 8
        assert keep == 4

    def test_damage_dice_includes_extra(self) -> None:
        c = make_combatant(fire=4)
        c.extra_dice["damage"][0] += 2
        c.extra_dice["damage"][1] += 1
        roll, keep = c.damage_dice
        # base_rolled(4) + fire(4) + extra(2) = 10 rolled
        # base_kept(2) + extra(1) = 3 kept
        assert roll == 10
        assert keep == 3

    def test_init_dice_includes_extra(self) -> None:
        c = make_combatant(void=3)
        c.extra_dice["initiative"][0] += 2
        roll, keep = c.init_dice
        # void+1+extra = 3+1+2 = 6 rolled
        # void+extra = 3+0 = 3 kept
        assert roll == 6
        assert keep == 3

    def test_wc_dice_includes_extra(self) -> None:
        c = make_combatant(water=4)
        c.extra_dice["wound_check"][1] += 1
        roll, keep = c.wc_dice
        # water+1+extra_rolled = 4+1+0 = 5 rolled
        # water+extra_kept = 4+1 = 5 kept
        assert roll == 5
        assert keep == 5


class TestR1TandR2T:
    """Tests that the __init__ logic for rank techniques
    sets up bonuses correctly."""

    def test_r1t_adds_extra_rolled_die(self) -> None:
        """1st Dan technique adds +1 rolled die to the specified roll types."""
        c = make_combatant()
        c.r1t_rolls = ["attack", "double_attack"]
        # Re-apply the init logic (since we set r1t after construction).
        for roll_type in c.r1t_rolls:
            c.extra_dice[roll_type][0] += 1
        assert c.extra_dice["attack"][0] == 1
        assert c.extra_dice["double_attack"][0] == 1
        assert c.extra_dice["parry"][0] == 0

    def test_r2t_adds_always_bonus(self) -> None:
        """2nd Dan technique adds +5 always bonus to one roll type."""
        c = make_combatant()
        c.r2t_rolls = "attack"
        c.always[c.r2t_rolls] += 5
        assert c.always["attack"] == 5
