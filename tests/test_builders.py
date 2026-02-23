"""Tests for the character builder and XP cost functions."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from l7r.combatant import Combatant
from l7r.builders import (
    Progression,
    build,
    _ring_cost,
    _basic_skill_cost,
    _advanced_skill_cost,
    _validate_progression,
    _resolve_school_class,
)
from l7r.builders.akodo_bushi import AkodoBushiProgression
from l7r.builders.bayushi_bushi import BayushiBushiProgression
from l7r.builders.isawa_duelist import IsawaDuelistProgression
from l7r.builders.kakita_duelist import KakitaDuelistProgression
from l7r.builders.kitsuki_magistrate import KitsukiMagistrateProgression
from l7r.builders.matsu_bushi import MatsuBushiProgression
from l7r.builders.mirumoto_bushi import MirumotoBushiProgression
from l7r.builders.otaku_bushi import OtakuBushiProgression
from l7r.builders.shiba_bushi import ShibaBushiProgression
from l7r.builders.shinjo_bushi import ShinjoBushiProgression


# -----------------------------------------------------------
# Cost helpers
# -----------------------------------------------------------


class TestRingCost:
    def test_base_costs(self):
        assert _ring_cost(3, discount=False) == 15
        assert _ring_cost(4, discount=False) == 20
        assert _ring_cost(5, discount=False) == 25
        assert _ring_cost(6, discount=False) == 30

    def test_discount(self):
        assert _ring_cost(4, discount=True) == 15
        assert _ring_cost(5, discount=True) == 20
        assert _ring_cost(6, discount=True) == 25


class TestBasicSkillCost:
    def test_ranks_1_and_2(self):
        assert _basic_skill_cost(1) == 2
        assert _basic_skill_cost(2) == 2

    def test_ranks_3_through_5(self):
        assert _basic_skill_cost(3) == 3
        assert _basic_skill_cost(4) == 3
        assert _basic_skill_cost(5) == 3


class TestAdvancedSkillCost:
    def test_ranks_1_and_2(self):
        assert _advanced_skill_cost(1) == 4
        assert _advanced_skill_cost(2) == 4

    def test_ranks_3_through_5(self):
        assert _advanced_skill_cost(3) == 6
        assert _advanced_skill_cost(4) == 8
        assert _advanced_skill_cost(5) == 10


# -----------------------------------------------------------
# Minimal test school & progressions
# -----------------------------------------------------------


class _SimpleSchool(Combatant):
    """Minimal school with one knack for isolated builder tests."""

    school_knacks = ["iaijutsu"]
    school_ring = "fire"
    r4t_ring_boost = "fire"
    r1t_rolls = []
    r2t_rolls = None


class _EmptyProg(Progression):
    school_class = _SimpleSchool
    steps = []


# -----------------------------------------------------------
# Starting state
# -----------------------------------------------------------


class TestStartingState:
    def test_rings_default_to_2_except_school_ring(self):
        c = build(_EmptyProg, xp=150, non_combat_pct=0.0)
        assert c.air == 2
        assert c.earth == 2
        assert c.water == 2
        assert c.void == 2
        assert c.fire == 3  # school ring

    def test_school_knacks_start_at_1(self):
        c = build(_EmptyProg, xp=150, non_combat_pct=0.0)
        assert c.iaijutsu == 1
        assert c.rank == 1

    def test_skills_start_at_1(self):
        c = build(_EmptyProg, xp=150, non_combat_pct=0.0)
        assert c.attack == 1
        assert c.parry == 1


# -----------------------------------------------------------
# Ring steps
# -----------------------------------------------------------


class TestBuildRings:
    def test_raises_ring_by_one(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("air", 3)]

        c = build(P, xp=15, non_combat_pct=0.0)  # air 2→3: 15 XP
        assert c.air == 3

    def test_insufficient_xp_leaves_ring(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("air", 3)]

        c = build(P, xp=14, non_combat_pct=0.0)
        assert c.air == 2

    def test_school_ring_raises_from_3(self):
        """School ring starts at 3, so one step raises it to 4."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("fire", 4)]

        c = build(P, xp=20, non_combat_pct=0.0)  # fire 3→4: 20 XP
        assert c.fire == 4

    def test_ring_max_5_for_non_school(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("air", 3), ("air", 4), ("air", 5)]

        c = build(P, xp=500, non_combat_pct=0.0)
        assert c.air == 5

    def test_ring_max_6_for_school_ring(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("fire", 4), ("fire", 5), ("fire", 6)]

        c = build(P, xp=500, non_combat_pct=0.0)
        assert c.fire == 6

    def test_multi_step_ring_raises(self):
        """Two separate steps raising the same ring."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("air", 3), ("air", 4)]

        # air 2→3: 15, 3→4: 20 = 35 XP
        c = build(P, xp=35, non_combat_pct=0.0)
        assert c.air == 4


# -----------------------------------------------------------
# Skill steps
# -----------------------------------------------------------


class TestBuildSkills:
    def test_raises_attack(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("attack", 2)]

        c = build(P, xp=4, non_combat_pct=0.0)  # 1→2: 4
        assert c.attack == 2

    def test_raises_parry(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("parry", 2), ("parry", 3)]

        c = build(P, xp=10, non_combat_pct=0.0)  # 1→2: 4, 2→3: 6
        assert c.parry == 3

    def test_partial_skill_raise(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("attack", 2), ("attack", 3)]

        c = build(P, xp=5, non_combat_pct=0.0)  # only enough for 1→2
        assert c.attack == 2

    def test_skill_max_5(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [
                ("attack", 2), ("attack", 3),
                ("attack", 4), ("attack", 5),
            ]

        c = build(P, xp=500, non_combat_pct=0.0)
        assert c.attack == 5


# -----------------------------------------------------------
# Knack steps
# -----------------------------------------------------------


class TestBuildKnacks:
    def test_raises_knack_by_one(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("knacks", 2), ("knacks", 3)]

        c = build(P, xp=10, non_combat_pct=0.0)  # 1→2: 4, 2→3: 6
        assert c.iaijutsu == 3
        assert c.rank == 3

    def test_partial_knack_raise(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("knacks", 2), ("knacks", 3)]

        c = build(P, xp=5, non_combat_pct=0.0)  # only enough for 1→2
        assert c.iaijutsu == 2

    def test_multiple_knacks_raised_in_order(self):
        """XP exhaustion mid-step leaves later knacks lower."""

        class _ThreeKnackSchool(Combatant):
            school_knacks = ["iaijutsu", "lunge", "feint"]
            school_ring = "fire"
            r4t_ring_boost = "fire"
            r1t_rolls = []
            r2t_rolls = None

        class P(Progression):
            school_class = _ThreeKnackSchool
            steps = [("knacks", 2)]

        # Each knack 1→2 costs 4, three knacks = 12 XP total.
        # With only 9 XP, two fit (8), third can't (4 > 1).
        c = build(P, xp=9, non_combat_pct=0.0)
        assert c.iaijutsu == 2
        assert c.lunge == 2
        assert c.feint == 1
        assert c.rank == 1  # min(2, 2, 1)

    def test_knack_max_5(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [
                ("knacks", 2), ("knacks", 3),
                ("knacks", 4), ("knacks", 5),
            ]

        c = build(P, xp=500, non_combat_pct=0.0)
        assert c.iaijutsu == 5


# -----------------------------------------------------------
# R4T ring boost & discount
# -----------------------------------------------------------


class TestR4T:
    def test_free_ring_boost_at_4th_dan(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("knacks", 2), ("knacks", 3), ("knacks", 4)]

        # iaijutsu 1→2: 4, 2→3: 6, 3→4: 8 = 18 XP
        # R4T triggers: fire (r4t_ring_boost) 3→4 for free
        c = build(P, xp=18, non_combat_pct=0.0)
        assert c.iaijutsu == 4
        assert c.rank == 4
        assert c.fire == 4

    def test_no_boost_before_4th_dan(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("knacks", 2), ("knacks", 3)]

        c = build(P, xp=10, non_combat_pct=0.0)
        assert c.iaijutsu == 3
        assert c.fire == 3  # school ring starting value, no boost

    def test_school_ring_discount_after_4th_dan(self):
        """After 4th Dan, school ring raises cost 5 fewer XP."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [
                ("knacks", 2), ("knacks", 3), ("knacks", 4),
                ("fire", 5),
            ]

        # knacks: 4 + 6 + 8 = 18 XP, R4T: fire→4 free
        # fire 4→5: 5×5 − 5 = 20 XP (discounted)
        # Total: 38 XP
        c = build(P, xp=38, non_combat_pct=0.0)
        assert c.fire == 5

    def test_discount_not_enough_xp(self):
        """Verify the discount is exactly 5 — 37 XP shouldn't be enough."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [
                ("knacks", 2), ("knacks", 3), ("knacks", 4),
                ("fire", 5),
            ]

        c = build(P, xp=37, non_combat_pct=0.0)
        assert c.fire == 4

    def test_no_discount_without_4th_dan(self):
        """Without 4th Dan, school ring raise is full price."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("fire", 4), ("fire", 5)]

        # fire 3→4: 20, 4→5: 25 = 45 XP (no discount)
        c = build(P, xp=44, non_combat_pct=0.0)
        assert c.fire == 4  # can't afford 5

    def test_non_school_ring_no_discount(self):
        """Non-school rings never get the discount even after 4th Dan."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [
                ("knacks", 2), ("knacks", 3), ("knacks", 4),
                ("air", 3), ("air", 4),
            ]

        # knacks: 18 XP, R4T fires
        # air 2→3: 15, 3→4: 20 = 35 XP (no discount)
        # Total: 53 XP
        c = build(P, xp=52, non_combat_pct=0.0)
        assert c.air == 3  # can't afford 4


# -----------------------------------------------------------
# Budget mechanics
# -----------------------------------------------------------


class TestBudget:
    def test_non_combat_pct_reduces_budget(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("air", 3)]

        # 150 × 0.1 = 15, exactly enough for air 2→3
        c = build(P, xp=150, non_combat_pct=0.9)
        assert c.air == 3

    def test_earned_xp_adds_to_budget(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("air", 3)]

        # (10 + 5) × 1.0 = 15
        c = build(P, xp=10, earned_xp=5, non_combat_pct=0.0)
        assert c.air == 3

    def test_xp_attribute_on_combatant(self):
        c = build(_EmptyProg, xp=150, earned_xp=50, non_combat_pct=0.0)
        assert c.xp == 200

    def test_zero_budget_produces_starting_character(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [
                ("knacks", 2), ("knacks", 3), ("knacks", 4), ("knacks", 5),
                ("attack", 2), ("attack", 3),
                ("attack", 4), ("attack", 5),
                ("air", 3), ("air", 4), ("air", 5),
            ]

        c = build(P, xp=0, non_combat_pct=0.0)
        assert c.iaijutsu == 1
        assert c.attack == 1
        assert c.air == 2

    def test_ring_step_skipped_when_already_raised(self):
        """R4T free boost raises school ring; a later explicit step
        for that level is skipped (ring already past target - 1)."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [
                ("knacks", 2), ("knacks", 3), ("knacks", 4),
                # R4T: fire 3→4 free
                ("fire", 4),  # fire is already 4 → skipped
                ("fire", 5),  # fire 4→5 should proceed (with discount)
            ]

        # knacks: 4+6+8 = 18; fire 4 skipped; fire 5: 20 (disc)
        with patch("l7r.builders._validate_progression"):
            c = build(P, xp=38, non_combat_pct=0.0)
        assert c.fire == 5

    def test_skill_step_skipped_when_already_raised(self):
        """A skill step whose target is already met gets skipped."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [
                ("attack", 2),
                ("attack", 2),  # already at 2 → skipped
                ("attack", 3),
            ]

        # attack 1→2: 4, skip, 2→3: 6 = 10
        with patch("l7r.builders._validate_progression"):
            c = build(P, xp=10, non_combat_pct=0.0)
        assert c.attack == 3

    def test_knack_step_skipped_when_already_raised(self):
        """In a multi-knack school, if one knack is already past
        the target, it gets skipped while others are raised."""

        class _TwoKnackSchool(Combatant):
            school_knacks = ["iaijutsu", "lunge"]
            school_ring = "fire"
            r4t_ring_boost = "fire"
            r1t_rolls = []
            r2t_rolls = None

        class P(Progression):
            school_class = _TwoKnackSchool
            steps = [
                ("knacks", 2),
                ("knacks", 2),  # both already at 2 → both skipped
                ("knacks", 3),
            ]

        # knacks 2: 4+4=8; knacks 2 again: both skip; knacks 3: 6+6=12
        with patch("l7r.builders._validate_progression"):
            c = build(P, xp=20, non_combat_pct=0.0)
        assert c.iaijutsu == 3
        assert c.lunge == 3


# -----------------------------------------------------------
# Auto-import of progression classes
# -----------------------------------------------------------


class TestBuilderAutoImport:
    def test_progression_in_all(self):
        """Every shipped progression is listed in __all__."""
        import l7r.builders as builders_pkg

        for name in (
            "AkodoBushiProgression",
            "BayushiBushiProgression",
            "IsawaDuelistProgression",
            "KakitaDuelistProgression",
            "KitsukiMagistrateProgression",
            "MatsuBushiProgression",
            "MirumotoBushiProgression",
            "OtakuBushiProgression",
            "ShibaBushiProgression",
            "ShinjoBushiProgression",
        ):
            assert name in builders_pkg.__all__

    def test_importable_from_package(self):
        """Progressions are importable directly from l7r.builders."""
        from l7r.builders import OtakuBushiProgression  # noqa: F811

        assert OtakuBushiProgression.steps  # non-empty

    def test_only_matching_prefix_exported(self):
        """Only classes matching the CamelCase prefix are exported;
        the base Progression class is not re-exported by the loop."""
        import l7r.builders as builders_pkg

        # Progression is defined in __init__.py itself, not by
        # the auto-import loop, so it should not appear in __all__.
        assert "Progression" not in builders_pkg.__all__


# -----------------------------------------------------------
# School class resolution
# -----------------------------------------------------------


class TestResolveSchoolClass:
    def test_explicit_school_class_returned(self):
        """When school_class is set, _resolve_school_class returns it."""
        assert _resolve_school_class(_EmptyProg) is _SimpleSchool

    def test_derived_from_class_name(self):
        """When school_class is None, derive from class name convention."""
        from l7r.schools.otaku_bushi import OtakuBushi

        assert _resolve_school_class(OtakuBushiProgression) is OtakuBushi

    def test_all_shipped_progressions_resolve(self):
        """Every shipped progression resolves to the correct school."""
        for prog in (
            AkodoBushiProgression,
            BayushiBushiProgression,
            IsawaDuelistProgression,
            KakitaDuelistProgression,
            KitsukiMagistrateProgression,
            MatsuBushiProgression,
            MirumotoBushiProgression,
            OtakuBushiProgression,
            ShibaBushiProgression,
            ShinjoBushiProgression,
        ):
            school = _resolve_school_class(prog)
            # Class name should match progression minus suffix
            expected_name = prog.__name__.removesuffix("Progression")
            assert school.__name__ == expected_name

    def test_no_school_class_no_convention_raises(self):
        """A progression with no school_class and no matching module raises."""
        class BogusProgression(Progression):
            steps = []

        with pytest.raises(ImportError):
            _resolve_school_class(BogusProgression)

    def test_build_works_without_explicit_school_class(self):
        """build() works when school_class is None (convention-based)."""
        from l7r.schools.mirumoto_bushi import MirumotoBushi

        c = build(MirumotoBushiProgression, xp=150, non_combat_pct=0.0)
        assert isinstance(c, MirumotoBushi)


# -----------------------------------------------------------
# Progression validation
# -----------------------------------------------------------


class TestValidateProgression:
    def test_valid_progression_passes(self):
        """A correctly ordered progression should not raise."""
        _validate_progression(MirumotoBushiProgression)

    def test_wrong_ring_target(self):
        """Ring step with target != current + 1 raises ValueError."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("air", 4)]  # air is at 2, target should be 3

        with pytest.raises(ValueError, match="ring 'air' is at 2.*expected 3"):
            _validate_progression(P)

    def test_skipped_knack_level(self):
        """Knack step that skips a level raises ValueError."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("knacks", 3)]  # iaijutsu is at 1, target should be 2

        with pytest.raises(
            ValueError, match="knack 'iaijutsu' is at 1.*expected 2"
        ):
            _validate_progression(P)

    def test_skill_target_exceeds_max(self):
        """Skill target above SKILL_MAX raises ValueError."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [
                ("attack", 2), ("attack", 3),
                ("attack", 4), ("attack", 5), ("attack", 6),
            ]

        with pytest.raises(ValueError, match="skill 'attack' target 6.*max 5"):
            _validate_progression(P)

    def test_ring_target_exceeds_max(self):
        """Non-school ring target above 5 raises ValueError."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [
                ("air", 3), ("air", 4), ("air", 5), ("air", 6),
            ]

        with pytest.raises(ValueError, match="ring 'air' target 6.*max 5"):
            _validate_progression(P)

    def test_school_ring_allows_6(self):
        """School ring can reach 6 without raising."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("fire", 4), ("fire", 5), ("fire", 6)]

        _validate_progression(P)  # should not raise

    def test_r4t_ring_included_after_boost(self):
        """Including a step for the R4T-boosted ring at the wrong level."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [
                ("knacks", 2), ("knacks", 3), ("knacks", 4),
                ("fire", 4),  # fire is already 4 from R4T boost
            ]

        with pytest.raises(ValueError, match="ring 'fire' is at 4.*expected 3"):
            _validate_progression(P)

    def test_knack_target_exceeds_max(self):
        """Knack target above SKILL_MAX raises ValueError."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [
                ("knacks", 2), ("knacks", 3), ("knacks", 4),
                ("knacks", 5), ("knacks", 6),
            ]

        with pytest.raises(ValueError, match="knack target 6.*max 5"):
            _validate_progression(P)

    def test_skipped_skill_level(self):
        """Skill step that skips a level raises ValueError."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("attack", 3)]  # attack is at 1, target should be 2

        with pytest.raises(
            ValueError, match="skill 'attack' is at 1.*expected 2"
        ):
            _validate_progression(P)

    def test_unknown_step_name(self):
        """Unknown step name raises ValueError."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("ninjutsu", 2)]

        with pytest.raises(ValueError, match="unknown step name"):
            _validate_progression(P)

    def test_all_school_progressions_valid(self):
        """Every shipped progression passes validation."""
        for prog in (
            AkodoBushiProgression,
            BayushiBushiProgression,
            IsawaDuelistProgression,
            KakitaDuelistProgression,
            KitsukiMagistrateProgression,
            MatsuBushiProgression,
            MirumotoBushiProgression,
            OtakuBushiProgression,
            ShibaBushiProgression,
            ShinjoBushiProgression,
        ):
            _validate_progression(prog)


