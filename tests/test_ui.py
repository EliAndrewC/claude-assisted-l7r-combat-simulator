"""Tests for UI helper functions (progression discovery, fighter building)."""

from __future__ import annotations

import pytest

from ui.app import build_fighter, get_progressions


class TestGetProgressions:
    def test_returns_all_progressions(self) -> None:
        progs = get_progressions()
        assert len(progs) == 25

    def test_display_names_have_no_progression_suffix(self) -> None:
        for name in get_progressions():
            assert "Progression" not in name

    def test_display_names_are_space_separated(self) -> None:
        progs = get_progressions()
        assert "Akodo Bushi" in progs
        assert "Kakita Duelist" in progs
        assert "Wave Man" in progs

    def test_schools_listed_before_professionals(self) -> None:
        names = list(get_progressions().keys())
        wave_man_idx = names.index("Wave Man")
        ninja_idx = names.index("Ninja")
        akodo_idx = names.index("Akodo Bushi")
        assert akodo_idx < wave_man_idx
        assert akodo_idx < ninja_idx


def _base_config(**overrides: object) -> dict:
    config: dict = {
        "progression_name": "Akodo Bushi",
        "total_xp": 150,
        "non_combat_pct": 0.2,
        "overrides": {},
        "strength_of_the_earth": False,
        "great_destiny": False,
        "permanent_wound": False,
        "lucky": False,
        "unlucky": False,
    }
    config.update(overrides)
    return config


class TestBuildFighter:
    def test_basic_build(self) -> None:
        fighter = build_fighter(_base_config())
        assert fighter.rank > 0
        assert fighter.xp == 150

    def test_xp_slider_maps_to_earned_xp(self) -> None:
        f1 = build_fighter(_base_config(total_xp=150))
        f2 = build_fighter(_base_config(total_xp=250))
        assert f2.xp == 250
        assert f2.rank >= f1.rank

    def test_strength_of_the_earth(self) -> None:
        fighter = build_fighter(_base_config(strength_of_the_earth=True))
        assert fighter.strength_of_the_earth is True
        assert fighter.always["wound_check"] >= 5

    def test_great_destiny(self) -> None:
        fighter = build_fighter(_base_config(great_destiny=True))
        assert fighter.great_destiny is True
        assert fighter.extra_serious >= 1

    def test_permanent_wound(self) -> None:
        fighter = build_fighter(_base_config(permanent_wound=True))
        assert fighter.permanent_wound is True

    def test_lucky(self) -> None:
        fighter = build_fighter(_base_config(lucky=True))
        assert fighter.lucky is True

    def test_unlucky(self) -> None:
        fighter = build_fighter(_base_config(unlucky=True))
        assert fighter.unlucky is True

    def test_manual_overrides(self) -> None:
        overrides = {"fire": 5, "attack": 4}
        fighter = build_fighter(_base_config(overrides=overrides))
        assert fighter.fire == 5
        assert fighter.attack == 4

    def test_baseline_overrides_are_noop(self) -> None:
        baseline = build_fighter(_base_config())
        overrides = {"fire": baseline.fire, "water": baseline.water}
        fighter = build_fighter(_base_config(overrides=overrides))
        assert fighter.fire == baseline.fire
        assert fighter.water == baseline.water

    def test_overrides_affect_derived_values(self) -> None:
        baseline = build_fighter(_base_config())
        fighter = build_fighter(_base_config(overrides={"parry": 5}))
        assert fighter.tn > baseline.tn

    def test_rank_override(self) -> None:
        fighter = build_fighter(_base_config(overrides={"rank": 1}))
        assert fighter.rank == 1
        for knack in fighter.school_knacks:
            assert getattr(fighter, knack) == 1

    def test_rank_override_high(self) -> None:
        fighter = build_fighter(_base_config(
            total_xp=300, overrides={"rank": 5},
        ))
        assert fighter.rank == 5
        for knack in fighter.school_knacks:
            assert getattr(fighter, knack) == 5

    def test_non_combat_pct_affects_build(self) -> None:
        f_high = build_fighter(_base_config(total_xp=300, non_combat_pct=0.0))
        f_low = build_fighter(_base_config(total_xp=300, non_combat_pct=0.5))
        high_total = sum(getattr(f_high, r) for r in ("air", "earth", "fire", "water", "void"))
        low_total = sum(getattr(f_low, r) for r in ("air", "earth", "fire", "water", "void"))
        assert high_total >= low_total

    def test_professional_progression(self) -> None:
        fighter = build_fighter(_base_config(
            progression_name="Wave Man", total_xp=200,
        ))
        assert fighter.xp == 200

    def test_great_destiny_and_permanent_wound_exclusive(self) -> None:
        with pytest.raises(ValueError):
            build_fighter(_base_config(
                great_destiny=True, permanent_wound=True,
            ))
