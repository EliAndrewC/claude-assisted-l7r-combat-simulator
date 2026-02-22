"""Tests for the character builder and XP cost functions."""

from __future__ import annotations

from l7r.combatant import Combatant
from l7r.builders import (
    Progression,
    build,
    _ring_cost,
    _basic_skill_cost,
    _advanced_skill_cost,
)
from l7r.builders.mirumoto_bushi import MirumotoBushiProgression


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

    def test_skills_start_at_0(self):
        c = build(_EmptyProg, xp=150, non_combat_pct=0.0)
        assert c.attack == 0
        assert c.parry == 0


# -----------------------------------------------------------
# Ring steps
# -----------------------------------------------------------


class TestBuildRings:
    def test_raises_ring_to_target(self):
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

    def test_school_ring_already_at_3(self):
        """School ring starts at 3, so ("fire", 3) is a no-op."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("fire", 3)]

        c = build(P, xp=150, non_combat_pct=0.0)
        assert c.fire == 3

    def test_ring_max_5_for_non_school(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("air", 7)]

        c = build(P, xp=500, non_combat_pct=0.0)
        assert c.air == 5

    def test_ring_max_6_for_school_ring(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("fire", 7)]

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

        c = build(P, xp=4, non_combat_pct=0.0)  # 0→1: 2, 1→2: 2
        assert c.attack == 2

    def test_raises_parry(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("parry", 3)]

        c = build(P, xp=7, non_combat_pct=0.0)  # 0→1: 2, 1→2: 2, 2→3: 3
        assert c.parry == 3

    def test_partial_skill_raise(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("attack", 2)]

        c = build(P, xp=3, non_combat_pct=0.0)  # only enough for 0→1
        assert c.attack == 1

    def test_skill_max_5(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("attack", 7)]

        c = build(P, xp=500, non_combat_pct=0.0)
        assert c.attack == 5


# -----------------------------------------------------------
# Knack steps
# -----------------------------------------------------------


class TestBuildKnacks:
    def test_raises_knack_to_target(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("knacks", 3)]

        c = build(P, xp=10, non_combat_pct=0.0)  # 1→2: 4, 2→3: 6
        assert c.iaijutsu == 3
        assert c.rank == 3

    def test_partial_knack_raise(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("knacks", 3)]

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
            steps = [("knacks", 7)]

        c = build(P, xp=500, non_combat_pct=0.0)
        assert c.iaijutsu == 5


# -----------------------------------------------------------
# R4T ring boost & discount
# -----------------------------------------------------------


class TestR4T:
    def test_free_ring_boost_at_4th_dan(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("knacks", 4)]

        # iaijutsu 1→2: 4, 2→3: 6, 3→4: 8 = 18 XP
        # R4T triggers: fire (r4t_ring_boost) 3→4 for free
        c = build(P, xp=18, non_combat_pct=0.0)
        assert c.iaijutsu == 4
        assert c.rank == 4
        assert c.fire == 4

    def test_no_boost_before_4th_dan(self):
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("knacks", 3)]

        c = build(P, xp=10, non_combat_pct=0.0)
        assert c.iaijutsu == 3
        assert c.fire == 3  # school ring starting value, no boost

    def test_school_ring_discount_after_4th_dan(self):
        """After 4th Dan, school ring raises cost 5 fewer XP."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("knacks", 4), ("fire", 5)]

        # knacks: 4 + 6 + 8 = 18 XP, R4T: fire→4 free
        # fire 4→5: 5×5 − 5 = 20 XP (discounted)
        # Total: 38 XP
        c = build(P, xp=38, non_combat_pct=0.0)
        assert c.fire == 5

    def test_discount_not_enough_xp(self):
        """Verify the discount is exactly 5 — 37 XP shouldn't be enough."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("knacks", 4), ("fire", 5)]

        c = build(P, xp=37, non_combat_pct=0.0)
        assert c.fire == 4

    def test_no_discount_without_4th_dan(self):
        """Without 4th Dan, school ring raise is full price."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("fire", 5)]

        # fire 3→4: 20, 4→5: 25 = 45 XP (no discount)
        c = build(P, xp=44, non_combat_pct=0.0)
        assert c.fire == 4  # can't afford 5

    def test_non_school_ring_no_discount(self):
        """Non-school rings never get the discount even after 4th Dan."""
        class P(Progression):
            school_class = _SimpleSchool
            steps = [("knacks", 4), ("air", 4)]

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
            steps = [("knacks", 5), ("attack", 5), ("air", 5)]

        c = build(P, xp=0, non_combat_pct=0.0)
        assert c.iaijutsu == 1
        assert c.attack == 0
        assert c.air == 2