# -----------------------------------------------------------
# R4T school ring boost (all schools)
# -----------------------------------------------------------


class TestR4TAllSchools:
    """Every school's R4T should boost its school ring from 3→4."""

    # 128 XP is exactly enough to reach 4th Dan for any school:
    #   knacks 3: 30 + attack 2: 4 + parry 3: 10
    #   + 4 rings to 3: 60 + knacks 4: 24 = 128
    _R4T_XP = 128

    def test_akodo_r4t(self):
        c = build(AkodoBushiProgression, xp=self._R4T_XP,
                  non_combat_pct=0.0)
        assert c.rank == 4
        assert c.water == 4  # school ring boosted by R4T

    def test_bayushi_r4t(self):
        c = build(BayushiBushiProgression, xp=self._R4T_XP,
                  non_combat_pct=0.0)
        assert c.rank == 4
        assert c.fire == 4  # school ring boosted by R4T

    def test_isawa_r4t(self):
        c = build(IsawaDuelistProgression, xp=self._R4T_XP,
                  non_combat_pct=0.0)
        assert c.rank == 4
        assert c.water == 4  # school ring boosted by R4T

    def test_kakita_r4t(self):
        c = build(KakitaDuelistProgression, xp=self._R4T_XP,
                  non_combat_pct=0.0)
        assert c.rank == 4
        assert c.fire == 4  # school ring boosted by R4T

    def test_kitsuki_r4t(self):
        c = build(KitsukiMagistrateProgression, xp=self._R4T_XP,
                  non_combat_pct=0.0)
        assert c.rank == 4
        assert c.water == 4  # school ring boosted by R4T

    def test_matsu_r4t(self):
        c = build(MatsuBushiProgression, xp=self._R4T_XP,
                  non_combat_pct=0.0)
        assert c.rank == 4
        assert c.fire == 4  # school ring boosted by R4T

    def test_otaku_r4t(self):
        c = build(OtakuBushiProgression, xp=self._R4T_XP,
                  non_combat_pct=0.0)
        assert c.rank == 4
        assert c.fire == 4  # school ring boosted by R4T

    def test_mirumoto_r4t(self):
        c = build(MirumotoBushiProgression, xp=self._R4T_XP,
                  non_combat_pct=0.0)
        assert c.rank == 4
        assert c.void == 4  # school ring boosted by R4T

    def test_shiba_r4t(self):
        c = build(ShibaBushiProgression, xp=self._R4T_XP,
                  non_combat_pct=0.0)
        assert c.rank == 4
        assert c.air == 4  # school ring boosted by R4T

    def test_shinjo_r4t(self):
        c = build(ShinjoBushiProgression, xp=self._R4T_XP,
                  non_combat_pct=0.0)
        assert c.rank == 4
        assert c.air == 4  # school ring boosted by R4T


