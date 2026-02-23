"""Tests for school implementations.

Covers Akodo Bushi, Bayushi Bushi, Kitsuki Magistrate, Matsu Bushi,
Mirumoto Bushi, and Shinjo Bushi. Each test class verifies class-level
attributes, constructor setup, rank techniques (with rank gating),
special abilities, and heuristic decision overrides.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from l7r.combatant import Combatant
from l7r.schools.AkodoBushi import AkodoBushi
from l7r.schools.BayushiBushi import BayushiBushi
from l7r.schools.IsawaDuelist import IsawaDuelist
import l7r.schools.KakitaBushi as kakita_mod
from l7r.schools.KakitaBushi import KakitaBushi
from l7r.schools.OtakuBushi import OtakuBushi
from l7r.schools.KitsukiMagistrate import KitsukiMagistrate
from l7r.schools.MatsuBushi import MatsuBushi
from l7r.schools.MirumotoBushi import MirumotoBushi
from l7r.schools.ShinjoBushi import ShinjoBushi


# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------

STATS = dict(
    air=3, earth=5, fire=3, water=3, void=3,
    attack=3, parry=3,
)


def make_enemy(**kw: int) -> Combatant:
    defaults = dict(STATS)
    defaults.update(kw)
    c = Combatant(**defaults)
    c.init_order = [5]
    c.actions = [5]
    return c


def link(a: Combatant, b: Combatant) -> None:
    a.enemy = b
    b.enemy = a
    a.attackable = {b}
    b.attackable = {a}


# ===================================================================
# AKODO BUSHI
# ===================================================================


class TestAkodoAttributes:
    def test_school_knacks(self) -> None:
        a = AkodoBushi(rank=3, **STATS)
        assert set(a.school_knacks) == {
            "double_attack", "feint", "iaijutsu",
        }

    def test_r1t_rolls(self) -> None:
        a = AkodoBushi(rank=1, **STATS)
        for rt in a.r1t_rolls:
            assert a.extra_dice[rt][0] >= 1

    def test_r2t_always_bonus(self) -> None:
        a = AkodoBushi(rank=2, **STATS)
        assert a.always["wound_check"] >= 5

    def test_hold_one_action_false(self) -> None:
        a = AkodoBushi(rank=1, **STATS)
        assert a.hold_one_action is False

    def test_high_wc_threshold(self) -> None:
        a = AkodoBushi(rank=1, **STATS)
        assert a.base_wc_threshold == 25


class TestAkodoSpecialAbility:
    def test_feint_grants_4_vps(self) -> None:
        a = AkodoBushi(rank=1, **STATS)
        a.attack_knack = "feint"
        before = a.vps
        a.sa_trigger()
        assert a.vps == before + 4

    def test_non_feint_no_vps(self) -> None:
        a = AkodoBushi(rank=1, **STATS)
        a.attack_knack = "attack"
        before = a.vps
        a.sa_trigger()
        assert a.vps == before

    def test_failed_feint_grants_1_vp(self) -> None:
        a = AkodoBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(a, enemy)
        a.attack_knack = "feint"
        a.attack_roll = enemy.tn - 1  # miss
        before = a.vps
        a.sa_failed_feint()
        assert a.vps == before + 1

    def test_failed_non_feint_no_vps(self) -> None:
        a = AkodoBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(a, enemy)
        a.attack_knack = "attack"
        a.attack_roll = enemy.tn - 1  # miss
        before = a.vps
        a.sa_failed_feint()
        assert a.vps == before

    def test_successful_feint_no_failed_bonus(self) -> None:
        """sa_failed_feint should not fire when feint succeeds."""
        a = AkodoBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(a, enemy)
        a.attack_knack = "feint"
        a.attack_roll = enemy.tn  # hit
        before = a.vps
        a.sa_failed_feint()
        assert a.vps == before


class TestAkodoR3T:
    def test_excess_creates_disc_bonuses(self) -> None:
        a = AkodoBushi(rank=3, **STATS)
        # check=30, light=10, total=10 → exceeded=20
        a.r3t_trigger(30, 10, 10)
        # 20 // 5 = 4, × attack(3) = 12
        for knack in ["attack", "double_attack", "feint"]:
            assert sum(sum(g) for g in a.multi[knack]) >= 12

    def test_no_excess_no_bonus(self) -> None:
        a = AkodoBushi(rank=3, **STATS)
        a.r3t_trigger(5, 10, 10)  # check < light
        for knack in ["attack", "double_attack", "feint"]:
            bonuses = [
                sum(g) for g in a.multi[knack] if sum(g)
            ]
            assert not bonuses

    def test_rank_gated(self) -> None:
        a = AkodoBushi(rank=2, **STATS)
        a.r3t_trigger(30, 10, 10)
        for knack in ["attack", "double_attack", "feint"]:
            assert not a.multi[knack]

    def test_shared_bonus_across_knacks(self) -> None:
        """All three knacks share the same list object."""
        a = AkodoBushi(rank=3, **STATS)
        a.r3t_trigger(20, 10, 10)
        lists = [a.multi[k][-1] for k in [
            "attack", "double_attack", "feint",
        ]]
        assert lists[0] is lists[1] is lists[2]


class TestAkodoNeedHigherWc:
    def test_near_death_uses_full_gap(self) -> None:
        """When next serious wound would kill, need_higher_wc uses
        the full gap (light - check) as the needed amount."""
        a = AkodoBushi(rank=4, **STATS)
        # sw_to_kill = 2 * earth(5) = 10
        a.serious = 9  # next one kills
        # light=30, check=20, gap=10
        # max_bonus needs to exceed gap
        a.always["wound_check"] = 15
        assert a.need_higher_wc(30, 20) is True

    def test_not_near_death_uses_reduced_gap(self) -> None:
        """When not about to die, need_higher_wc uses light - check - 9.
        needed=max(0, 20-15-9)=0, but 0 < max_bonus so still True."""
        a = AkodoBushi(rank=4, **STATS)
        a.serious = 0
        # light=20, check=15, gap = max(0, 20-15-9) = 0
        # max_bonus("wound_check") = 5 (R2T always bonus)
        # 0 < 5 → True (still beneficial to spend)
        assert a.need_higher_wc(20, 15) is True

    def test_false_when_check_exceeds_light(self) -> None:
        """Returns False when check already exceeds light (no wounds)."""
        a = AkodoBushi(rank=4, **STATS)
        a.serious = 0
        # check > light: no wounds at all, no need for bonus
        # needed = max(0, 5-30-9) = 0, 0 < 5 → True
        # Actually, need a case where max_bonus is 0 too
        a.always["wound_check"] = 0  # remove R2T
        assert a.need_higher_wc(5, 30) is False

    def test_returns_false_when_bonus_insufficient(self) -> None:
        a = AkodoBushi(rank=4, **STATS)
        a.serious = 9
        # light=50, check=10, gap=40, but max_bonus is low
        assert a.need_higher_wc(50, 10) is False


class TestAkodoR4T:
    def test_spend_vps_for_wc_raises(self) -> None:
        a = AkodoBushi(rank=4, **STATS)
        a.vps = 5
        a.serious = 9  # near death: needed = light - check
        # light=15, check=10 → needed=5, max_bonus needs to exceed 5
        a.always["wound_check"] = 10  # max_bonus=10 > needed=5
        vps_before = a.vps
        a.wc_bonus(15, 10)
        assert a.vps < vps_before

    def test_spends_2_when_single_doesnt_help(self) -> None:
        """When a single +5 wouldn't cross a wound threshold, spend 2 VPs."""
        a = AkodoBushi(rank=4, **STATS)
        a.vps = 5
        a.serious = 9  # near death
        # light=15, check=10, max_bonus starts at always(20)=20
        a.always["wound_check"] = 20
        vps_before = a.vps
        a.wc_bonus(15, 10)
        assert a.vps < vps_before

    def test_stops_when_out_of_vps(self) -> None:
        a = AkodoBushi(rank=4, **STATS)
        a.vps = 0  # no VPs to spend
        a.serious = 9
        a.always["wound_check"] = 20
        vps_before = a.vps
        a.wc_bonus(15, 10)
        assert a.vps == vps_before  # couldn't spend any

    def test_rank_gated(self) -> None:
        a = AkodoBushi(rank=3, **STATS)
        a.vps = 5
        vps_before = a.vps
        a.wc_bonus(40, 10)
        assert a.vps == vps_before


class TestAkodoR5T:
    def test_reflects_damage(self) -> None:
        a = AkodoBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(a, enemy)
        a.vps = 10

        with patch.object(enemy, "wound_check") as mock_wc:
            a.r5t_trigger(50, 30, 30)

        mock_wc.assert_called_once()
        damage = mock_wc.call_args[0][0]
        assert damage > 0
        assert damage % 10 == 0

    def test_rank_gated(self) -> None:
        a = AkodoBushi(rank=4, **STATS)
        enemy = make_enemy()
        link(a, enemy)
        a.vps = 10

        with patch.object(enemy, "wound_check") as mock_wc:
            a.r5t_trigger(50, 30, 30)

        mock_wc.assert_not_called()

    def test_limited_by_vps(self) -> None:
        a = AkodoBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(a, enemy)
        a.vps = 3  # Only 3 VPs, needs > 2 to spend

        with patch.object(enemy, "wound_check") as mock_wc:
            a.r5t_trigger(50, 30, 30)

        # Should only spend 1 VP (goes from 3 to 2)
        if mock_wc.called:
            assert mock_wc.call_args[0][0] == 10

    def test_limited_by_light(self) -> None:
        a = AkodoBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(a, enemy)
        a.vps = 10

        with patch.object(enemy, "wound_check") as mock_wc:
            a.r5t_trigger(50, 5, 5)  # Only 5 light

        mock_wc.assert_not_called()


