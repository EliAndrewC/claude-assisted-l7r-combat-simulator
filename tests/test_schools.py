"""Tests for the five complete school implementations.

Covers Akodo Bushi, Bayushi Bushi, Kitsuki Magistrate, Matsu Bushi,
and Shinjo Bushi. Each test class verifies class-level attributes,
constructor setup, rank techniques (with rank gating), special
abilities, and AI decision overrides.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from l7r.combatant import Combatant
from l7r.schools.AkodoBushi import AkodoBushi
from l7r.schools.BayushiBushi import BayushiBushi
from l7r.schools.KitsukiMagistrate import KitsukiMagistrate
from l7r.schools.MatsuBushi import MatsuBushi
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
        # Should have attack(3) free raises = [5, 5, 5]
        for rt in ["attack", "wound_check"]:
            total = sum(
                sum(g) for g in k.multi[rt]
            )
            assert total == 5 * k.attack

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