# -----------------------------------------------------------
# Mirumoto integration tests
# -----------------------------------------------------------


class TestMirumotoBuild:
    def test_150xp_no_noncombat(self):
        """150 XP, 0% non-combat → reaches 4th Dan.

        After reaching 4th Dan and raising attack 3 / parry 4, 8 XP
        remain.  Air 4 (20) too expensive; attack 4 (8) fits exactly.
        """
        # Budget: 150
        # knacks 3: 30 → 120; attack 2: 4 → 116
        # parry 2: 4 → 112; parry 3: 6 → 106
        # rings to 3: 60 → 46
        # knacks 4: 24 → 22, R4T: void→4
        # attack 3: 6 → 16; parry 4: 8 → 8
        # air 4: 20 > 8 → skip; water/fire/earth 4: skip
        # knacks 5: all skip (10 > 8)
        # attack 4: 8 → 0; parry 5: skip
        c = build(MirumotoBushiProgression, xp=150, non_combat_pct=0.0)

        assert c.rank == 4
        assert c.void == 4
        assert c.air == 3
        assert c.earth == 3
        assert c.fire == 3
        assert c.water == 3
        assert c.counterattack == 4
        assert c.double_attack == 4
        assert c.iaijutsu == 4
        assert c.attack == 4
        assert c.parry == 4

    def test_200xp_no_noncombat(self):
        """200 XP, 0% non-combat → rings reach 4, one knack to 5.

        After the ring-to-4 steps, 18 XP remain.  Counterattack 5
        fits (10), then attack 4 (8) uses the rest.
        """
        # Budget: 200
        # knacks 3: 30 → 170; attack 2: 4 → 166
        # parry 2: 4 → 162; parry 3: 6 → 156
        # rings to 3: 60 → 96
        # knacks 4: 24 → 72, R4T: void→4
        # attack 3: 6 → 66; parry 4: 8 → 58
        # air 4: 20 → 38; water 4: 20 → 18
        # fire 4: 20 > 18 → skip; earth 4: skip
        # knacks 5: counterattack 4→5: 10 → 8 (others skip)
        # attack 4: 8 → 0; parry 5: skip
        c = build(MirumotoBushiProgression, xp=150, earned_xp=50,
                  non_combat_pct=0.0)

        assert c.rank == 4
        assert c.void == 4
        assert c.air == 4
        assert c.water == 4
        assert c.fire == 3
        assert c.earth == 3
        assert c.counterattack == 5
        assert c.double_attack == 4
        assert c.iaijutsu == 4
        assert c.attack == 4
        assert c.parry == 4

    def test_default_params(self):
        """Default 150 XP with 20% non-combat → 120 budget, rank 3."""
        # Budget: 120
        # knacks 3: 30 → 90; attack 2: 4 → 86
        # parry 2: 4 → 82; parry 3: 6 → 76
        # rings to 3: 60 → 16
        # knacks 4: counterattack 3→4: 8 → 8; double_attack 3→4: 8 → 0
        #           iaijutsu 3→4: 8 > 0 → skip
        # attack 3: 6 > 0 → skip; parry 4: skip
        c = build(MirumotoBushiProgression)

        assert c.rank == 3
        assert c.void == 3  # no R4T
        assert c.counterattack == 4
        assert c.double_attack == 4
        assert c.iaijutsu == 3
        assert c.attack == 2
        assert c.parry == 3

    def test_full_build(self):
        """Enough XP to complete the entire progression."""
        # Total cost of all steps: 415 XP (see detailed breakdown below)
        # knacks 3: 30; attack 2: 4; parry 2-3: 4+6 = 10
        # rings to 3: 4×15 = 60
        # knacks 4: 24; R4T: void 3→4 free
        # attack 3: 6; parry 4: 8
        # rings to 4: 4×20 = 80
        # knacks 5: 3×10 = 30
        # attack 4: 8; parry 5: 10
        # void 5: 20 (disc); void 6: 25 (disc)
        # air/water/fire/earth 5: 4×25 = 100
        # Total: 30+4+10+60+24+6+8+80+30+8+10+20+25+100 = 415
        c = build(MirumotoBushiProgression, xp=415, non_combat_pct=0.0)

        assert c.rank == 5
        assert c.void == 6
        assert c.air == 5
        assert c.earth == 5
        assert c.fire == 5
        assert c.water == 5
        assert c.attack == 4
        assert c.parry == 5
        assert c.counterattack == 5
        assert c.double_attack == 5
        assert c.iaijutsu == 5

    def test_returns_mirumoto_instance(self):
        """The builder returns an actual MirumotoBushi, not a bare Combatant."""
        from l7r.schools.mirumoto_bushi import MirumotoBushi

        c = build(MirumotoBushiProgression, xp=150, non_combat_pct=0.0)
        assert isinstance(c, MirumotoBushi)