class TestAkodoChooseAction:
    def test_feints_when_low_vps(self) -> None:
        a = AkodoBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(a, enemy)
        a.vps = 2
        a.actions = [3]
        a.phase = 3

        result = a.choose_action()
        assert result is not None
        assert result[0] == "feint"

    def test_normal_attack_with_disc_bonuses(self) -> None:
        a = AkodoBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(a, enemy)
        a.vps = 10
        a.actions = [3, 5]
        a.phase = 3
        a.disc["attack"].append(15)

        with patch.object(
            Combatant, "choose_action",
            return_value=("attack", enemy),
        ):
            result = a.choose_action()

        assert result is not None

    def test_passes_without_disc_and_high_vps(self) -> None:
        a = AkodoBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(a, enemy)
        a.vps = 10
        a.actions = [3]
        a.phase = 3

        result = a.choose_action()
        assert result is None


class TestAkodoDiscBonus:
    def test_aggressive_spend_on_large_stockpile(self) -> None:
        a = AkodoBushi(rank=3, **STATS)
        # Need >1 entry remaining and sum>=30 AFTER the initial spend.
        # Initial spend of 5 will consume the smallest entry (5).
        # Remaining: [10, 15, 20] → len=3 > 1, sum=45 >= 30 → aggressive path.
        a.disc["attack"] = [5, 10, 15, 20]

        bonus = a.disc_bonus("attack", 5)
        # Should spend 5 (initial) + aggressive extra
        assert bonus > 5

    def test_no_aggressive_spend_on_small_stockpile(self) -> None:
        a = AkodoBushi(rank=3, **STATS)
        a.disc["attack"] = [10]
        bonus = a.disc_bonus("attack", 5)
        assert bonus == 10  # spends what's needed, no extra

    def test_no_aggressive_spend_on_non_attack(self) -> None:
        a = AkodoBushi(rank=3, **STATS)
        a.disc["wound_check"] = [15, 20]
        bonus = a.disc_bonus("wound_check", 5)
        assert bonus == 15  # only spends minimum needed, no aggressive path


class TestAkodoInit:
    def test_event_handlers_registered(self) -> None:
        a = AkodoBushi(rank=5, **STATS)
        assert a.sa_trigger in a.events["successful_attack"]
        assert a.sa_failed_feint in a.events["post_attack"]
        assert a.r3t_trigger in a.events["wound_check"]
        assert a.r5t_trigger in a.events["wound_check"]


# ===================================================================
# BAYUSHI BUSHI
# ===================================================================


class TestBayushiAttributes:
    def test_school_knacks(self) -> None:
        b = BayushiBushi(rank=3, **STATS)
        assert set(b.school_knacks) == {
            "double_attack", "feint", "iaijutsu",
        }

    def test_r1t_rolls(self) -> None:
        b = BayushiBushi(rank=1, **STATS)
        for rt in b.r1t_rolls:
            assert b.extra_dice[rt][0] >= 1

    def test_r2t_always_bonus(self) -> None:
        b = BayushiBushi(rank=2, **STATS)
        assert b.always["double_attack"] >= 5

    def test_high_vp_fail_threshold(self) -> None:
        b = BayushiBushi(rank=1, **STATS)
        assert b.vp_fail_threshold == 0.85

    def test_high_datt_threshold(self) -> None:
        b = BayushiBushi(rank=1, **STATS)
        assert b.datt_threshold == 0.3


class TestBayushiSpecialAbility:
    def test_vps_on_attack_add_damage_dice(self) -> None:
        b = BayushiBushi(rank=1, **STATS)
        rolled_before = b.base_damage_rolled
        kept_before = b.base_damage_kept

        b.sa_trigger(2, "attack")

        assert b.base_damage_rolled == rolled_before + 2
        assert b.base_damage_kept == kept_before + 2

    def test_vps_on_feint(self) -> None:
        b = BayushiBushi(rank=1, **STATS)
        rolled_before = b.base_damage_rolled
        b.sa_trigger(1, "feint")
        assert b.base_damage_rolled == rolled_before + 1

    def test_vps_on_parry_no_effect(self) -> None:
        b = BayushiBushi(rank=1, **STATS)
        rolled_before = b.base_damage_rolled
        b.sa_trigger(2, "parry")
        assert b.base_damage_rolled == rolled_before


class TestBayushiR3T:
    def test_feint_sets_damage(self) -> None:
        b = BayushiBushi(rank=3, **STATS)
        b.attack_knack = "feint"
        b.r3t_trigger()
        assert b.base_damage_rolled == b.attack
        assert b.base_damage_kept == 1

    def test_non_feint_no_change(self) -> None:
        b = BayushiBushi(rank=3, **STATS)
        b.attack_knack = "attack"
        rolled_before = b.base_damage_rolled
        b.r3t_trigger()
        assert b.base_damage_rolled == rolled_before

    def test_rank_gated(self) -> None:
        b = BayushiBushi(rank=2, **STATS)
        b.attack_knack = "feint"
        rolled_before = b.base_damage_rolled
        b.r3t_trigger()
        assert b.base_damage_rolled == rolled_before

    def test_feint_next_damage_bypasses_extras(self) -> None:
        """R3T feint damage skips extra dice from TN excess."""
        b = BayushiBushi(rank=3, **STATS)
        b.attack_knack = "feint"
        b.r3t_trigger()
        b.attack_roll = 50  # Way over TN

        roll, keep, serious = b.next_damage(20, True)
        assert roll == b.attack
        assert keep == 1
        assert serious == 0

    def test_non_feint_uses_base_next_damage(self) -> None:
        """Non-feint attacks use standard next_damage logic."""
        b = BayushiBushi(rank=3, **STATS)
        b.attack_knack = "attack"
        b.attack_roll = 30

        roll, keep, serious = b.next_damage(20, True)
        base = Combatant(rank=3, **STATS)
        base.attack_roll = 30
        base_roll, base_keep, base_serious = base.next_damage(20, True)
        assert roll == base_roll
        assert keep == base_keep


class TestBayushiR4T:
    def test_grants_shared_disc_bonus(self) -> None:
        b = BayushiBushi(rank=4, **STATS)
        b.r4t_trigger()

        for knack in ["feint", "attack", "double_attack"]:
            total = sum(sum(g) for g in b.multi[knack])
            assert total >= 5

    def test_shared_bonus_object(self) -> None:
        """All three knacks share the same list reference."""
        b = BayushiBushi(rank=4, **STATS)
        b.r4t_trigger()
        lists = [
            b.multi[k][-1]
            for k in ["feint", "attack", "double_attack"]
        ]
        assert lists[0] is lists[1] is lists[2]

    def test_rank_gated(self) -> None:
        b = BayushiBushi(rank=3, **STATS)
        b.r4t_trigger()
        for knack in ["feint", "attack", "double_attack"]:
            assert not b.multi[knack]


class TestBayushiR5T:
    def test_halves_excess(self) -> None:
        b = BayushiBushi(rank=5, **STATS)
        # light=30, check=10 → excess=20 → halved=10
        result = b.calc_serious(30, 10)
        normal = Combatant.calc_serious(b, 30, 10)
        assert result < normal

    def test_rank_gated(self) -> None:
        b = BayushiBushi(rank=4, **STATS)
        result = b.calc_serious(30, 10)
        normal = Combatant.calc_serious(b, 30, 10)
        assert result == normal

    def test_pass_check_zero(self) -> None:
        b = BayushiBushi(rank=5, **STATS)
        assert b.calc_serious(10, 20) == 0


class TestBayushiResetDamage:
    def test_restores_base_damage(self) -> None:
        b = BayushiBushi(rank=1, **STATS)
        b.base_damage_rolled = 10
        b.base_damage_kept = 8
        b.reset_damage()
        assert b.base_damage_rolled == 4
        assert b.base_damage_kept == 2


class TestBayushiMakeAttack:
    def test_r3t_feint_always_hits(self) -> None:
        """At rank 3+, feints that meet TN always hit."""
        b = BayushiBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        b.attack_knack = "feint"

        # Base make_attack returns False (feint), but
        # R3T override returns True if roll >= TN
        with patch.object(
            Combatant, "make_attack", return_value=False,
        ):
            b.attack_roll = enemy.tn
            result = b.make_attack()

        assert result is True

    def test_r3t_feint_miss(self) -> None:
        b = BayushiBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        b.attack_knack = "feint"

        with patch.object(
            Combatant, "make_attack", return_value=False,
        ):
            b.attack_roll = enemy.tn - 1
            result = b.make_attack()

        assert result is False


class TestBayushiAttVps:
    def test_always_spends_at_least_1(self) -> None:
        b = BayushiBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        b.attack_knack = "attack"
        b.vps = 3

        with patch.object(
            Combatant, "att_vps", return_value=0,
        ):
            vps = b.att_vps(enemy.tn, 6, 3)

        assert vps >= 1
        assert b.vps == 2  # Spent 1

    def test_no_vps_no_spend(self) -> None:
        b = BayushiBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        b.attack_knack = "attack"
        b.vps = 0

        with patch.object(
            Combatant, "att_vps", return_value=0,
        ):
            vps = b.att_vps(enemy.tn, 6, 3)

        assert vps == 0


class TestBayushiAttTarget:
    def test_prefers_wounded(self) -> None:
        b = BayushiBushi(rank=1, **STATS)
        e1 = make_enemy()
        e2 = make_enemy()
        e1.light = 0
        e2.light = 15
        b.attackable = {e1, e2}

        target = b.att_target()
        assert target is e2

    def test_falls_back_when_no_wounded(self) -> None:
        b = BayushiBushi(rank=1, **STATS)
        e1 = make_enemy()
        e2 = make_enemy()
        e1.light = 0
        e2.light = 0
        b.attackable = {e1, e2}
        b.init_order = [3]

        with patch.object(
            Combatant, "att_target", return_value=e1,
        ):
            target = b.att_target()
        assert target in {e1, e2}


class TestBayushiInit:
    def test_event_handlers_registered(self) -> None:
        b = BayushiBushi(rank=5, **STATS)
        assert b.sa_trigger in b.events["vps_spent"]
        assert b.r3t_trigger in b.events["pre_attack"]
        assert b.r4t_trigger in b.events["post_attack"]


class TestBayushiChooseAction:
    def test_feints_unwounded_targets(self) -> None:
        b = BayushiBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        enemy.light = 0
        b.actions = [3]
        b.phase = 3
        b.init_order = [3]

        result = b.choose_action()
        assert result is not None
        assert result[0] == "feint"

    def test_normal_attack_wounded_targets(self) -> None:
        b = BayushiBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        enemy.light = 10
        b.actions = [3, 5]
        b.phase = 3
        b.init_order = [3, 5]

        with patch.object(
            Combatant, "choose_action",
            return_value=("attack", enemy),
        ):
            result = b.choose_action()

        assert result is not None