# -----------------------------------------------------------
# Mirumoto integration tests
# -----------------------------------------------------------


class TestMirumotoBuild:
    def test_150xp_no_noncombat(self):
        """150 XP, 0% non-combat → reaches 4th Dan, rings at 3.

        After reaching 4th Dan and raising attack 3 / parry 4, 19 XP
        remain.  The four ring-to-4 steps (20 each) all skip, but
        cheaper steps further down the progression still fire:
        counterattack to 5 (10), attack to 4 (3), parry to 5 (3).
        """
        # Budget: 150
        # knacks 3: 30 → 120; attack 2: 4 → 116; parry 3: 7 → 109
        # rings to 3: 60 → 49
        # knacks 4: 24 → 25, R4T: void→4
        # attack 3: 3 → 22; parry 4: 3 → 19
        # air/earth/water/fire 4: 20 each, all skip
        # knacks 5: counterattack 4→5: 10 → 9 (others skip)
        # attack 4: 3 → 6; parry 5: 3 → 3
        # remaining rings to 5: all skip
        c = build(MirumotoBushiProgression, xp=150, non_combat_pct=0.0)

        assert c.rank == 4
        assert c.void == 4
        assert c.air == 3
        assert c.earth == 3
        assert c.fire == 3
        assert c.water == 3
        assert c.counterattack == 5
        assert c.double_attack == 4
        assert c.iaijutsu == 4
        assert c.attack == 4
        assert c.parry == 5

    def test_200xp_no_noncombat(self):
        """200 XP, 0% non-combat → rings start reaching 4.

        After the ring-to-4 steps, 9 XP remain — not enough for
        knacks 5 (10 each) but enough for attack 4 (3) and parry 5 (3).
        """
        # After parry 4: spent 131, remaining 69
        # air 4: 20 → 49; earth 4: 20 → 29; water 4: 20 → 9
        # fire 4: 20 > 9 → skip
        # knacks 5: 10 each > 9 → all skip
        # attack 4: 3 → 6; parry 5: 3 → 3
        c = build(MirumotoBushiProgression, xp=150, earned_xp=50,
                  non_combat_pct=0.0)

        assert c.rank == 4
        assert c.void == 4
        assert c.air == 4
        assert c.earth == 4
        assert c.water == 4
        assert c.fire == 3
        assert c.attack == 4
        assert c.parry == 5

    def test_default_params(self):
        """Default 150 XP with 20% non-combat → 120 budget, rank 3."""
        # Budget: 120
        # knacks 3: 30 → 90; attack 2: 4 → 86; parry 3: 7 → 79
        # rings to 3: 60 → 19
        # knacks 4: counterattack 3→4: 8 → 11; double_attack 3→4: 8 → 3
        #           iaijutsu 3→4: 8 > 3 → skip
        # attack 3: 3 → 0; parry 4: budget exhausted
        c = build(MirumotoBushiProgression)

        assert c.rank == 3
        assert c.void == 3  # no R4T
        assert c.counterattack == 4
        assert c.double_attack == 4
        assert c.iaijutsu == 3
        assert c.attack == 3
        assert c.parry == 3

    def test_full_build(self):
        """Enough XP to complete the entire progression."""
        # Total cost of all steps: 367 XP (see detailed breakdown below)
        # knacks 3: 30; attack 2: 4; parry 3: 7
        # rings to 3: 60
        # knacks 4: 24; R4T: void→4 free
        # attack 3: 3; parry 4: 3
        # rings to 4: air 20 + earth 20 + water 20 + fire 20 = 80
        # knacks 5: 3×10 = 30
        # attack 4: 3; parry 5: 3
        # void 5: 25−5=20; air 5: 25; earth 5: 25; water 5: 25; fire 5: 25
        # Total: 30+4+7+60+24+3+3+80+30+3+3+20+25+25+25+25 = 367
        c = build(MirumotoBushiProgression, xp=367, non_combat_pct=0.0)

        assert c.rank == 5
        assert c.void == 5
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
        from l7r.schools.MirumotoBushi import MirumotoBushi

        c = build(MirumotoBushiProgression, xp=150, non_combat_pct=0.0)
        assert isinstance(c, MirumotoBushi)