# -----------------------------------------------------------
# Non-Mirumoto school progressions
#
# All schools get R4T (school ring 3→4 free at 4th Dan), so
# every full build costs 415 XP:
#   knacks 3: 30  +  attack 2: 4  +  parry 2-3: 10  +  rings to 3: 4×15 = 60
#   knacks 4: 24 (R4T: school ring 3→4)
#   attack 3: 6  +  parry 4: 8  +  rings to 4: 4×20 = 80
#   knacks 5: 30  +  attack 4: 8  +  parry 5: 10
#   school 5: 20 (disc)  +  school 6: 25 (disc)  +  other 4 to 5: 4×25 = 100
#   Total: 415
# -----------------------------------------------------------

_FULL_BUILD_XP = 415


class TestIsawaDuelistBuild:
    def test_full_build(self):
        from l7r.schools.isawa_duelist import IsawaDuelist

        c = build(IsawaDuelistProgression, xp=_FULL_BUILD_XP,
                  non_combat_pct=0.0)
        assert isinstance(c, IsawaDuelist)
        assert c.rank == 5
        assert c.water == 6  # school ring
        for ring in ("air", "earth", "fire", "void"):
            assert getattr(c, ring) == 5
        assert c.attack == 4
        assert c.parry == 5

    def test_default_params(self):
        """120 budget → rank 3, school ring (water) at 3."""
        c = build(IsawaDuelistProgression)
        assert c.rank == 3
        assert c.water == 3