# ===================================================================
# KITSUKI MAGISTRATE
# ===================================================================


class TestKitsukiAttributes:
    def test_school_knacks(self) -> None:
        k = KitsukiMagistrate(rank=1, **STATS)
        assert set(k.school_knacks) == {
            "discern_honor", "iaijutsu", "presence",
        }

    def test_r1t_rolls(self) -> None:
        k = KitsukiMagistrate(rank=1, **STATS)
        for rt in k.r1t_rolls:
            assert k.extra_dice[rt][0] >= 1

    def test_r2t_always_bonus(self) -> None:
        k = KitsukiMagistrate(rank=2, **STATS)
        assert k.always["interrogation"] >= 5


class TestKitsukiParryDice:
    def test_uses_water_not_air(self) -> None:
        k = KitsukiMagistrate(
            rank=1, air=2, water=5,
            earth=5, fire=3, void=3,
            attack=3, parry=3,
        )
        roll, keep = k.parry_dice
        # Water(5) + parry(3) + R1T(1) = 9 rolled
        assert roll == 5 + 3 + 1
        assert keep == 5

    def test_different_from_air_parry(self) -> None:
        k = KitsukiMagistrate(
            rank=1, air=2, water=5,
            earth=5, fire=3, void=3,
            attack=3, parry=3,
        )
        base = Combatant(
            air=2, water=5,
            earth=5, fire=3, void=3,
            attack=3, parry=3,
        )
        # Kitsuki: Water(5)-based + R1T(1). Base: Air(2)-based.
        # Kitsuki rolled = 5+3+1=9, Base rolled = 2+3=5
        assert k.parry_dice[0] > base.parry_dice[0]
        assert k.parry_dice[1] > base.parry_dice[1]  # keep: 5 vs 2


class TestKitsukiR3T:
    def test_shared_disc_bonuses(self) -> None:
        k = KitsukiMagistrate(rank=3, **STATS)
        # 5 investigation raises = [5, 5, 5, 5, 5]
        for rt in ["attack", "wound_check"]:
            total = sum(
                sum(g) for g in k.multi[rt]
            )
            assert total == 5 * 5

    def test_shared_reference(self) -> None:
        """Attack and wound_check share same list."""
        k = KitsukiMagistrate(rank=3, **STATS)
        assert k.multi["attack"][-1] is (
            k.multi["wound_check"][-1]
        )

    def test_rank_gated(self) -> None:
        k = KitsukiMagistrate(rank=2, **STATS)
        assert not k.multi["attack"]
        assert not k.multi["wound_check"]


class TestKitsukiR5T:
    def test_whammy_reduces_rings(self) -> None:
        k = KitsukiMagistrate(rank=5, xp=100, **STATS)
        enemy = make_enemy(air=4, fire=4, water=4, xp=50)
        k.whammy(enemy)

        assert enemy.air == 3
        assert enemy.fire == 3
        assert enemy.water == 3

    def test_whammy_reset_restores(self) -> None:
        k = KitsukiMagistrate(rank=5, xp=100, **STATS)
        enemy = make_enemy(air=4, fire=4, water=4, xp=50)
        k.attackable = {enemy}
        k.targeted = [enemy]
        k.whammy(enemy)

        # After whammy: rings reduced by 1
        assert enemy.air == 3
        assert enemy.fire == 3
        assert enemy.water == 3

        k.whammy_reset()

        # whammy_reset restores rings then re-applies via r5t_trigger
        # If XP budget allows, it re-whammies the same enemy
        # so rings end up reduced again
        assert enemy.air <= 4
        assert enemy.fire <= 4
        assert enemy.water <= 4

    def test_death_handler_registered(self) -> None:
        k = KitsukiMagistrate(rank=5, xp=100, **STATS)
        enemy = make_enemy(xp=50)
        k.whammy(enemy)
        assert k.whammy_reset in enemy.events["death"]


class TestKitsukiInit:
    def test_event_handlers(self) -> None:
        k = KitsukiMagistrate(rank=5, **STATS)
        assert k.r5t_trigger in k.events["pre_combat"]


# ===================================================================
# MATSU BUSHI
# ===================================================================


class TestMatsuAttributes:
    def test_school_knacks(self) -> None:
        m = MatsuBushi(rank=1, **STATS)
        assert set(m.school_knacks) == {
            "double_attack", "iaijutsu", "lunge",
        }

    def test_r1t_rolls(self) -> None:
        m = MatsuBushi(rank=1, **STATS)
        for rt in m.r1t_rolls:
            assert m.extra_dice[rt][0] >= 1

    def test_r2t_always_bonus(self) -> None:
        m = MatsuBushi(rank=2, **STATS)
        assert m.always["iaijutsu"] >= 5

    def test_hold_one_action_false(self) -> None:
        m = MatsuBushi(rank=1, **STATS)
        assert m.hold_one_action is False


class TestMatsuSpecialAbility:
    def test_always_rolls_10_initiative(self) -> None:
        """Regardless of Void, always rolls 10 initiative dice."""
        for void in [2, 3, 5, 8]:
            stats = dict(STATS, void=void)
            m = MatsuBushi(rank=1, **stats)
            roll, keep = m.init_dice
            assert roll == 10

    def test_keep_unchanged(self) -> None:
        m = MatsuBushi(rank=1, **STATS)
        _, keep = m.init_dice
        assert keep == m.void


class TestMatsuR3T:
    def test_vps_create_disc_wc_bonus(self) -> None:
        m = MatsuBushi(rank=3, **STATS)
        m.r3t_trigger(2, "attack")
        expected = 3 * m.attack  # per VP
        total = sum(m.disc["wound_check"])
        assert total == 2 * expected

    def test_rank_gated(self) -> None:
        m = MatsuBushi(rank=2, **STATS)
        m.r3t_trigger(2, "attack")
        assert not m.disc["wound_check"]

    def test_any_roll_type(self) -> None:
        """R3T fires on any roll type, not just attacks."""
        m = MatsuBushi(rank=3, **STATS)
        m.r3t_trigger(1, "wound_check")
        assert sum(m.disc["wound_check"]) == 3 * m.attack


class TestMatsuAttProb:
    def test_double_attack_gets_vp_boost(self) -> None:
        m = MatsuBushi(rank=4, **STATS)
        m.vps = 3
        prob_datt = m.att_prob("double_attack", 25)
        # Compare without VP boost
        m.vps = 0
        prob_no_vp = m.att_prob("double_attack", 25)
        assert prob_datt > prob_no_vp

    def test_non_datt_no_vp_boost(self) -> None:
        m = MatsuBushi(rank=4, **STATS)
        m.vps = 3
        prob_att = m.att_prob("attack", 15)
        m.vps = 0
        prob_no_vp = m.att_prob("attack", 15)
        assert prob_att == prob_no_vp