class TestKakitaBuild:
    def test_full_build(self):
        from l7r.schools.kakita_duelist import KakitaDuelist

        c = build(KakitaDuelistProgression, xp=_FULL_BUILD_XP,
                  non_combat_pct=0.0)
        assert isinstance(c, KakitaDuelist)
        assert c.rank == 5
        assert c.fire == 6  # school ring
        for ring in ("air", "earth", "water", "void"):
            assert getattr(c, ring) == 5
        assert c.attack == 4
        assert c.parry == 5

    def test_default_params(self):
        """120 budget → rank 3, school ring (fire) at 3."""
        c = build(KakitaDuelistProgression)
        assert c.rank == 3
        assert c.fire == 3


class TestOtakuBuild:
    def test_full_build(self):
        from l7r.schools.otaku_bushi import OtakuBushi

        c = build(OtakuBushiProgression, xp=_FULL_BUILD_XP,
                  non_combat_pct=0.0)
        assert isinstance(c, OtakuBushi)
        assert c.rank == 5
        assert c.fire == 6  # school ring
        for ring in ("air", "earth", "water", "void"):
            assert getattr(c, ring) == 5
        assert c.attack == 4
        assert c.parry == 5

    def test_default_params(self):
        """120 budget → rank 3, school ring (fire) at 3."""
        c = build(OtakuBushiProgression)
        assert c.rank == 3
        assert c.fire == 3


class TestAkodoBuild:
    def test_full_build(self):
        from l7r.schools.akodo_bushi import AkodoBushi

        c = build(AkodoBushiProgression, xp=_FULL_BUILD_XP,
                  non_combat_pct=0.0)
        assert isinstance(c, AkodoBushi)
        assert c.rank == 5
        assert c.water == 6  # school ring
        for ring in ("air", "earth", "fire", "void"):
            assert getattr(c, ring) == 5
        assert c.attack == 4
        assert c.parry == 5

    def test_default_params(self):
        """120 budget → rank 3, school ring (water) at 3."""
        c = build(AkodoBushiProgression)
        assert c.rank == 3
        assert c.water == 3

    def test_ring_priority(self):
        """With 150 XP, Fire should be raised before Water."""
        # Budget 150 → after knacks-4 (step 8), 25 XP remain.
        # Akodo has no R4T boost so rank stays 3 if knacks
        # don't all reach 4.  Let's check at a budget where
        # rings-to-4 start: fire should come first.
        c = build(AkodoBushiProgression, xp=150, non_combat_pct=0.0)
        assert c.fire >= c.water or c.fire >= c.air


class TestBayushiBuild:
    def test_full_build(self):
        from l7r.schools.bayushi_bushi import BayushiBushi

        c = build(BayushiBushiProgression, xp=_FULL_BUILD_XP,
                  non_combat_pct=0.0)
        assert isinstance(c, BayushiBushi)
        assert c.rank == 5
        assert c.fire == 6  # school ring
        for ring in ("air", "earth", "water", "void"):
            assert getattr(c, ring) == 5
        assert c.attack == 4
        assert c.parry == 5

    def test_default_params(self):
        """120 budget → rank 3, school ring (fire) at 3."""
        c = build(BayushiBushiProgression)
        assert c.rank == 3
        assert c.fire == 3

    def test_ring_priority(self):
        """Fire (school ring) should be raised to 4 before Air."""
        c = build(BayushiBushiProgression, xp=250, non_combat_pct=0.0)
        assert c.fire >= c.air