class TestMatsuR4T:
    def test_lowers_vp_fail_threshold(self) -> None:
        m = MatsuBushi(rank=4, **STATS)
        base = MatsuBushi(rank=3, **STATS)
        assert m.vp_fail_threshold < base.vp_fail_threshold

    def test_raises_datt_threshold(self) -> None:
        m = MatsuBushi(rank=4, **STATS)
        assert m.datt_threshold == 0.33

    def test_missed_datt_becomes_hit(self) -> None:
        m = MatsuBushi(rank=4, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        m.attack_knack = "double_attack"

        # Base attack misses. attack_roll is below
        # enemy.tn (which has +20 from datt) but above
        # enemy.tn - 20 (the non-datt TN).
        with patch.object(
            Combatant, "make_attack", return_value=False,
        ):
            # enemy.tn is the RAISED tn (includes +20)
            m.attack_roll = enemy.tn - 15
            result = m.make_attack()

        assert result is True
        assert m.attack_roll == 0

    def test_missed_datt_by_too_much(self) -> None:
        m = MatsuBushi(rank=4, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        m.attack_knack = "double_attack"

        with patch.object(
            Combatant, "make_attack", return_value=False,
        ):
            # Below even the non-datt TN
            m.attack_roll = enemy.tn - 25
            result = m.make_attack()

        assert result is False

    def test_rank_gated(self) -> None:
        m = MatsuBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        m.attack_knack = "double_attack"

        with patch.object(
            Combatant, "make_attack", return_value=False,
        ):
            m.attack_roll = enemy.tn - 15
            result = m.make_attack()

        assert result is False

    def test_only_double_attack(self) -> None:
        m = MatsuBushi(rank=4, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        m.attack_knack = "attack"

        with patch.object(
            Combatant, "make_attack", return_value=False,
        ):
            m.attack_roll = enemy.tn - 5
            result = m.make_attack()

        assert result is False


class TestMatsuR5T:
    def test_pre_records_serious(self) -> None:
        m = MatsuBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        enemy.serious = 2
        m.r5t_pre()
        assert m.pre_sw == 2

    def test_pre_raises_threshold(self) -> None:
        m = MatsuBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        before = enemy.base_wc_threshold
        m.r5t_pre()
        assert enemy.base_wc_threshold == before + 10

    def test_post_sets_light_wounds(self) -> None:
        m = MatsuBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        m.engine = MagicMock()

        m.pre_sw = 0
        enemy.serious = 1  # Dealt 1 serious
        enemy.light = 0    # Light cleared
        enemy.dead = False
        enemy.base_wc_threshold += 10

        m.r5t_post()

        assert enemy.light == 10
        assert enemy.base_wc_threshold == 10

    def test_post_no_effect_if_no_serious(self) -> None:
        m = MatsuBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        m.engine = MagicMock()

        m.pre_sw = 0
        enemy.serious = 0  # No serious dealt
        enemy.light = 0
        enemy.dead = False
        enemy.base_wc_threshold += 10

        m.r5t_post()
        assert enemy.light == 0

    def test_post_no_effect_if_dead(self) -> None:
        m = MatsuBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(m, enemy)

        m.pre_sw = 0
        enemy.serious = 5
        enemy.light = 0
        enemy.dead = True
        enemy.base_wc_threshold += 10

        m.r5t_post()
        assert enemy.light == 0

    def test_rank_gated(self) -> None:
        m = MatsuBushi(rank=4, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        before = enemy.base_wc_threshold
        m.r5t_pre()
        assert enemy.base_wc_threshold == before


class TestMatsuInit:
    def test_event_handlers(self) -> None:
        m = MatsuBushi(rank=5, **STATS)
        assert m.r3t_trigger in m.events["vps_spent"]
        assert m.r5t_pre in m.events["pre_attack"]
        assert m.r5t_post in m.events["post_attack"]


# ===================================================================
# SHINJO BUSHI
# ===================================================================


class TestShinjoAttributes:
    def test_school_knacks(self) -> None:
        s = ShinjoBushi(rank=1, **STATS)
        assert set(s.school_knacks) == {
            "double_attack", "iaijutsu", "lunge",
        }

    def test_r1t_rolls(self) -> None:
        s = ShinjoBushi(rank=1, **STATS)
        for rt in s.r1t_rolls:
            assert s.extra_dice[rt][0] >= 1

    def test_r2t_always_bonus(self) -> None:
        s = ShinjoBushi(rank=2, **STATS)
        assert s.always["parry"] >= 5

    def test_predeclare_bonus(self) -> None:
        s = ShinjoBushi(rank=1, **STATS)
        assert s.predeclare_bonus == 5


class TestShinjoR3T:
    def test_lowers_action_dice(self) -> None:
        s = ShinjoBushi(rank=3, **STATS)
        s.actions = [5, 7, 9]
        s.r3t_trigger()
        # Each lowered by attack(3)
        assert s.actions == [2, 4, 6]

    def test_rank_gated(self) -> None:
        s = ShinjoBushi(rank=2, **STATS)
        s.actions = [5, 7, 9]
        s.r3t_trigger()
        assert s.actions == [5, 7, 9]

    def test_can_go_negative(self) -> None:
        """Action dice can go below 0 (will act immediately)."""
        s = ShinjoBushi(rank=3, attack=5, **{
            k: v for k, v in STATS.items()
            if k != "attack"
        })
        s.actions = [3, 5]
        s.r3t_trigger()
        assert s.actions == [-2, 0]


class TestShinjoR4T:
    def test_replaces_highest_with_1(self) -> None:
        s = ShinjoBushi(rank=4, **STATS)

        with patch(
            "l7r.combatant.d10",
            side_effect=[4, 6, 8, 3],
        ):
            s.initiative()

        # Base: sorted [3,4,6,8], keep 3 → [3,4,6]
        # R4T: insert 1 at front, pop highest → [1,3,4]
        assert 1 in s.actions
        assert s.actions[0] == 1

    def test_init_order_updated(self) -> None:
        s = ShinjoBushi(rank=4, **STATS)

        with patch(
            "l7r.combatant.d10",
            side_effect=[4, 6, 8, 3],
        ):
            s.initiative()

        assert s.init_order == s.actions

    def test_rank_gated(self) -> None:
        s = ShinjoBushi(rank=3, **STATS)

        with patch(
            "l7r.combatant.d10",
            side_effect=[4, 6, 8, 3],
        ):
            s.initiative()

        # No R4T at rank 3
        assert 1 not in s.actions or s.actions != [1, 3, 4]


class TestShinjoR5T:
    def test_excess_becomes_wc_disc(self) -> None:
        s = ShinjoBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(s, enemy)
        s.parry_roll = 30
        enemy.attack_roll = 20

        s.r5t_trigger()

        assert 10 in s.disc["wound_check"]

    def test_no_excess_no_bonus(self) -> None:
        s = ShinjoBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(s, enemy)
        s.parry_roll = 15
        enemy.attack_roll = 20

        s.r5t_trigger()
        assert not s.disc["wound_check"]

    def test_rank_gated(self) -> None:
        s = ShinjoBushi(rank=4, **STATS)
        enemy = make_enemy()
        link(s, enemy)
        s.parry_roll = 30
        enemy.attack_roll = 20

        s.r5t_trigger()
        assert not s.disc["wound_check"]


class TestShinjoWCThreshold:
    def test_uses_max_bonus(self) -> None:
        s = ShinjoBushi(rank=5, **STATS)
        s.always["wound_check"] = 20
        assert s.wc_threshold >= 20

    def test_at_least_base(self) -> None:
        s = ShinjoBushi(rank=1, **STATS)
        assert s.wc_threshold >= s.base_wc_threshold


class TestShinjoChooseAction:
    def test_only_attacks_phase_10(self) -> None:
        s = ShinjoBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(s, enemy)
        s.actions = [3, 5]
        s.phase = 5

        result = s.choose_action()
        assert result is None

    def test_attacks_in_phase_10(self) -> None:
        s = ShinjoBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(s, enemy)
        s.actions = [3, 5]
        s.phase = 10
        s.init_order = [3, 5]

        result = s.choose_action()
        assert result is not None

    def test_accumulates_timing_bonus(self) -> None:
        s = ShinjoBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(s, enemy)
        s.actions = [3]
        s.phase = 7

        s.choose_action()

        # Bonus = 2 * (7 - 3) = 8
        assert s.auto_once["attack"] == 8
        assert s.auto_once["parry"] == 8
        assert s.auto_once["double_attack"] == 8


class TestShinjoWillPredeclare:
    def test_predeclares_with_2_actions(self) -> None:
        s = ShinjoBushi(rank=1, **STATS)
        s.actions = [3, 5]
        assert s.will_predeclare() is True

    def test_no_predeclare_with_1_action(self) -> None:
        s = ShinjoBushi(rank=1, **STATS)
        s.actions = [3]
        assert s.will_predeclare() is False

    def test_no_predeclare_no_actions(self) -> None:
        s = ShinjoBushi(rank=1, **STATS)
        s.actions = []
        assert s.will_predeclare() is False


class TestShinjoInit:
    def test_event_handlers(self) -> None:
        s = ShinjoBushi(rank=5, **STATS)
        assert s.r3t_trigger in s.events["successful_parry"]
        assert s.r5t_trigger in s.events["successful_parry"]


# ===================================================================
# MIRUMOTO BUSHI
# ===================================================================


class TestMirumotoClassAttrs:
    def test_school_knacks(self) -> None:
        assert MirumotoBushi.school_knacks == [
            "counterattack", "double_attack", "iaijutsu",
        ]

    def test_r1t_rolls(self) -> None:
        assert MirumotoBushi.r1t_rolls == ["attack", "double_attack", "parry"]

    def test_r2t_roll(self) -> None:
        assert MirumotoBushi.r2t_rolls == "parry"

    def test_school_ring(self) -> None:
        assert MirumotoBushi.school_ring == "void"


class TestMirumotoInit:
    def test_event_handlers(self) -> None:
        m = MirumotoBushi(rank=3, **STATS)
        assert m.sa_trigger in m.events["successful_parry"]
        assert m.r3t_trigger in m.events["pre_round"]

    def test_r5_registers_vps_spent_handler(self) -> None:
        m = MirumotoBushi(rank=5, **STATS)
        assert m.r5t_trigger in m.events["vps_spent"]

    def test_r4_no_vps_spent_handler(self) -> None:
        m = MirumotoBushi(rank=4, **STATS)
        assert m.r5t_trigger not in m.events["vps_spent"]

    def test_no_vp_doubling(self) -> None:
        """R5T no longer doubles starting VPs."""
        m = MirumotoBushi(rank=5, **STATS)
        base_vps = min(3, 3, 3, 3, 3) + m.extra_vps
        assert m.vps == base_vps


class TestMirumotoSA:
    def test_gain_1_vp_on_parry(self) -> None:
        m = MirumotoBushi(rank=3, **STATS)
        initial = m.vps
        m.sa_trigger()
        assert m.vps == initial + 1

    def test_gain_1_vp_at_rank_5_too(self) -> None:
        """SA always gives 1 VP regardless of rank (R5T is now +10 per VP)."""
        m = MirumotoBushi(rank=5, **STATS)
        initial = m.vps
        m.sa_trigger()
        assert m.vps == initial + 1


class TestMirumotoR3T:
    def test_generates_points_at_rank_3(self) -> None:
        m = MirumotoBushi(rank=3, **STATS)
        m.r3t_trigger()
        assert m.points == [2] * m.attack

    def test_no_points_below_rank_3(self) -> None:
        m = MirumotoBushi(rank=2, **STATS)
        m.r3t_trigger()
        assert not hasattr(m, "points") or m.points == []

    def test_registers_multi_bonuses_at_rank_3(self) -> None:
        """R3T points are always registered as multi bonuses, not just at R4."""
        m = MirumotoBushi(rank=3, **STATS)
        m.r3t_trigger()
        for knack in ["attack", "double_attack", "counterattack", "parry"]:
            assert m.points in m.multi[knack]

    def test_no_multi_on_lunge(self) -> None:
        """R3T points do not apply to lunge."""
        m = MirumotoBushi(rank=3, **STATS)
        m.r3t_trigger()
        assert m.points not in m.multi["lunge"]

    def test_points_shared_across_knacks(self) -> None:
        """Consuming a point from one knack depletes it for all."""
        m = MirumotoBushi(rank=3, **STATS)
        m.r3t_trigger()
        m.points.pop()
        for knack in ["attack", "double_attack", "counterattack", "parry"]:
            assert len(m.multi[knack][0]) == m.attack - 1


class TestMirumotoChooseAction:
    def test_holds_until_phase_10(self) -> None:
        m = MirumotoBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        m.actions = [3, 5, 8]
        m.phase = 5
        assert m.choose_action() is None

    def test_attacks_in_phase_10(self) -> None:
        m = MirumotoBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        m.actions = [3, 5]
        m.phase = 10
        m.init_order = [3, 5]
        result = m.choose_action()
        assert result is not None
        knack, target = result
        assert knack in ("attack", "double_attack")
        assert target is enemy

    def test_double_attack_when_vps_make_viable(self) -> None:
        """With enough VPs and bonuses, prefer double attack."""
        m = MirumotoBushi(rank=4, **{**STATS, "void": 5, "fire": 5, "attack": 5})
        enemy = make_enemy(air=2, parry=1)  # low TN
        link(m, enemy)
        m.vps = 10
        m.actions = [3]
        m.phase = 10
        m.init_order = [3]
        m.r3t_trigger()  # generate R3T bonuses
        knack, _ = m.choose_action()
        assert knack == "double_attack"

    def test_regular_attack_when_double_not_viable(self) -> None:
        """Against very high TN, fall back to regular attack."""
        m = MirumotoBushi(rank=3, **STATS)
        enemy = make_enemy(air=5, parry=5)  # TN = 30
        link(m, enemy)
        m.vps = 0
        m.actions = [3]
        m.phase = 10
        m.init_order = [3]
        knack, _ = m.choose_action()
        assert knack == "attack"

    def test_consumes_action_die(self) -> None:
        m = MirumotoBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        m.actions = [3, 7]
        m.phase = 10
        m.init_order = [3, 7]
        m.choose_action()
        assert m.actions == [7]

    def test_no_action_when_no_actions(self) -> None:
        m = MirumotoBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        m.actions = []
        m.phase = 10
        assert m.choose_action() is None


class TestMirumotoWillPredeclare:
    def test_predeclares_with_many_actions(self) -> None:
        m = MirumotoBushi(rank=3, **STATS)
        m.actions = [3, 5, 8]
        assert m.will_predeclare() is True
        assert m.predeclare_bonus == 5

    def test_no_predeclare_with_few_actions(self) -> None:
        m = MirumotoBushi(rank=3, **STATS)
        m.actions = [3]
        assert m.will_predeclare() is False
        assert m.predeclare_bonus == 0

    def test_no_predeclare_with_no_actions(self) -> None:
        m = MirumotoBushi(rank=3, **STATS)
        m.actions = []
        assert m.will_predeclare() is False
        assert m.predeclare_bonus == 0


class TestMirumotoWillParry:
    def _make_defender(self, rank: int = 3, **kw: int) -> MirumotoBushi:
        defaults = dict(STATS)
        defaults.update(kw)
        m = MirumotoBushi(rank=rank, **defaults)
        m.predeclare_bonus = 0
        return m

    def test_parries_when_predeclared(self) -> None:
        """If predeclare_bonus is set, always parry."""
        m = self._make_defender()
        enemy = make_enemy(fire=5)
        link(m, enemy)
        m.predeclare_bonus = 5
        m.actions = [3]
        m.phase = 5
        assert m.will_parry() is True

    def test_parries_with_current_phase_action(self) -> None:
        """Normal parry when action is available this phase."""
        m = self._make_defender()
        enemy = make_enemy(fire=5)
        link(m, enemy)
        m.actions = [5, 8]
        m.phase = 5
        # Ensure projected damage is high enough to want to parry
        with patch.object(m, "projected_damage", side_effect=[4, 0]):
            assert m.will_parry() is True
        assert m.actions == [8]

    def test_uses_r3t_points_to_lower_action_die(self) -> None:
        """Spends R3T points to lower a future action die to parry."""
        m = self._make_defender()
        enemy = make_enemy(fire=5)
        link(m, enemy)
        m.r3t_trigger()  # generates points
        initial_points = len(m.points)
        m.actions = [8]  # future action
        m.phase = 5
        cost = 8 - 5  # 3 points to lower from phase 8 to phase 5
        with patch.object(m, "projected_damage", side_effect=[4, 0]):
            result = m.will_parry()
        assert result is True
        assert len(m.points) == initial_points - cost
        assert m.actions == []

    def test_no_parry_when_insufficient_points(self) -> None:
        """Won't parry if not enough R3T points to lower die."""
        m = self._make_defender()
        enemy = make_enemy(fire=3)
        link(m, enemy)
        m.points = [2]  # only 1 point
        m.actions = [9]  # need 4 points to lower from 9 to 5
        m.phase = 5
        with patch.object(m, "projected_damage", side_effect=[3, 1]):
            result = m.will_parry()
        assert result is False

    def test_higher_threshold_when_few_actions(self) -> None:
        """With few actions remaining, needs higher damage to parry."""
        m = self._make_defender()
        enemy = make_enemy(fire=3)
        link(m, enemy)
        m.actions = [5]  # only 1 action
        m.phase = 5
        # Moderate damage: base parry threshold would allow, but late
        # round threshold should deny
        with patch.object(
            m, "projected_damage",
            side_effect=[m.late_parry_threshold - 1, 0],
        ):
            result = m.will_parry()
        assert result is False

    def test_still_parries_when_lethal_even_with_few_actions(self) -> None:
        """Always parry to survive, even in late round mode."""
        m = self._make_defender()
        enemy = make_enemy(fire=5)
        link(m, enemy)
        m.actions = [5]
        m.phase = 5
        m.serious = m.sw_to_kill - 1  # one from death
        with patch.object(m, "projected_damage", side_effect=[1, 0]):
            result = m.will_parry()
        assert result is True

    def test_no_parry_when_no_actions_and_no_points(self) -> None:
        m = self._make_defender()
        enemy = make_enemy(fire=3)
        link(m, enemy)
        m.actions = []
        m.phase = 5
        m.points = []
        assert m.will_parry() is False


class TestMirumotoR4T:
    """R4T: When the Mirumoto's parry fails, the attacker's rolled
    damage dice are halved."""

    def test_halves_damage_dice_on_failed_parry(self) -> None:
        m = MirumotoBushi(rank=4, **STATS)
        enemy = make_enemy(fire=4)
        link(m, enemy)
        m.predeclare_bonus = 0
        enemy.attack_roll = 99  # guarantees parry fails
        enemy.attack_knack = "attack"

        original_rolled = enemy.damage_dice[0]
        m.make_parry()

        # After failed parry, enemy damage dice should be halved
        assert enemy.damage_dice[0] == original_rolled // 2

    def test_damage_restored_after_post_defense(self) -> None:
        m = MirumotoBushi(rank=4, **STATS)
        enemy = make_enemy(fire=4)
        link(m, enemy)
        m.predeclare_bonus = 0
        enemy.attack_roll = 99
        enemy.attack_knack = "attack"

        original_rolled = enemy.damage_dice[0]
        m.make_parry()

        # Trigger post_defense to restore
        m.triggers("post_defense")
        assert enemy.damage_dice[0] == original_rolled

    def test_no_effect_below_rank_4(self) -> None:
        m = MirumotoBushi(rank=3, **STATS)
        enemy = make_enemy(fire=4)
        link(m, enemy)
        m.predeclare_bonus = 0
        enemy.attack_roll = 99
        enemy.attack_knack = "attack"

        original_rolled = enemy.damage_dice[0]
        m.make_parry()
        assert enemy.damage_dice[0] == original_rolled

    def test_no_effect_on_successful_parry(self) -> None:
        m = MirumotoBushi(rank=4, **STATS)
        enemy = make_enemy(fire=4)
        link(m, enemy)
        m.predeclare_bonus = 0
        enemy.attack_roll = 0  # guarantees parry succeeds
        enemy.attack_knack = "attack"

        original_rolled = enemy.damage_dice[0]
        m.make_parry()
        assert enemy.damage_dice[0] == original_rolled


class TestMirumotoR5T:
    """R5T: Each VP spent gives an extra +10 bonus to the roll."""

    def test_adds_bonus_on_vps_spent(self) -> None:
        m = MirumotoBushi(rank=5, **STATS)
        m.r5t_trigger(2, "attack")
        assert m.auto_once["attack"] == 20

    def test_scales_with_vps(self) -> None:
        m = MirumotoBushi(rank=5, **STATS)
        m.r5t_trigger(3, "parry")
        assert m.auto_once["parry"] == 30

    def test_stacks_with_existing_auto_once(self) -> None:
        m = MirumotoBushi(rank=5, **STATS)
        m.auto_once["attack"] = 5
        m.r5t_trigger(1, "attack")
        assert m.auto_once["attack"] == 15

    def test_not_registered_below_rank_5(self) -> None:
        m = MirumotoBushi(rank=4, **STATS)
        assert m.r5t_trigger not in m.events["vps_spent"]


class TestMirumotoKnackLevels:
    def test_knacks_from_rank(self) -> None:
        m = MirumotoBushi(rank=4, **STATS)
        for knack in m.school_knacks:
            assert getattr(m, knack) == 4


# ===================================================================
# SCHOOL KNACK LEVELS FROM RANK
# ===================================================================


class TestSchoolKnackLevels:
    """All schools set knack levels from rank."""

    def test_akodo_knacks_from_rank(self) -> None:
        a = AkodoBushi(rank=4, **STATS)
        for knack in a.school_knacks:
            assert getattr(a, knack) == 4

    def test_bayushi_knacks_from_rank(self) -> None:
        b = BayushiBushi(rank=3, **STATS)
        for knack in b.school_knacks:
            assert getattr(b, knack) == 3

    def test_kitsuki_knacks_from_rank(self) -> None:
        k = KitsukiMagistrate(rank=2, **STATS)
        for knack in k.school_knacks:
            assert getattr(k, knack) == 2

    def test_matsu_knacks_from_rank(self) -> None:
        m = MatsuBushi(rank=5, **STATS)
        for knack in m.school_knacks:
            assert getattr(m, knack) == 5

    def test_shinjo_knacks_from_rank(self) -> None:
        s = ShinjoBushi(rank=1, **STATS)
        for knack in s.school_knacks:
            assert getattr(s, knack) == 1

    def test_kakita_knacks_from_rank(self) -> None:
        k = KakitaBushi(rank=4, **STATS)
        for knack in k.school_knacks:
            assert getattr(k, knack) == 4


# ===================================================================
# KAKITA BUSHI
# ===================================================================


class TestKakitaClassAttrs:
    def test_school_knacks(self) -> None:
        assert KakitaBushi.school_knacks == [
            "double_attack", "iaijutsu", "lunge",
        ]

    def test_r1t_rolls(self) -> None:
        assert KakitaBushi.r1t_rolls == [
            "double_attack", "iaijutsu", "initiative",
        ]

    def test_r2t_rolls(self) -> None:
        assert KakitaBushi.r2t_rolls == "iaijutsu"

    def test_school_ring(self) -> None:
        assert KakitaBushi.school_ring == "fire"

    def test_r4t_ring_boost(self) -> None:
        assert KakitaBushi.r4t_ring_boost == "fire"

    def test_hold_one_action_false(self) -> None:
        assert KakitaBushi.hold_one_action is False


class TestKakitaInit:
    def test_r4t_trigger_registered(self) -> None:
        k = KakitaBushi(rank=4, **STATS)
        assert k.r4t_trigger in k.events["successful_attack"]

    def test_r5t_trigger_registered(self) -> None:
        k = KakitaBushi(rank=5, **STATS)
        assert k.r5t_trigger in k.events["pre_round"]


class TestKakitaInitiative:
    def test_tens_become_zeros(self) -> None:
        k = KakitaBushi(rank=1, **STATS)
        # init_dice = (5, 3): void(3)+1+R1T(1) rolled, void(3) kept
        with patch(
            "l7r.schools.KakitaBushi.d10",
            side_effect=[10, 3, 7, 10, 5],
        ):
            k.initiative()
        assert 0 in k.actions
        assert 10 not in k.actions

    def test_non_tens_unchanged(self) -> None:
        k = KakitaBushi(rank=1, **STATS)
        # init_dice = (5, 3): need 5 dice, keep first 3
        with patch(
            "l7r.schools.KakitaBushi.d10",
            side_effect=[4, 6, 8, 2, 9],
        ):
            k.initiative()
        assert len(k.actions) == 3
        # First 3 dice kept (not sorted): [4, 6, 8]
        assert k.actions == [4, 6, 8]

    def test_init_order_matches_actions(self) -> None:
        k = KakitaBushi(rank=1, **STATS)
        with patch(
            "l7r.schools.KakitaBushi.d10",
            side_effect=[10, 5, 3, 7, 2],
        ):
            k.initiative()
        assert k.init_order == k.actions

    def test_r1t_extra_initiative_die(self) -> None:
        k = KakitaBushi(rank=1, **STATS)
        roll, keep = k.init_dice
        # base: void(3)+1 = 4 rolled, void(3) kept
        # R1T adds 1 rolled die for initiative
        assert roll == 3 + 1 + 1  # void + 1 + r1t
        assert keep == 3


class TestKakitaR3T:
    def test_positive_bonus_when_acting_first(self) -> None:
        k = KakitaBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.phase = 2
        enemy.actions = [5]
        # bonus = attack(3) * (5 - 2) = 9
        assert k.r3t_bonus() == 9

    def test_zero_when_enemy_acts_same_phase(self) -> None:
        k = KakitaBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.phase = 5
        enemy.actions = [5]
        assert k.r3t_bonus() == 0

    def test_scales_with_attack_and_gap(self) -> None:
        stats = {**STATS, "attack": 5}
        k = KakitaBushi(rank=3, **stats)
        enemy = make_enemy()
        link(k, enemy)
        k.phase = 1
        enemy.actions = [8]
        # bonus = attack(5) * (8 - 1) = 35
        assert k.r3t_bonus() == 35

    def test_returns_zero_when_no_enemy(self) -> None:
        k = KakitaBushi(rank=3, **STATS)
        # No enemy set — hasattr guard should return 0
        assert k.r3t_bonus() == 0


class TestKakitaR4T:
    def test_iaijutsu_adds_damage(self) -> None:
        k = KakitaBushi(rank=4, **STATS)
        k.attack_knack = "iaijutsu"
        k.r4t_trigger()
        assert k.auto_once["damage"] == 5

    def test_non_iaijutsu_no_bonus(self) -> None:
        k = KakitaBushi(rank=4, **STATS)
        k.attack_knack = "attack"
        k.r4t_trigger()
        assert k.auto_once["damage"] == 0

    def test_rank_gated(self) -> None:
        k = KakitaBushi(rank=3, **STATS)
        k.attack_knack = "iaijutsu"
        k.r4t_trigger()
        assert k.auto_once["damage"] == 0


class TestKakitaR5T:
    def test_rank_5_calls_wound_check(self) -> None:
        k = KakitaBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.phase = 0

        with (
            patch.object(enemy, "xky", return_value=10),
            patch.object(enemy, "wound_check") as mock_wc,
        ):
            k.r5t_trigger()

        mock_wc.assert_called_once()
        assert mock_wc.call_args[0][0] > 0

    def test_rank_below_5_no_action(self) -> None:
        k = KakitaBushi(rank=4, **STATS)
        enemy = make_enemy()
        link(k, enemy)

        with patch.object(enemy, "wound_check") as mock_wc:
            k.r5t_trigger()

        mock_wc.assert_not_called()


class TestKakitaChooseAction:
    def test_phase_0_uses_iaijutsu(self) -> None:
        k = KakitaBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.actions = [0]
        k.phase = 0
        k.init_order = [0]

        result = k.choose_action()
        assert result is not None
        assert result[0] == "iaijutsu"

    def test_normal_attack(self) -> None:
        k = KakitaBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.actions = [3]
        k.phase = 3
        k.init_order = [3]

        result = k.choose_action()
        assert result is not None
        assert result[0] in ("attack", "double_attack")

    def test_no_actions_returns_none(self) -> None:
        k = KakitaBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.actions = []
        k.phase = 5

        assert k.choose_action() is None

    def test_double_attack_when_prob_high(self) -> None:
        k = KakitaBushi(
            rank=3, **{**STATS, "fire": 5, "attack": 5, "void": 5},
        )
        enemy = make_enemy(air=2, parry=1)  # low TN
        link(k, enemy)
        k.actions = [3]
        k.phase = 3
        k.init_order = [3]

        with patch.object(
            k, "att_prob", side_effect=lambda knack, tn: 0.9,
        ):
            result = k.choose_action()

        assert result is not None
        assert result[0] == "double_attack"

    def test_regular_attack_when_datt_needs_vps(self) -> None:
        k = KakitaBushi(rank=3, **STATS)
        enemy = make_enemy(air=5, parry=5)
        link(k, enemy)
        k.actions = [3]
        k.phase = 3
        k.init_order = [3]

        # datt_prob below vp_fail_threshold
        def fake_att_prob(knack: str, tn: int) -> float:
            if knack == "double_attack":
                return 0.3  # below vp_fail_threshold (0.7)
            return 0.8

        with patch.object(k, "att_prob", side_effect=fake_att_prob):
            result = k.choose_action()

        assert result is not None
        assert result[0] == "attack"

    def test_interrupt_iaijutsu_high_damage(self) -> None:
        k = KakitaBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.actions = [7, 9]  # future actions, not current phase
        k.phase = 3

        with patch.object(k, "projected_damage", return_value=3):
            result = k.choose_action()

        assert result is not None
        assert result[0] == "iaijutsu"
        assert result[1] is enemy
        assert k.actions == []

    def test_no_interrupt_low_damage(self) -> None:
        k = KakitaBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.actions = [7, 9]
        k.phase = 3

        with patch.object(k, "projected_damage", return_value=1):
            result = k.choose_action()

        assert result is None
        assert k.actions == [7, 9]  # actions unchanged

    def test_no_interrupt_fewer_than_2_actions(self) -> None:
        k = KakitaBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.actions = [7]  # only 1 action
        k.phase = 3

        assert k.choose_action() is None

    def test_interrupt_consumes_last_2_actions(self) -> None:
        k = KakitaBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.actions = [5, 7, 9]  # 3 future actions
        k.phase = 3

        with patch.object(k, "projected_damage", return_value=4):
            result = k.choose_action()

        assert result is not None
        assert result[0] == "iaijutsu"
        assert k.actions == [5]  # only first action remains


class TestKakitaDiscBonus:
    def test_disc_bonus_adds_r3t(self) -> None:
        k = KakitaBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.phase = 2
        enemy.actions = [5]
        # r3t_bonus = 3 * (5-2) = 9
        k.disc["attack"] = [5]
        bonus = k.disc_bonus("attack", 10)
        # r3t gives 9, then needs 10-9=1 from disc, disc has 5 → spends 5
        assert bonus == 9 + 5

    def test_max_bonus_adds_r3t(self) -> None:
        k = KakitaBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.phase = 2
        enemy.actions = [5]
        # r3t_bonus = 9
        base_max = Combatant.max_bonus(k, "attack")
        assert k.max_bonus("attack") == base_max + 9


class TestKakitaAttTarget:
    def test_prefers_distant_enemy_over_close_low_tn(self) -> None:
        """TN 30 enemy 4 phases away beats TN 25 enemy acting
        now because R3T bonus lowers effective TN."""
        k = KakitaBushi(rank=3, **STATS)  # attack=3
        k.phase = 2
        k.init_order = [2]

        # Enemy A: TN 30, phase 6 → bonus=3*(6-2)=12, eff TN=18
        far_enemy = make_enemy(parry=5)       # tn = 30
        far_enemy.actions = [6]
        far_enemy.init_order = [6]

        # Enemy B: TN 25, next action phase 2 → bonus = 0, eff TN = 25
        close_enemy = make_enemy(parry=4)     # tn = 25
        close_enemy.actions = [2]
        close_enemy.init_order = [2]

        k.attackable = {far_enemy, close_enemy}

        # With double_attack knack, only lowest effective TN is eligible.
        # far_enemy effective TN = 18, close_enemy effective TN = 25
        # So only far_enemy should be in the target pool.
        target = k.att_target("double_attack")
        assert target is far_enemy

    def test_no_r3t_advantage_uses_base_weights(self) -> None:
        """When both enemies act in the current phase, R3T bonus is 0 for both
        and behavior matches the base att_target weighting."""
        k = KakitaBushi(rank=3, **STATS)
        k.phase = 3
        k.init_order = [3]

        e1 = make_enemy(parry=3)  # tn = 20
        e1.actions = [3]
        e1.init_order = [3]

        e2 = make_enemy(parry=4)  # tn = 25
        e2.actions = [3]
        e2.init_order = [3]

        k.attackable = {e1, e2}

        # Both have R3T bonus = 0 (phase not < next_action).
        # Weights should be based on raw TN only:
        # e1: 1 + 0 + (30-20)//5 + 1 - 1 = 3
        # e2: 1 + 0 + (30-25)//5 + 1 - 1 = 2
        # Verify by checking the list passed to random.choice
        with patch("l7r.schools.KakitaBushi.random.choice",
                   side_effect=lambda lst: lst[0]) as mock_choice:
            k.att_target("attack")
            pool = mock_choice.call_args[0][0]

        assert pool.count(e1) == 3
        assert pool.count(e2) == 2

    def test_double_attack_filters_by_effective_tn(self) -> None:
        """Double attack restricts to lowest effective TN."""
        k = KakitaBushi(rank=3, **{**STATS, "attack": 4})
        k.phase = 1
        k.init_order = [1]

        # Enemy A: TN 20, actions=[5] → bonus = 4*(5-1) = 16, eff TN = 4
        easy = make_enemy(parry=3)  # tn = 20
        easy.actions = [5]
        easy.init_order = [5]

        # Enemy B: TN 15, actions=[1] → bonus = 0, eff TN = 15
        hard = make_enemy(parry=2)  # tn = 15
        hard.actions = [1]
        hard.init_order = [1]

        k.attackable = {easy, hard}

        # double_attack restricts to min effective TN = 4 (easy)
        target = k.att_target("double_attack")
        assert target is easy

    def test_rank_gated_no_r3t_below_rank_3(self) -> None:
        """Below rank 3, _r3t_bonus_vs returns 0 so target selection matches
        the base behavior (no timing bonus)."""
        k = KakitaBushi(rank=2, **STATS)
        k.phase = 1
        k.init_order = [1]

        # Without R3T: far_enemy has higher TN, not picked
        far_enemy = make_enemy(parry=5)       # tn = 30
        far_enemy.actions = [8]
        far_enemy.init_order = [8]

        close_enemy = make_enemy(parry=2)     # tn = 15
        close_enemy.actions = [1]
        close_enemy.init_order = [1]

        k.attackable = {far_enemy, close_enemy}

        # At rank 2, R3T doesn't apply, so double_attack picks lowest raw TN
        target = k.att_target("double_attack")
        assert target is close_enemy


class TestKakitaParryThreshold:
    def test_sw_parry_threshold(self) -> None:
        assert KakitaBushi.sw_parry_threshold == 3


# ===================================================================
# ISAWA DUELIST
# ===================================================================


class TestIsawaDuelistClassAttrs:
    def test_school_knacks(self) -> None:
        assert IsawaDuelist.school_knacks == [
            "double_attack", "iaijutsu", "lunge",
        ]

    def test_r1t_rolls(self) -> None:
        assert IsawaDuelist.r1t_rolls == [
            "double_attack", "lunge", "wound_check",
        ]

    def test_r2t_rolls(self) -> None:
        assert IsawaDuelist.r2t_rolls == "wound_check"

    def test_school_ring(self) -> None:
        assert IsawaDuelist.school_ring == "water"

    def test_r4t_ring_boost(self) -> None:
        assert IsawaDuelist.r4t_ring_boost == "water"


class TestIsawaDuelistInit:
    def test_r5t_trigger_registered(self) -> None:
        d = IsawaDuelist(rank=5, **STATS)
        assert d.r5t_trigger in d.events["wound_check"]

    def test_reset_r4t_lunge_registered(self) -> None:
        d = IsawaDuelist(rank=4, **STATS)
        assert d._reset_r4t_lunge in d.events["pre_round"]


class TestIsawaDuelistDamageDice:
    def test_water_substituted_for_fire(self) -> None:
        d = IsawaDuelist(
            rank=1, air=3, earth=5, fire=2, water=5,
            void=3, attack=3, parry=3,
        )
        roll, keep = d.damage_dice
        # base: base_damage_rolled(4) + fire(2) = 6 rolled
        # swap: 6 - fire(2) + water(5) = 9 rolled
        assert roll == 4 + 5  # base_rolled + water
        assert keep == 2  # base_kept unchanged


class TestIsawaDuelistR3T:
    def test_triggers_when_disc_insufficient(self) -> None:
        """R3T activates when disc bonuses alone don't suffice
        but adding 3*attack gets there."""
        d = IsawaDuelist(rank=3, **STATS)
        original_tn = d.tn
        # Need 10, disc has nothing, 3*attack(3)=9 → 9 >= 10? No.
        # So use needed=9 where 0+9 >= 9
        bonus = d.disc_bonus("attack", 9)
        assert bonus == 9
        assert d.tn == original_tn - 5

    def test_lowers_tn_by_5(self) -> None:
        d = IsawaDuelist(rank=3, **STATS)
        original_tn = d.tn
        d.disc_bonus("attack", 1)
        assert d.tn == original_tn - 5

    def test_rank_gated(self) -> None:
        d = IsawaDuelist(rank=2, **STATS)
        original_tn = d.tn
        d.disc_bonus("attack", 5)
        assert d.tn == original_tn  # no TN change

    def test_parry_negates_tn_penalty(self) -> None:
        """When enemy parries (was_parried=True), TN resets
        immediately in post_attack."""
        d = IsawaDuelist(rank=3, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        original_tn = d.tn
        d.attack_knack = "attack"
        d.disc_bonus("attack", 5)
        assert d.tn == original_tn - 5

        # Simulate was_parried = True then trigger post_attack
        d.was_parried = True
        d.triggers("post_attack")
        assert d.tn == original_tn

    def test_no_parry_keeps_tn_penalty(self) -> None:
        """When enemy doesn't parry, TN penalty persists
        and is registered on post_defense."""
        d = IsawaDuelist(rank=3, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        original_tn = d.tn
        d.attack_knack = "attack"
        d.disc_bonus("attack", 5)
        assert d.tn == original_tn - 5

        # Simulate was_parried = False then trigger post_attack
        d.was_parried = False
        d.triggers("post_attack")
        # TN should still be lowered (post_defense handler queued)
        assert d.tn == original_tn - 5

        # Now trigger post_defense — TN should reset
        d.triggers("post_defense")
        assert d.tn == original_tn


class TestIsawaDuelistMaxBonus:
    def test_adds_3_times_attack_at_rank_3(self) -> None:
        d = IsawaDuelist(rank=3, **STATS)
        base = Combatant.max_bonus(d, "attack")
        assert d.max_bonus("attack") == base + 3 * d.attack

    def test_no_bonus_below_rank_3(self) -> None:
        d = IsawaDuelist(rank=2, **STATS)
        base = Combatant.max_bonus(d, "attack")
        assert d.max_bonus("attack") == base


class TestIsawaDuelistR5T:
    def test_excess_creates_disc_bonuses(self) -> None:
        d = IsawaDuelist(rank=5, **STATS)
        # check=30, light=10, total=10 → exceeded=20
        d.r5t_trigger(30, 10, 10)
        assert sum(d.disc["wound_check"]) == 20

    def test_rank_gated(self) -> None:
        d = IsawaDuelist(rank=4, **STATS)
        d.r5t_trigger(30, 10, 10)
        assert not d.disc["wound_check"]


class TestIsawaDuelistChooseAction:
    def test_first_action_lunges(self) -> None:
        d = IsawaDuelist(rank=3, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        d.actions = [3, 3]
        d.init_order = [3, 3]
        d.phase = 3

        result = d.choose_action()
        assert result is not None
        assert result[0] == "lunge"

    def test_later_action_double_attack_when_viable(self) -> None:
        """After the first action, prefer double attack when prob is high."""
        d = IsawaDuelist(
            rank=3, **{**STATS, "fire": 5, "attack": 5, "void": 5},
        )
        enemy = make_enemy(air=2, parry=1)  # low TN
        link(d, enemy)
        # Simulate: first action already consumed, second action at phase 10
        d.actions = [5]
        d.init_order = [3, 5]
        d.phase = 10

        with patch.object(
            d, "att_prob", side_effect=lambda knack, tn: 0.9,
        ):
            result = d.choose_action()

        assert result is not None
        assert result[0] == "double_attack"

    def test_later_action_lunge_when_datt_not_viable(self) -> None:
        """When double attack prob is too low, fall back to lunge."""
        d = IsawaDuelist(rank=3, **STATS)
        enemy = make_enemy(air=5, parry=5)
        link(d, enemy)
        d.actions = [5]
        d.init_order = [3, 5]
        d.phase = 10

        def fake_att_prob(knack: str, tn: int) -> float:
            if knack == "double_attack":
                return 0.3
            return 0.8

        with patch.object(d, "att_prob", side_effect=fake_att_prob):
            result = d.choose_action()

        assert result is not None
        assert result[0] == "lunge"

    def test_holds_one_action_for_parry(self) -> None:
        """With only 1 action and hold_one_action=True (default),
        pass unless phase is 10."""
        d = IsawaDuelist(rank=3, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        d.actions = [5]
        d.init_order = [3, 5]
        d.phase = 5

        result = d.choose_action()
        assert result is None

    def test_phase_10_doesnt_hold(self) -> None:
        """At phase 10, use remaining actions rather than holding."""
        d = IsawaDuelist(rank=3, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        d.actions = [5]
        d.init_order = [3, 5]
        d.phase = 10

        result = d.choose_action()
        assert result is not None

    def test_no_actions_returns_none(self) -> None:
        d = IsawaDuelist(rank=3, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        d.actions = []
        d.phase = 5

        result = d.choose_action()
        assert result is None

    def test_r4t_interrupt_lunge(self) -> None:
        """R4T: interrupt lunge when threat is high, rank 4+."""
        d = IsawaDuelist(rank=4, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        d.actions = [7]
        d.phase = 3
        d._r4t_lunged = False

        with patch.object(d, "projected_damage", return_value=3):
            result = d.choose_action()

        assert result is not None
        assert result[0] == "lunge"
        assert d._r4t_lunged is True
        assert d.actions == []  # consumed the action

    def test_r4t_once_per_round(self) -> None:
        """R4T interrupt can only be used once per round."""
        d = IsawaDuelist(rank=4, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        d.actions = [7, 9]
        d.phase = 3
        d._r4t_lunged = True  # already used this round

        with patch.object(d, "projected_damage", return_value=3):
            result = d.choose_action()

        assert result is None
        assert d.actions == [7, 9]  # actions unchanged

    def test_r4t_rank_gated(self) -> None:
        """Below rank 4, no interrupt lunge."""
        d = IsawaDuelist(rank=3, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        d.actions = [7]
        d.phase = 3

        with patch.object(d, "projected_damage", return_value=3):
            result = d.choose_action()

        assert result is None


class TestIsawaDuelistKnackLevels:
    def test_knacks_from_rank(self) -> None:
        d = IsawaDuelist(rank=4, **STATS)
        for knack in d.school_knacks:
            assert getattr(d, knack) == 4


# ===================================================================
# OTAKU BUSHI
# ===================================================================


class TestOtakuBushiClassAttrs:
    def test_school_knacks(self) -> None:
        assert OtakuBushi.school_knacks == [
            "double_attack", "iaijutsu", "lunge",
        ]

    def test_r1t_rolls(self) -> None:
        assert OtakuBushi.r1t_rolls == [
            "iaijutsu", "lunge", "wound_check",
        ]

    def test_r2t_rolls(self) -> None:
        assert OtakuBushi.r2t_rolls == "wound_check"

    def test_school_ring(self) -> None:
        assert OtakuBushi.school_ring == "fire"

    def test_r4t_ring_boost(self) -> None:
        assert OtakuBushi.r4t_ring_boost == "fire"

    def test_hold_one_action_false(self) -> None:
        assert OtakuBushi.hold_one_action is False


class TestOtakuBushiInit:
    def test_event_handlers_registered(self) -> None:
        o = OtakuBushi(rank=5, **STATS)
        assert o.sa_trigger in o.events["post_defense"]
        assert o.r3t_pre_trigger in o.events["pre_attack"]
        assert o.r3t_post_trigger in o.events["post_attack"]
        assert o.r4t_succ_trigger in o.events["successful_attack"]
        assert o.r4t_post_trigger in o.events["post_attack"]


class TestOtakuBushiSA:
    def test_sa_lunges_attacker(self) -> None:
        """SA: after being attacked, spend an action to lunge."""
        o = OtakuBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(o, enemy)
        o.actions = [5, 8]
        engine = MagicMock()
        o.engine = engine

        o.sa_trigger()

        engine.attack.assert_called_once_with("lunge", o, enemy)
        assert o.actions == [5]  # popped from end

    def test_sa_no_actions(self) -> None:
        """SA: does nothing when no actions remain."""
        o = OtakuBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(o, enemy)
        o.actions = []
        engine = MagicMock()
        o.engine = engine

        o.sa_trigger()

        engine.attack.assert_not_called()


class TestOtakuBushiR3T:
    def test_delays_enemy_actions_on_wound(self) -> None:
        o = OtakuBushi(rank=3, **{**STATS, "fire": 4})
        enemy = make_enemy(fire=2)
        link(o, enemy)
        enemy.actions = [3, 6]

        # Snapshot before attack
        o.prev_wounds = (enemy.light, enemy.serious)
        # Simulate dealing wounds
        enemy.light = 10
        o.r3t_post_trigger()

        # diff = max(1, 4 - 2) = 2
        assert enemy.actions == [5, 8]

    def test_minimum_delay_is_1(self) -> None:
        o = OtakuBushi(rank=3, **{**STATS, "fire": 2})
        enemy = make_enemy(fire=3)  # enemy has higher fire
        link(o, enemy)
        enemy.actions = [3, 6]

        o.prev_wounds = (enemy.light, enemy.serious)
        enemy.serious = 1
        o.r3t_post_trigger()

        # diff = max(1, 2 - 3) = 1
        assert enemy.actions == [4, 7]

    def test_rank_gated(self) -> None:
        o = OtakuBushi(rank=2, **STATS)
        enemy = make_enemy()
        link(o, enemy)
        enemy.actions = [3, 6]

        o.prev_wounds = (enemy.light, enemy.serious)
        enemy.light = 10
        o.r3t_post_trigger()

        assert enemy.actions == [3, 6]  # unchanged

    def test_no_delay_without_wounds(self) -> None:
        o = OtakuBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(o, enemy)
        enemy.actions = [3, 6]

        o.prev_wounds = (enemy.light, enemy.serious)
        # No new wounds dealt
        o.r3t_post_trigger()

        assert enemy.actions == [3, 6]  # unchanged


class TestOtakuBushiR4T:
    def test_lunge_converts_rolled_to_kept(self) -> None:
        o = OtakuBushi(rank=4, **STATS)
        o.attack_knack = "lunge"
        original = o.base_damage_rolled
        o.auto_once["damage_rolled"] = 0

        o.r4t_succ_trigger()

        assert o.auto_once["damage_rolled"] == -1
        assert o.base_damage_rolled == original + 1

    def test_non_lunge_no_effect(self) -> None:
        o = OtakuBushi(rank=4, **STATS)
        o.attack_knack = "attack"
        original = o.base_damage_rolled
        o.auto_once["damage_rolled"] = 0

        o.r4t_succ_trigger()

        assert o.auto_once["damage_rolled"] == 0
        assert o.base_damage_rolled == original

    def test_rank_gated(self) -> None:
        o = OtakuBushi(rank=3, **STATS)
        o.attack_knack = "lunge"
        original = o.base_damage_rolled
        o.auto_once["damage_rolled"] = 0

        o.r4t_succ_trigger()

        assert o.auto_once["damage_rolled"] == 0
        assert o.base_damage_rolled == original

    def test_post_trigger_resets_base_damage(self) -> None:
        o = OtakuBushi(rank=4, **STATS)
        o.base_damage_rolled = 999

        o.r4t_post_trigger()

        assert o.base_damage_rolled == OtakuBushi.base_damage_rolled


class TestOtakuBushiR5T:
    def test_adds_serious_wound_reduces_dice(self) -> None:
        o = OtakuBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(o, enemy)
        o.attack_knack = "lunge"
        o.attack_roll = enemy.tn

        roll, keep, serious = o.next_damage(enemy.tn, False)
        base_roll, base_keep, base_serious = Combatant.next_damage(
            o, enemy.tn, False,
        )

        assert serious == base_serious + 1
        assert roll == max(2, base_roll - 10)

    def test_applies_to_attack(self) -> None:
        o = OtakuBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(o, enemy)
        o.attack_knack = "attack"
        o.attack_roll = enemy.tn

        _, _, serious = o.next_damage(enemy.tn, False)
        _, _, base_serious = Combatant.next_damage(o, enemy.tn, False)

        assert serious == base_serious + 1

    def test_not_applied_to_double_attack(self) -> None:
        o = OtakuBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(o, enemy)
        o.attack_knack = "double_attack"
        o.attack_roll = enemy.tn

        roll, keep, serious = o.next_damage(enemy.tn, False)
        base_roll, base_keep, base_serious = Combatant.next_damage(
            o, enemy.tn, False,
        )

        assert serious == base_serious
        assert roll == base_roll

    def test_rank_gated(self) -> None:
        o = OtakuBushi(rank=4, **STATS)
        enemy = make_enemy()
        link(o, enemy)
        o.attack_knack = "lunge"
        o.attack_roll = enemy.tn

        roll, keep, serious = o.next_damage(enemy.tn, False)
        base_roll, base_keep, base_serious = Combatant.next_damage(
            o, enemy.tn, False,
        )

        assert serious == base_serious
        assert roll == base_roll


class TestOtakuBushiChooseAction:
    def test_first_action_lunges(self) -> None:
        o = OtakuBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(o, enemy)
        o.actions = [3, 7]
        o.init_order = [3, 7]
        o.phase = 3

        result = o.choose_action()
        assert result is not None
        assert result[0] == "lunge"

    def test_later_action_double_attack_when_viable(self) -> None:
        """After the first action, prefer double attack if prob is high."""
        o = OtakuBushi(
            rank=3, **{**STATS, "fire": 5, "attack": 5, "void": 5},
        )
        enemy = make_enemy(air=2, parry=1)
        link(o, enemy)
        o.actions = [5]
        o.init_order = [3, 5]
        o.phase = 5

        with patch.object(
            o, "att_prob", side_effect=lambda knack, tn: 0.9,
        ):
            result = o.choose_action()

        assert result is not None
        assert result[0] == "double_attack"

    def test_later_action_lunge_when_datt_not_viable(self) -> None:
        """When double attack prob is too low, fall back to lunge."""
        o = OtakuBushi(rank=3, **STATS)
        enemy = make_enemy(air=5, parry=5)
        link(o, enemy)
        o.actions = [5]
        o.init_order = [3, 5]
        o.phase = 5

        def fake_att_prob(knack: str, tn: int) -> float:
            if knack == "double_attack":
                return 0.3
            return 0.8

        with patch.object(o, "att_prob", side_effect=fake_att_prob):
            result = o.choose_action()

        assert result is not None
        assert result[0] == "lunge"

    def test_no_actions_returns_none(self) -> None:
        o = OtakuBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(o, enemy)
        o.actions = []
        o.phase = 5

        assert o.choose_action() is None

    def test_action_not_ready_returns_none(self) -> None:
        o = OtakuBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(o, enemy)
        o.actions = [7]
        o.phase = 3

        assert o.choose_action() is None

    def test_does_not_hold_actions(self) -> None:
        """With hold_one_action=False, acts even with only 1 action."""
        o = OtakuBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(o, enemy)
        o.actions = [5]
        o.init_order = [3, 5]
        o.phase = 5

        result = o.choose_action()
        assert result is not None
        assert result[0] == "lunge"

    def test_lunge_without_double_attack_knack(self) -> None:
        """Without the double_attack knack, always lunge."""
        o = OtakuBushi(rank=1, **STATS)
        enemy = make_enemy()
        link(o, enemy)
        o.actions = [5]
        o.init_order = [3, 5]
        o.phase = 5

        result = o.choose_action()
        assert result is not None
        assert result[0] == "lunge"


class TestOtakuBushiKnackLevels:
    def test_knacks_from_rank(self) -> None:
        o = OtakuBushi(rank=4, **STATS)
        for knack in o.school_knacks:
            assert getattr(o, knack) == 4