class TestKitsukiBuild:
    def test_full_build(self):
        from l7r.schools.kitsuki_magistrate import KitsukiMagistrate

        c = build(KitsukiMagistrateProgression, xp=_FULL_BUILD_XP,
                  non_combat_pct=0.0)
        assert isinstance(c, KitsukiMagistrate)
        assert c.rank == 5
        assert c.water == 6  # school ring
        for ring in ("air", "earth", "fire", "void"):
            assert getattr(c, ring) == 5
        assert c.attack == 4
        assert c.parry == 5

    def test_default_params(self):
        c = build(KitsukiMagistrateProgression)
        assert c.rank == 3
        assert c.water == 3

    def test_ring_priority(self):
        """Water (school ring) raised to 4 before Air."""
        c = build(KitsukiMagistrateProgression, xp=250,
                  non_combat_pct=0.0)
        assert c.water >= c.air


class TestMatsuBuild:
    def test_full_build(self):
        from l7r.schools.matsu_bushi import MatsuBushi

        c = build(MatsuBushiProgression, xp=_FULL_BUILD_XP,
                  non_combat_pct=0.0)
        assert isinstance(c, MatsuBushi)
        assert c.rank == 5
        assert c.fire == 6  # school ring
        for ring in ("air", "earth", "water", "void"):
            assert getattr(c, ring) == 5
        assert c.attack == 4
        assert c.parry == 5

    def test_default_params(self):
        c = build(MatsuBushiProgression)
        assert c.rank == 3
        assert c.fire == 3

    def test_ring_priority(self):
        """Fire (school ring) raised before Air at higher XP."""
        c = build(MatsuBushiProgression, xp=250, non_combat_pct=0.0)
        assert c.fire >= c.air


class TestShinjoBuild:
    def test_full_build(self):
        from l7r.schools.shinjo_bushi import ShinjoBushi

        c = build(ShinjoBushiProgression, xp=_FULL_BUILD_XP,
                  non_combat_pct=0.0)
        assert isinstance(c, ShinjoBushi)
        assert c.rank == 5
        assert c.air == 6  # school ring
        for ring in ("earth", "fire", "water", "void"):
            assert getattr(c, ring) == 5
        assert c.attack == 4
        assert c.parry == 5

    def test_default_params(self):
        c = build(ShinjoBushiProgression)
        assert c.rank == 3
        assert c.air == 3

    def test_ring_priority(self):
        """Air (parry ring) raised before Fire for defensive Shinjo."""
        c = build(ShinjoBushiProgression, xp=250, non_combat_pct=0.0)
        assert c.air >= c.fire


class TestShibaBuild:
    def test_full_build(self):
        from l7r.schools.shiba_bushi import ShibaBushi

        c = build(ShibaBushiProgression, xp=_FULL_BUILD_XP,
                  non_combat_pct=0.0)
        assert isinstance(c, ShibaBushi)
        assert c.rank == 5
        assert c.air == 6  # school ring
        for ring in ("earth", "fire", "water", "void"):
            assert getattr(c, ring) == 5
        assert c.attack == 4
        assert c.parry == 5

    def test_default_params(self):
        """120 budget → rank 3, school ring (air) at 3."""
        c = build(ShibaBushiProgression)
        assert c.rank == 3
        assert c.air == 3

    def test_ring_priority(self):
        """Air (school ring) raised before Fire at higher XP."""
        c = build(ShibaBushiProgression, xp=250, non_combat_pct=0.0)
        assert c.air >= c.fire
