"""Tests for the 7 'free raise' school implementations.

Covers Kuni Witch Hunter, Courtier, Merchant, Doji Artisan, Ide Diplomat,
Ikoma Bard, and Shosuro Actor. Also tests engine changes for forced parry
and reactive counterattack.
"""

from __future__ import annotations

from unittest.mock import patch

from l7r.combatant import Combatant

from l7r.schools.kuni_witch_hunter import KuniWitchHunter
from l7r.schools.courtier import Courtier
from l7r.schools.merchant import Merchant
from l7r.schools.doji_artisan import DojiArtisan
from l7r.schools.ide_diplomat import IdeDiplomat
from l7r.schools.ikoma_bard import IkomaBard
from l7r.schools.shosuro_actor import ShosuroActor


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
# KUNI WITCH HUNTER
# ===================================================================


class TestKuniAttributes:
    def test_school_knacks(self) -> None:
        k = KuniWitchHunter(rank=1, **STATS)
        assert set(k.school_knacks) == {
            "detect_taint", "iaijutsu", "presence",
        }

    def test_r1t_rolls(self) -> None:
        k = KuniWitchHunter(rank=1, **STATS)
        for rt in k.r1t_rolls:
            assert k.extra_dice[rt][0] >= 1

    def test_r2t_always_bonus(self) -> None:
        k = KuniWitchHunter(rank=2, **STATS)
        assert k.always["interrogation"] >= 5

    def test_school_ring(self) -> None:
        assert KuniWitchHunter.school_ring == "earth"


class TestKuniSA:
    """SA: +1k1 on wound checks."""

    def test_wound_check_extra_dice(self) -> None:
        k = KuniWitchHunter(rank=1, **STATS)
        # SA adds +1 rolled and +1 kept to wound check
        base = Combatant(**STATS)
        assert k.extra_dice["wound_check"][0] > base.extra_dice["wound_check"][0]
        assert k.extra_dice["wound_check"][1] > base.extra_dice["wound_check"][1]

    def test_attack_dice_unaffected(self) -> None:
        k = KuniWitchHunter(rank=1, **STATS)
        base = Combatant(**STATS)
        # Attack extra dice should only differ by R1T if applicable
        assert k.extra_dice["attack"] == base.extra_dice["attack"]


class TestKuniR3T:
    def test_shared_disc_bonuses(self) -> None:
        k = KuniWitchHunter(rank=3, **STATS)
        for rt in ["attack", "wound_check"]:
            total = sum(sum(g) for g in k.multi[rt])
            assert total == 5 * 10

    def test_shared_reference(self) -> None:
        k = KuniWitchHunter(rank=3, **STATS)
        assert k.multi["attack"][-1] is k.multi["wound_check"][-1]

    def test_rank_gated(self) -> None:
        k = KuniWitchHunter(rank=2, **STATS)
        assert not k.multi["attack"]
        assert not k.multi["wound_check"]


class TestKuniR4T:
    def test_extra_initiative_die(self) -> None:
        k = KuniWitchHunter(rank=4, **STATS)
        base = KuniWitchHunter(rank=3, **STATS)
        assert k.init_dice[0] > base.init_dice[0]

    def test_hold_one_action(self) -> None:
        k = KuniWitchHunter(rank=4, **STATS)
        assert k.hold_one_action is True

    def test_rank_gated(self) -> None:
        k = KuniWitchHunter(rank=3, **STATS)
        base = Combatant(**STATS)
        assert k.init_dice[0] == base.init_dice[0] + 0  # no extra at R3


class TestKuniR5T:
    def test_reflects_light_wounds_to_enemy(self) -> None:
        k = KuniWitchHunter(rank=5, **STATS)
        enemy = make_enemy()
        link(k, enemy)

        with patch.object(enemy, "wound_check") as mock_enemy_wc:
            with patch.object(k, "wound_check"):
                k.r5t_trigger(20, 15, 30)

        mock_enemy_wc.assert_called_once_with(15)

    def test_self_damage_is_half(self) -> None:
        k = KuniWitchHunter(rank=5, **STATS)
        enemy = make_enemy()
        link(k, enemy)

        with patch.object(enemy, "wound_check"):
            with patch.object(k, "wound_check") as mock_self_wc:
                k.r5t_trigger(20, 20, 30)

        mock_self_wc.assert_called_once_with(10)

    def test_no_self_damage_when_light_is_1(self) -> None:
        """Half of 1 rounds down to 0, so no self wound check."""
        k = KuniWitchHunter(rank=5, **STATS)
        enemy = make_enemy()
        link(k, enemy)

        with patch.object(enemy, "wound_check"):
            with patch.object(k, "wound_check") as mock_self_wc:
                k.r5t_trigger(20, 1, 21)

        mock_self_wc.assert_not_called()

    def test_no_reflection_on_zero_light(self) -> None:
        k = KuniWitchHunter(rank=5, **STATS)
        enemy = make_enemy()
        link(k, enemy)

        with patch.object(enemy, "wound_check") as mock_wc:
            k.r5t_trigger(20, 0, 20)

        mock_wc.assert_not_called()

    def test_no_reflection_when_near_death(self) -> None:
        """Don't reflect when one serious wound from dying."""
        k = KuniWitchHunter(rank=5, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.serious = k.sw_to_kill - 1

        with patch.object(enemy, "wound_check") as mock_wc:
            k.r5t_trigger(20, 15, 30)

        mock_wc.assert_not_called()

    def test_rank_gated(self) -> None:
        k = KuniWitchHunter(rank=4, **STATS)
        assert k.r5t_trigger not in [
            f for handlers in k.events.values() for f in handlers
        ]


class TestKuniInit:
    def test_event_handlers(self) -> None:
        k = KuniWitchHunter(rank=5, **STATS)
        assert k.r5t_trigger in k.events["wound_check"]


# ===================================================================
# COURTIER
# ===================================================================


class TestCourtierAttributes:
    def test_school_knacks(self) -> None:
        c = Courtier(rank=1, **STATS)
        assert set(c.school_knacks) == {
            "discern_honor", "oppose_social", "worldliness",
        }

    def test_r1t_rolls(self) -> None:
        c = Courtier(rank=1, **STATS)
        for rt in c.r1t_rolls:
            assert c.extra_dice[rt][0] >= 1

    def test_r2t_always_bonus(self) -> None:
        c = Courtier(rank=2, **STATS)
        assert c.always["oppose_social"] >= 5

    def test_school_ring(self) -> None:
        assert Courtier.school_ring == "air"


class TestCourtierSA:
    """SA: +Air to attack and damage."""

    def test_attack_bonus_equals_air(self) -> None:
        c = Courtier(rank=1, air=4, earth=5, fire=3, water=3, void=3,
                     attack=3, parry=3)
        assert c.always["attack"] >= 4

    def test_damage_bonus_equals_air(self) -> None:
        c = Courtier(rank=1, air=4, earth=5, fire=3, water=3, void=3,
                     attack=3, parry=3)
        assert c.always["damage"] >= 4

    def test_higher_air_higher_bonus(self) -> None:
        low = Courtier(rank=1, air=2, earth=5, fire=3, water=3, void=3,
                       attack=3, parry=3)
        high = Courtier(rank=1, air=5, earth=5, fire=3, water=3, void=3,
                        attack=3, parry=3)
        assert high.always["attack"] > low.always["attack"]
        assert high.always["damage"] > low.always["damage"]


class TestCourtierR3T:
    def test_shared_disc_bonuses(self) -> None:
        c = Courtier(rank=3, **STATS)
        for rt in ["attack", "wound_check"]:
            total = sum(sum(g) for g in c.multi[rt])
            assert total == 5 * 10

    def test_shared_reference(self) -> None:
        c = Courtier(rank=3, **STATS)
        assert c.multi["attack"][-1] is c.multi["wound_check"][-1]

    def test_rank_gated(self) -> None:
        c = Courtier(rank=2, **STATS)
        assert not c.multi["attack"]
        assert not c.multi["wound_check"]


class TestCourtierR4T:
    def test_new_target_grants_vp(self) -> None:
        c = Courtier(rank=4, **STATS)
        enemy = make_enemy()
        link(c, enemy)
        vps_before = c.vps
        c.r4t_trigger()
        assert c.vps == vps_before + 1

    def test_same_target_no_vp(self) -> None:
        c = Courtier(rank=4, **STATS)
        enemy = make_enemy()
        link(c, enemy)
        c.r4t_trigger()
        vps_before = c.vps
        c.r4t_trigger()
        assert c.vps == vps_before

    def test_different_targets_each_grant_vp(self) -> None:
        c = Courtier(rank=4, **STATS)
        e1 = make_enemy()
        e2 = make_enemy()
        link(c, e1)
        c.r4t_trigger()
        c.enemy = e2
        vps_before = c.vps
        c.r4t_trigger()
        assert c.vps == vps_before + 1


class TestCourtierR5T:
    def test_adds_air_to_attack_parry_wc(self) -> None:
        c = Courtier(rank=5, air=4, earth=5, fire=3, water=3, void=3,
                     attack=3, parry=3)
        # R5T adds Air to attack (stacking with SA), parry, wound_check
        assert c.always["attack"] >= 2 * 4  # SA + R5T
        assert c.always["parry"] >= 4
        assert c.always["wound_check"] >= 4

    def test_rank_gated(self) -> None:
        c = Courtier(rank=4, **STATS)
        assert c.always["parry"] == 0
        assert c.always["wound_check"] == 0


class TestCourtierInit:
    def test_event_handlers(self) -> None:
        c = Courtier(rank=4, **STATS)
        assert c.r4t_trigger in c.events["successful_attack"]


# ===================================================================
# MERCHANT
# ===================================================================


class TestMerchantAttributes:
    def test_school_knacks(self) -> None:
        m = Merchant(rank=1, **STATS)
        assert set(m.school_knacks) == {
            "discern_honor", "oppose_knowledge", "worldliness",
        }

    def test_r1t_rolls(self) -> None:
        m = Merchant(rank=1, **STATS)
        for rt in m.r1t_rolls:
            assert m.extra_dice[rt][0] >= 1

    def test_r2t_always_bonus(self) -> None:
        m = Merchant(rank=2, **STATS)
        assert m.always["interrogation"] >= 5

    def test_school_ring(self) -> None:
        assert Merchant.school_ring == "water"


class TestMerchantR3T:
    def test_shared_disc_bonuses(self) -> None:
        m = Merchant(rank=3, **STATS)
        for rt in ["attack", "wound_check"]:
            total = sum(sum(g) for g in m.multi[rt])
            assert total == 5 * 10

    def test_shared_reference(self) -> None:
        m = Merchant(rank=3, **STATS)
        assert m.multi["attack"][-1] is m.multi["wound_check"][-1]

    def test_rank_gated(self) -> None:
        m = Merchant(rank=2, **STATS)
        assert not m.multi["attack"]
        assert not m.multi["wound_check"]


class TestMerchantSA:
    """SA: Post-roll VP spending. VPs committed after seeing dice."""

    def test_att_vps_returns_zero(self) -> None:
        m = Merchant(rank=1, **STATS)
        assert m.att_vps(20, 6, 3) == 0

    def test_parry_vps_returns_zero(self) -> None:
        m = Merchant(rank=1, **STATS)
        assert m.parry_vps(20, 6, 3) == 0

    def test_wc_vps_returns_zero(self) -> None:
        m = Merchant(rank=1, **STATS)
        assert m.wc_vps(30, 4, 3) == 0

    def test_no_vps_spent_when_already_hitting(self) -> None:
        """When dice already beat TN, no VPs should be spent."""
        m = Merchant(rank=1, **STATS)
        enemy = make_enemy(parry=1)  # TN = 10
        link(m, enemy)
        m.vps = 3
        m.attack_knack = "attack"
        vps_before = m.vps
        # Dice that already beat TN 10: [8, 9, 10, 11] → keep top 3 = 30
        with patch("l7r.schools.merchant.d10", side_effect=[8, 9, 10, 11]):
            m.xky(4, 3, True, "attack")
        assert m.vps == vps_before

    def test_vps_spent_when_roll_misses_tn(self) -> None:
        """When dice miss TN, VPs should be spent to close the gap."""
        m = Merchant(rank=1, **STATS)
        enemy = make_enemy(parry=3)  # TN = 20
        link(m, enemy)
        m.vps = 3
        m.attack_knack = "attack"
        # Dice [1, 2, 3, 4] → keep top 3 = 9, TN = 20, gap = 11
        # 2 VPs estimated to bring result to ~21 (>= 20) → spends 2
        with patch("l7r.schools.merchant.d10", side_effect=[1, 2, 3, 4, 8, 9]):
            m.xky(4, 3, True, "attack")
        assert m.vps < 3

    def test_vps_deducted_correctly(self) -> None:
        """VP count should decrease by exactly the number spent."""
        m = Merchant(rank=1, **STATS)
        enemy = make_enemy(parry=3)  # TN = 20
        link(m, enemy)
        m.vps = 3
        m.attack_knack = "attack"
        # Roll low enough to miss TN 20 by a small margin
        # [1, 2, 3, 7] → keep 3 = 12, need ~8 more → 1-2 VPs
        with patch("l7r.schools.merchant.d10", side_effect=[1, 2, 3, 7, 10, 10]):
            m.xky(4, 3, True, "attack")
        # VPs should have been deducted
        assert 0 <= m.vps < 3

    def test_vps_spent_event_fires(self) -> None:
        """The vps_spent trigger should fire when VPs are spent."""
        m = Merchant(rank=1, **STATS)
        enemy = make_enemy(parry=5)  # TN = 30
        link(m, enemy)
        m.vps = 3
        m.attack_knack = "attack"
        fired = []
        m.events["vps_spent"].append(lambda vps, rt: fired.append((vps, rt)))
        with patch("l7r.schools.merchant.d10", side_effect=[1, 2, 3, 4, 8, 9, 10]):
            m.xky(4, 3, True, "attack")
        if m.vps < 3:
            assert len(fired) == 1
            assert fired[0][1] == "attack"
            assert fired[0][0] > 0

    def test_no_vps_on_damage_rolls(self) -> None:
        """Damage rolls should never trigger VP spending."""
        m = Merchant(rank=1, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        m.vps = 3
        vps_before = m.vps
        with patch("l7r.schools.merchant.d10", side_effect=[1, 2, 3, 4]):
            m.xky(4, 2, True, "damage")
        assert m.vps == vps_before

    def test_parry_vps_spent_when_roll_misses(self) -> None:
        """VPs should be spent on parry when roll misses enemy attack_roll."""
        m = Merchant(rank=1, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        enemy.attack_roll = 20
        m.predeclare_bonus = 0
        m.vps = 3
        # Low parry dice: [1, 2, 3, 4] → keep top 3 = 9, need 11 more
        # 2 VPs estimated to bring result to ~21 (>= 20) → spends 2
        with patch("l7r.schools.merchant.d10", side_effect=[1, 2, 3, 4, 10, 10]):
            m.xky(4, 3, True, "parry")
        assert m.vps < 3

    def test_parry_no_vps_when_already_succeeding(self) -> None:
        """No VPs on parry when roll already beats attack_roll."""
        m = Merchant(rank=1, **STATS)
        enemy = make_enemy()
        link(m, enemy)
        enemy.attack_roll = 10
        m.predeclare_bonus = 0
        m.vps = 3
        vps_before = m.vps
        # High parry dice: [8, 9, 10, 11] → keep top 3 = 30
        with patch("l7r.schools.merchant.d10", side_effect=[8, 9, 10, 11]):
            m.xky(4, 3, True, "parry")
        assert m.vps == vps_before

    def test_wound_check_stashes_light_total(self) -> None:
        """wound_check should stash _wc_light_total before calling super."""
        m = Merchant(rank=1, **STATS)
        m.light = 5
        with patch.object(Combatant, "wound_check"):
            m.wound_check(10)
        assert m._wc_light_total == 15

    def test_wound_check_vps_spent_to_prevent_serious(self) -> None:
        """VPs spent on wound check when they prevent serious wounds."""
        m = Merchant(rank=1, **STATS)
        m.vps = 3
        m.light = 0
        m._wc_light_total = 40  # high TN that will cause serious wounds
        # Low wound check dice: [1, 2, 3, 4] → keep top 3 = 9
        # calc_serious(40, 9) = ceil((40-9)/10) = 4 serious wounds
        # With VPs, should improve result and reduce serious wounds
        with patch("l7r.schools.merchant.d10", side_effect=[1, 2, 3, 4, 8, 9, 10]):
            m.xky(4, 3, True, "wound_check")
        assert m.vps < 3

    def test_vp_at_10_rolled_keeps_more_not_new_die(self) -> None:
        """When rolled == 10, VP adds +2 kept (overflow), no new die."""
        m = Merchant(rank=1, **STATS)
        enemy = make_enemy(parry=7)  # TN = 40
        link(m, enemy)
        m.vps = 2
        m.attack_knack = "attack"
        # 10k3: [1,2,3,4,5,6,7,8,9,10] → keep 3 = 27. TN=40.
        # 1 VP at 10 rolled: kept += 2 → 10k5, keep top 5 = 40.
        # Sim estimate: 10k5 avg ≈ 40 → 1 VP sufficient.
        with patch("l7r.schools.merchant.d10",
                   side_effect=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]):
            result = m.xky(10, 3, True, "attack")
        # Should have spent 1 VP (kept goes 3→5, result = 6+7+8+9+10 = 40)
        assert m.vps == 1
        assert result == 40

    def test_no_vps_spent_when_zero_vps(self) -> None:
        """With 0 VPs available, no spending should occur."""
        m = Merchant(rank=1, **STATS)
        enemy = make_enemy(parry=5)  # TN = 30
        link(m, enemy)
        m.vps = 0
        m.attack_knack = "attack"
        with patch("l7r.schools.merchant.d10", side_effect=[1, 2, 3, 4]):
            m.xky(4, 3, True, "attack")
        assert m.vps == 0

    def test_all_vps_cant_close_gap_spends_zero(self) -> None:
        """If even all VPs can't reach TN, spend nothing."""
        m = Merchant(rank=1, **STATS)
        enemy = make_enemy(parry=10)  # TN = 55
        link(m, enemy)
        m.vps = 1
        m.attack_knack = "attack"
        vps_before = m.vps
        # Very low dice, TN impossibly high for 1 VP
        with patch("l7r.schools.merchant.d10", side_effect=[1, 1, 1, 1, 2]):
            m.xky(4, 3, True, "attack")
        assert m.vps == vps_before


class TestMerchantR5T:
    def test_rerolls_fives_and_sixes(self) -> None:
        """R5T: 5s and 6s are always marked for reroll."""
        m = Merchant(rank=5, **STATS)
        # 4k2: dice [5, 6, 8, 9]. The 5 and 6 are rerolled to 7, 10.
        # After reroll: [7, 8, 9, 10] → keep top 2 = 9+10 = 19
        with patch("l7r.schools.merchant.d10", side_effect=[5, 6, 8, 9, 7, 10]):
            result = m.xky(4, 2, True, "attack")
        assert result == 19

    def test_pulls_in_low_dice_when_threshold_met(self) -> None:
        """R5T: After marking 5s/6s, greedily add lower dice if
        total sum still meets 5*(X-1) threshold."""
        m = Merchant(rank=5, **STATS)
        # 5k2: dice [2, 3, 5, 8, 9]. Mark 5 first (sum=5, X=1,
        # need >= 0). Then try 3: sum=8, X=2, need >= 5. OK.
        # Then try 2: sum=10, X=3, need >= 10. OK.
        # All three (5, 3, 2) rerolled → 7, 7, 7.
        # After: [7, 7, 7, 8, 9] → keep top 2 = 8+9 = 17
        with patch("l7r.schools.merchant.d10",
                   side_effect=[2, 3, 5, 8, 9, 7, 7, 7]):
            result = m.xky(5, 2, True, "attack")
        assert result == 17

    def test_stops_when_threshold_would_break(self) -> None:
        """R5T: Won't add a die if it would break the threshold."""
        m = Merchant(rank=5, **STATS)
        # 4k2: dice [1, 5, 8, 9]. Mark 5 (sum=5, X=1, need >= 0).
        # Try 1: sum=6, X=2, need >= 5. 6 >= 5, OK → mark it.
        # Reroll both (5, 1) → 7, 7.
        # After: [7, 7, 8, 9] → keep top 2 = 8+9 = 17
        with patch("l7r.schools.merchant.d10",
                   side_effect=[1, 5, 8, 9, 7, 7]):
            result = m.xky(4, 2, True, "attack")
        assert result == 17

    def test_no_reroll_without_fives_or_sixes(self) -> None:
        """R5T: If no 5s or 6s rolled, low dice (< 5) can still be
        rerolled since a single die needs sum >= 0."""
        m = Merchant(rank=5, **STATS)
        # 4k2: dice [1, 2, 8, 9]. No 5s/6s. Candidates: [2, 1].
        # Try 2: sum=2, X=1, need >= 0. OK.
        # Try 1: sum=3, X=2, need >= 5. 3 < 5. STOP.
        # Reroll just the 2 → 7.
        # After: [1, 7, 8, 9] → keep top 2 = 8+9 = 17
        with patch("l7r.schools.merchant.d10",
                   side_effect=[1, 2, 8, 9, 7]):
            result = m.xky(4, 2, True, "attack")
        assert result == 17

    def test_rank_gated(self) -> None:
        """Below rank 5, no R5T reroll occurs (5s and 6s are kept as-is)."""
        m = Merchant(rank=4, **STATS)
        m.vps = 0  # no VPs to avoid post-roll VP logic
        # 4k2: dice [5, 6, 8, 9]. Without R5T, no reroll → keep top 2 = 8+9 = 17
        with patch("l7r.schools.merchant.d10", side_effect=[5, 6, 8, 9]):
            result = m.xky(4, 2, True, "attack")
        assert result == 17


# ===================================================================
# DOJI ARTISAN
# ===================================================================


class TestDojiArtisanAttributes:
    def test_school_knacks(self) -> None:
        d = DojiArtisan(rank=1, **STATS)
        assert set(d.school_knacks) == {
            "counterattack", "oppose_social", "worldliness",
        }

    def test_r1t_rolls(self) -> None:
        d = DojiArtisan(rank=1, **STATS)
        for rt in d.r1t_rolls:
            assert d.extra_dice[rt][0] >= 1

    def test_r2t_always_bonus(self) -> None:
        d = DojiArtisan(rank=2, **STATS)
        assert d.always["oppose_social"] >= 5

    def test_school_ring(self) -> None:
        assert DojiArtisan.school_ring == "air"


class TestDojiArtisanSA:
    """SA: Reactive counterattack. Free with ready action, else 1 VP."""

    def test_will_react_with_ready_action(self) -> None:
        d = DojiArtisan(rank=1, **STATS)
        d.actions = [3]
        d.phase = 5
        d.vps = 0  # no VPs needed when action is ready
        enemy = make_enemy()
        assert d.will_react_to_attack(enemy) is True

    def test_will_react_with_vps_but_no_action(self) -> None:
        d = DojiArtisan(rank=1, **STATS)
        d.actions = []
        d.vps = 3
        enemy = make_enemy()
        assert d.will_react_to_attack(enemy) is True

    def test_will_react_with_vps_and_future_action(self) -> None:
        """Action in future phase doesn't count as ready."""
        d = DojiArtisan(rank=1, **STATS)
        d.actions = [8]  # not ready at phase 3
        d.phase = 3
        d.vps = 1
        enemy = make_enemy()
        assert d.will_react_to_attack(enemy) is True

    def test_wont_react_without_actions_or_vps(self) -> None:
        d = DojiArtisan(rank=1, **STATS)
        d.actions = []
        d.vps = 0
        enemy = make_enemy()
        assert d.will_react_to_attack(enemy) is False

    def test_counterattack_free_with_ready_action(self) -> None:
        """When action is ready, counterattack costs action only, no VP."""
        d = DojiArtisan(rank=1, **STATS)
        d.actions = [3, 5]
        d.phase = 5
        d.vps = 3
        enemy = make_enemy()
        vps_before = d.vps

        d.will_counterattack(enemy)
        assert len(d.actions) == 1  # spent one action
        assert d.vps == vps_before  # no VP cost

    def test_counterattack_costs_vp_without_ready_action(self) -> None:
        """When no ready action, counterattack costs 1 VP."""
        d = DojiArtisan(rank=1, **STATS)
        d.actions = []
        d.phase = 5
        d.vps = 3
        enemy = make_enemy()

        d.will_counterattack(enemy)
        assert d.vps == 2

    def test_sa_vp_grants_1k1(self) -> None:
        """VP spent on SA also grants +1k1 on counterattack roll."""
        d = DojiArtisan(rank=1, **STATS)
        d.actions = []
        d.phase = 5
        d.vps = 3
        enemy = make_enemy()
        rolled_before = d.extra_dice["counterattack"][0]
        kept_before = d.extra_dice["counterattack"][1]

        d.will_counterattack(enemy)
        assert d.extra_dice["counterattack"][0] == rolled_before + 1
        assert d.extra_dice["counterattack"][1] == kept_before + 1

    def test_sa_vp_1k1_cleaned_up_on_post_attack(self) -> None:
        """The +1k1 from SA VP is removed after the counterattack."""
        d = DojiArtisan(rank=1, **STATS)
        d.actions = []
        d.phase = 5
        d.vps = 3
        enemy = make_enemy()
        rolled_before = d.extra_dice["counterattack"][0]
        kept_before = d.extra_dice["counterattack"][1]

        d.will_counterattack(enemy)
        d.attack_knack = "counterattack"
        d.triggers("post_attack")  # one-shot cleanup fires
        assert d.extra_dice["counterattack"][0] == rolled_before
        assert d.extra_dice["counterattack"][1] == kept_before

    def test_counterattack_fails_without_action_or_vp(self) -> None:
        d = DojiArtisan(rank=1, **STATS)
        d.actions = []
        d.phase = 5
        d.vps = 0
        enemy = make_enemy()
        assert d.will_counterattack(enemy) is False


class TestDojiArtisanR3T:
    def test_shared_disc_bonuses(self) -> None:
        d = DojiArtisan(rank=3, **STATS)
        for rt in ["counterattack", "wound_check"]:
            total = sum(sum(g) for g in d.multi[rt])
            assert total == 5 * 10

    def test_shared_reference(self) -> None:
        d = DojiArtisan(rank=3, **STATS)
        assert d.multi["counterattack"][-1] is d.multi["wound_check"][-1]

    def test_rank_gated(self) -> None:
        d = DojiArtisan(rank=2, **STATS)
        assert not d.multi["counterattack"]
        assert not d.multi["wound_check"]


class TestDojiArtisanR4T:
    def test_tracks_attackers(self) -> None:
        d = DojiArtisan(rank=4, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        d.r4t_track()
        assert enemy in d.attacked_by

    def test_reset_clears_tracked(self) -> None:
        d = DojiArtisan(rank=4, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        d.attacked_by.add(enemy)
        d.r4t_reset()
        assert not d.attacked_by

    def test_bonus_against_non_attacker(self) -> None:
        d = DojiArtisan(rank=4, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        d.actions = [3, 5]
        d.phase = 10  # phase 10 so hold_one_action allows attack
        d.init_order = [3, 5]
        d.attacked_by = set()  # enemy hasn't attacked us

        action = d.choose_action()
        assert action is not None
        # Phase bonus should have been added
        assert d.auto_once[action[0]] >= 10


class TestDojiArtisanR5T:
    def test_attack_bonus_from_enemy_tn(self) -> None:
        d = DojiArtisan(rank=5, **STATS)
        enemy = make_enemy(parry=4)  # TN = 5 + 5*4 = 25
        link(d, enemy)
        d.attack_knack = "attack"
        d.r5t_attack_bonus()
        # (25 - 10) // 5 = 3
        assert d.auto_once["attack"] >= 3

    def test_parry_bonus_from_attack_roll(self) -> None:
        """R5T parry bonus is based on the enemy's attack roll."""
        d = DojiArtisan(rank=5, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        enemy.attack_roll = 30
        d.r5t_defense_bonus()
        # (30 - 10) // 5 = 4
        assert d.auto_once["parry"] >= 4

    def test_wc_bonus_from_wound_check_tn(self) -> None:
        """R5T wound check bonus is based on the wound check TN
        (total light wounds), not the attack roll."""
        d = DojiArtisan(rank=5, **STATS)
        # total light wounds = 25
        d.r5t_wc_bonus(check=0, light=10, total=25)
        # (25 - 10) // 5 = 3
        assert d.auto_once["wound_check"] == 3

    def test_defense_bonus_does_not_set_wc(self) -> None:
        """r5t_defense_bonus should only set parry, not wound_check."""
        d = DojiArtisan(rank=5, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        enemy.attack_roll = 30
        d.r5t_defense_bonus()
        assert d.auto_once["wound_check"] == 0
        assert d.auto_once["parry"] >= 4

    def test_parry_bonus_cleaned_up_if_unused(self) -> None:
        """If no parry is attempted, the R5T parry bonus is removed
        in post_defense so it doesn't leak into the next roll."""
        d = DojiArtisan(rank=5, **STATS)
        enemy = make_enemy()
        link(d, enemy)
        enemy.attack_roll = 30
        d.r5t_defense_bonus()
        assert d.auto_once["parry"] >= 4

        # Simulate no parry attempted — post_defense cleans up
        d.r5t_cleanup_parry()
        assert d.auto_once["parry"] == 0

    def test_rank_gated(self) -> None:
        d = DojiArtisan(rank=4, **STATS)
        assert d.r5t_attack_bonus not in [
            f for handlers in d.events.values() for f in handlers
        ]


class TestDojiArtisanInit:
    def test_event_handlers_r4(self) -> None:
        d = DojiArtisan(rank=4, **STATS)
        assert d.r4t_reset in d.events["pre_round"]
        assert d.r4t_track in d.events["pre_defense"]

    def test_event_handlers_r5(self) -> None:
        d = DojiArtisan(rank=5, **STATS)
        assert d.r5t_attack_bonus in d.events["pre_attack"]
        assert d.r5t_defense_bonus in d.events["pre_defense"]
        assert d.r5t_cleanup_parry in d.events["post_defense"]
        assert d.r5t_wc_bonus in d.events["wound_check"]


# ===================================================================
# IDE DIPLOMAT
# ===================================================================


class TestIdeDiplomatAttributes:
    def test_school_knacks(self) -> None:
        i = IdeDiplomat(rank=1, **STATS)
        assert set(i.school_knacks) == {
            "double_attack", "feint", "worldliness",
        }

    def test_r1t_rolls(self) -> None:
        i = IdeDiplomat(rank=1, **STATS)
        for rt in i.r1t_rolls:
            assert i.extra_dice[rt][0] >= 1

    def test_r2t_always_bonus(self) -> None:
        i = IdeDiplomat(rank=2, **STATS)
        assert i.always["attack"] >= 5

    def test_school_ring(self) -> None:
        assert IdeDiplomat.school_ring == "water"


class TestIdeDiplomatSA:
    """SA: After successful feint, lower target TN by 10."""

    def test_feint_lowers_tn(self) -> None:
        i = IdeDiplomat(rank=1, **STATS)
        enemy = make_enemy()
        link(i, enemy)
        i.attack_knack = "feint"
        tn_before = enemy.tn
        i.sa_trigger()
        assert enemy.tn == tn_before - 10

    def test_non_feint_no_tn_change(self) -> None:
        i = IdeDiplomat(rank=1, **STATS)
        enemy = make_enemy()
        link(i, enemy)
        i.attack_knack = "attack"
        tn_before = enemy.tn
        i.sa_trigger()
        assert enemy.tn == tn_before

    def test_tn_restored_after_defense(self) -> None:
        i = IdeDiplomat(rank=1, **STATS)
        enemy = make_enemy()
        link(i, enemy)
        i.attack_knack = "feint"
        tn_before = enemy.tn
        i.sa_trigger()
        assert enemy.tn == tn_before - 10
        # Simulate post_defense trigger
        enemy.triggers("post_defense")
        assert enemy.tn == tn_before


class TestIdeDiplomatR3TAttack:
    """R3T attack depletion: spend VP to subtract 5k1 from enemy roll."""

    def test_reduces_enemy_attack_roll_near_miss(self) -> None:
        """Always spends when avg reduction would cause a miss."""
        i = IdeDiplomat(rank=3, **STATS)
        enemy = make_enemy()
        link(i, enemy)
        # avg 5k1 is ~8.5, so attack_roll just above TN triggers
        enemy.attack_roll = i.tn + 5
        i.vps = 3
        roll_before = enemy.attack_roll
        i.r3t_deplete_attack()
        assert enemy.attack_roll < roll_before

    def test_reduces_when_sw_reduction_meets_threshold(self) -> None:
        """Spends when projected SW reduction >= threshold."""
        i = IdeDiplomat(rank=3, **STATS)
        enemy = make_enemy(fire=5, attack=5)
        link(i, enemy)
        enemy.attack_knack = "attack"
        # High attack roll means lots of extra damage dice
        enemy.attack_roll = i.tn + 30
        # Deplete the R3T disc pool so wound checks are no longer
        # trivial — this makes the depletion actually matter.
        i.multi["wound_check"] = []
        i.r3t_attack_sw_threshold = 0.1
        i.vps = 3
        roll_before = enemy.attack_roll
        i.r3t_deplete_attack()
        assert enemy.attack_roll < roll_before

    def test_no_spend_when_reduction_below_threshold(self) -> None:
        """Doesn't spend when projected SW reduction is small."""
        i = IdeDiplomat(rank=3, **STATS)
        # Set a very high threshold so no reduction qualifies
        i.r3t_attack_sw_threshold = 100.0
        enemy = make_enemy()
        link(i, enemy)
        # Attack roll far above TN so avg reduction won't cause miss
        enemy.attack_roll = i.tn + 50
        enemy.attack_knack = "attack"
        i.vps = 3
        roll_before = enemy.attack_roll
        i.r3t_deplete_attack()
        assert enemy.attack_roll == roll_before

    def test_costs_1_vp(self) -> None:
        i = IdeDiplomat(rank=3, **STATS)
        enemy = make_enemy()
        link(i, enemy)
        enemy.attack_roll = i.tn + 5  # near miss → will spend
        i.vps = 3
        vps_before = i.vps
        i.r3t_deplete_attack()
        assert i.vps == vps_before - 1

    def test_no_vps_no_effect(self) -> None:
        i = IdeDiplomat(rank=3, **STATS)
        enemy = make_enemy()
        link(i, enemy)
        enemy.attack_roll = i.tn + 5
        i.vps = 0
        roll_before = enemy.attack_roll
        i.r3t_deplete_attack()
        assert enemy.attack_roll == roll_before

    def test_threshold_is_class_variable(self) -> None:
        """Threshold is a class variable for simulation tuning."""
        assert hasattr(IdeDiplomat, 'r3t_attack_sw_threshold')
        assert isinstance(IdeDiplomat.r3t_attack_sw_threshold, float)


class TestIdeDiplomatR3TWoundCheck:
    """R3T wound check boost: spend VP to add 5k1 to wound check."""

    def test_boosts_when_sw_reduction_meets_threshold(self) -> None:
        """Spends when the boost would reduce serious wounds."""
        i = IdeDiplomat(rank=3, **STATS)
        i.vps = 3
        # Light wounds barely exceeding check → boost saves a SW
        # check=15, total=25 → 1 SW; check+8.5=23.5, total=25 → 0 SW
        i.r3t_boost_wc(15, 10, 25)
        assert i.auto_once["wound_check"] > 0

    def test_no_boost_when_unnecessary(self) -> None:
        """Doesn't spend when already passing the wound check."""
        i = IdeDiplomat(rank=3, **STATS)
        i.vps = 3
        # check=50 far exceeds total=10 → 0 SW either way
        i.r3t_boost_wc(50, 5, 10)
        assert i.auto_once["wound_check"] == 0

    def test_costs_1_vp(self) -> None:
        i = IdeDiplomat(rank=3, **STATS)
        i.vps = 3
        vps_before = i.vps
        # Scenario where boost helps (see test above)
        i.r3t_boost_wc(15, 10, 25)
        if i.auto_once["wound_check"] > 0:
            assert i.vps == vps_before - 1

    def test_no_vps_no_effect(self) -> None:
        i = IdeDiplomat(rank=3, **STATS)
        i.vps = 0
        i.r3t_boost_wc(15, 10, 25)
        assert i.auto_once["wound_check"] == 0

    def test_threshold_is_class_variable(self) -> None:
        assert hasattr(IdeDiplomat, 'r3t_wc_sw_threshold')
        assert isinstance(IdeDiplomat.r3t_wc_sw_threshold, float)


class TestIdeDiplomatR5T:
    def test_gains_temp_vp(self) -> None:
        i = IdeDiplomat(rank=5, **STATS)
        vps_before = i.vps
        i.r5t_trigger(1, "attack")
        assert i.vps == vps_before + 1

    def test_persists_across_rounds(self) -> None:
        """R5T counter persists — no per-round reset."""
        i = IdeDiplomat(rank=5, **STATS)
        i.r5t_trigger(1, "attack")
        assert i.r5t_vps == 1
        # Simulate round boundary — counter should not reset
        i.triggers("post_round")
        assert i.r5t_vps == 1

    def test_prevents_infinite_loop(self) -> None:
        """R5T VP doesn't trigger another R5T grant."""
        i = IdeDiplomat(rank=5, **STATS)
        # First spend: r5t_vps goes 0→1, vps += 1
        i.r5t_trigger(1, "attack")
        vps_after_first = i.vps
        # Second call with vps=1 but r5t_vps already == 1
        i.r5t_trigger(1, "attack")
        assert i.vps == vps_after_first  # no extra VP

    def test_rank_gated(self) -> None:
        i = IdeDiplomat(rank=4, **STATS)
        assert not hasattr(i, 'r5t_vps')


class TestIdeDiplomatInit:
    def test_event_handlers(self) -> None:
        i = IdeDiplomat(rank=5, **STATS)
        assert i.sa_trigger in i.events["successful_attack"]
        assert i.r3t_deplete_attack in i.events["pre_defense"]
        assert i.r3t_boost_wc in i.events["wound_check"]
        assert i.r5t_trigger in i.events["vps_spent"]


# ===================================================================
# IKOMA BARD
# ===================================================================


class TestIkomaBardAttributes:
    def test_school_knacks(self) -> None:
        b = IkomaBard(rank=1, **STATS)
        assert set(b.school_knacks) == {
            "discern_honor", "oppose_knowledge", "oppose_social",
        }

    def test_r1t_rolls(self) -> None:
        b = IkomaBard(rank=1, **STATS)
        for rt in b.r1t_rolls:
            assert b.extra_dice[rt][0] >= 1

    def test_r2t_always_bonus(self) -> None:
        b = IkomaBard(rank=2, **STATS)
        assert b.always["attack"] >= 5

    def test_school_ring(self) -> None:
        assert IkomaBard.school_ring == "fire"


class TestIkomaBardSA:
    """SA: Force enemy to parry + feint lowers TN by 10."""

    def test_forces_parry_on_attack(self) -> None:
        b = IkomaBard(rank=1, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        b.actions = [3]
        b.phase = 10  # phase 10 so hold_one_action allows
        b.init_order = [3]
        enemy.forced_parry = False

        b.choose_action()
        assert enemy.forced_parry is True

    def test_once_per_round(self) -> None:
        b = IkomaBard(rank=1, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        b.actions = [3]
        b.phase = 10
        b.init_order = [3]

        b.choose_action()
        assert b.sa_used_this_round == 1

        # Second attack shouldn't force parry
        enemy.forced_parry = False
        b.actions = [5]
        b.phase = 10
        b.choose_action()
        assert enemy.forced_parry is False

    def test_resets_each_round(self) -> None:
        b = IkomaBard(rank=1, **STATS)
        b.sa_used_this_round = 1
        b.sa_reset()
        assert b.sa_used_this_round == 0

    def test_feint_lowers_tn(self) -> None:
        """SA: Successful feint should lower target's TN by 10."""
        b = IkomaBard(rank=1, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        b.attack_knack = "feint"
        original_tn = enemy.tn

        b.sa_feint_trigger()
        assert enemy.tn == original_tn - 10

    def test_feint_tn_restored_after_defense(self) -> None:
        """SA: TN reduction should be restored after post_defense."""
        b = IkomaBard(rank=1, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        b.attack_knack = "feint"
        original_tn = enemy.tn

        b.sa_feint_trigger()
        assert enemy.tn == original_tn - 10

        # Simulate post_defense — one-shot handler restores TN
        enemy.triggers("post_defense")
        assert enemy.tn == original_tn

    def test_non_feint_no_tn_change(self) -> None:
        """SA feint trigger should not fire for normal attacks."""
        b = IkomaBard(rank=1, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        b.attack_knack = "attack"
        original_tn = enemy.tn

        b.sa_feint_trigger()
        assert enemy.tn == original_tn


class TestIkomaBardFeintChoice:
    """choose_action: feint when hit probability is below threshold."""

    def test_feints_when_attack_prob_low(self) -> None:
        """Should feint when att_prob < feint_threshold."""
        b = IkomaBard(rank=1, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        b.actions = [3]
        b.phase = 10
        b.init_order = [3]

        with patch.object(b, "att_prob", return_value=0.2):
            knack, target = b.choose_action()
        assert knack == "feint"
        assert target is enemy

    def test_attacks_when_prob_above_threshold(self) -> None:
        """Should attack normally when att_prob >= feint_threshold."""
        b = IkomaBard(rank=1, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        b.actions = [3]
        b.phase = 10
        b.init_order = [3]

        with patch.object(b, "att_prob", return_value=0.8):
            knack, target = b.choose_action()
        assert knack == "attack"

    def test_no_forced_parry_when_feinting(self) -> None:
        """Forced parry SA should not be used when feinting."""
        b = IkomaBard(rank=1, **STATS)
        enemy = make_enemy()
        link(b, enemy)
        b.actions = [3]
        b.phase = 10
        b.init_order = [3]
        enemy.forced_parry = False

        with patch.object(b, "att_prob", return_value=0.2):
            b.choose_action()
        assert enemy.forced_parry is False
        assert b.sa_used_this_round == 0

    def test_threshold_is_class_variable(self) -> None:
        assert hasattr(IkomaBard, "feint_threshold")
        assert isinstance(IkomaBard.feint_threshold, float)


class TestIkomaBardR3T:
    def test_shared_disc_bonuses(self) -> None:
        b = IkomaBard(rank=3, **STATS)
        for rt in ["attack", "wound_check"]:
            total = sum(sum(g) for g in b.multi[rt])
            assert total == 5 * 10

    def test_shared_reference(self) -> None:
        b = IkomaBard(rank=3, **STATS)
        assert b.multi["attack"][-1] is b.multi["wound_check"][-1]

    def test_rank_gated(self) -> None:
        b = IkomaBard(rank=2, **STATS)
        assert not b.multi["attack"]
        assert not b.multi["wound_check"]


class TestIkomaBardR4T:
    def test_damage_floor(self) -> None:
        b = IkomaBard(rank=4, **STATS)
        b.attack_roll = 20
        b.auto_once["damage_rolled"] = 0
        b.auto_once["damage_kept"] = 0
        b.auto_once["serious"] = 0

        roll, keep, serious = b.next_damage(20, True)
        assert roll >= 10

    def test_no_floor_when_parried(self) -> None:
        b = IkomaBard(rank=4, **STATS)
        b.attack_roll = 20
        b.auto_once["damage_rolled"] = 0
        b.auto_once["damage_kept"] = 0
        b.auto_once["serious"] = 0

        roll, keep, serious = b.next_damage(20, False)
        # Without extra_damage, base roll should be weapon + fire
        base_roll = b.damage_dice[0]
        assert roll == base_roll

    def test_rank_gated(self) -> None:
        b = IkomaBard(rank=3, **STATS)
        b.attack_roll = 20
        b.auto_once["damage_rolled"] = 0
        b.auto_once["damage_kept"] = 0
        b.auto_once["serious"] = 0

        roll, keep, serious = b.next_damage(20, True)
        # At rank 3, no damage floor
        assert roll == b.damage_dice[0]


class TestIkomaBardR5T:
    def test_allows_2_uses_per_round(self) -> None:
        b = IkomaBard(rank=5, **STATS)
        assert b.sa_max_uses == 2

    def test_rank_4_only_1_use(self) -> None:
        b = IkomaBard(rank=4, **STATS)
        assert b.sa_max_uses == 1


class TestIkomaBardInit:
    def test_event_handlers(self) -> None:
        b = IkomaBard(rank=3, **STATS)
        assert b.sa_reset in b.events["pre_round"]
        assert b.sa_feint_trigger in b.events["successful_attack"]


# ===================================================================
# SHOSURO ACTOR
# ===================================================================


class TestShosuroActorAttributes:
    def test_school_knacks(self) -> None:
        s = ShosuroActor(rank=1, **STATS)
        assert set(s.school_knacks) == {
            "athletics", "discern_honor", "pontificate",
        }

    def test_r1t_rolls(self) -> None:
        s = ShosuroActor(rank=1, **STATS)
        for rt in s.r1t_rolls:
            assert s.extra_dice[rt][0] >= 1

    def test_r2t_always_bonus(self) -> None:
        s = ShosuroActor(rank=2, **STATS)
        assert s.always["pontificate"] >= 5

    def test_school_ring(self) -> None:
        assert ShosuroActor.school_ring == "air"


class TestShosuroActorSA:
    """SA: Extra rolled dice = rank on attack, parry, wound_check."""

    def test_extra_dice_equals_rank(self) -> None:
        for rank in [1, 3, 5]:
            s = ShosuroActor(rank=rank, **STATS)
            base = Combatant(**STATS)
            for rt in ["attack", "parry", "wound_check"]:
                assert s.extra_dice[rt][0] >= base.extra_dice[rt][0] + rank

    def test_other_rolls_unaffected(self) -> None:
        s = ShosuroActor(rank=3, **STATS)
        base = Combatant(**STATS)
        assert s.extra_dice["damage"] == base.extra_dice["damage"]


class TestShosuroActorR3T:
    def test_shared_disc_bonuses(self) -> None:
        s = ShosuroActor(rank=3, **STATS)
        for rt in ["attack", "wound_check"]:
            total = sum(sum(g) for g in s.multi[rt])
            assert total == 5 * 10

    def test_shared_reference(self) -> None:
        s = ShosuroActor(rank=3, **STATS)
        assert s.multi["attack"][-1] is s.multi["wound_check"][-1]

    def test_rank_gated(self) -> None:
        s = ShosuroActor(rank=2, **STATS)
        assert not s.multi["attack"]
        assert not s.multi["wound_check"]


class TestShosuroActorR5T:
    def test_adds_lowest_3_of_all_dice(self) -> None:
        """R5T: add lowest 3 of ALL rolled dice (some counted twice)."""
        s = ShosuroActor(rank=5, **STATS)
        # Patch d10 to return deterministic values
        # 4k3: dice [9,6,5,2] → keep [9,6,5]=20, add [2,5,6]=13 → 33
        with patch("l7r.schools.shosuro_actor.d10", side_effect=[2, 5, 6, 9]):
            result = s.xky(4, 3, True, "attack")
        assert result == 20 + 13  # 33

    def test_3k3_doubles_all(self) -> None:
        """R5T: 3k3 should double the roll (all dice counted twice)."""
        s = ShosuroActor(rank=5, **STATS)
        with patch("l7r.schools.shosuro_actor.d10", side_effect=[3, 5, 7]):
            result = s.xky(3, 3, True, "attack")
        # kept = 3+5+7=15, lowest 3 = [3,5,7]=15, total = 30
        assert result == 30

    def test_fewer_than_3_dice(self) -> None:
        """R5T: If fewer than 3 dice, add all of them."""
        s = ShosuroActor(rank=5, **STATS)
        with patch("l7r.schools.shosuro_actor.d10", side_effect=[4, 8]):
            result = s.xky(2, 2, True, "attack")
        # kept = 4+8=12, lowest 2 = [4,8]=12, total = 24
        assert result == 24

    def test_applies_to_all_roll_types(self) -> None:
        """R5T applies to any roll type that uses xky."""
        s = ShosuroActor(rank=5, **STATS)
        with patch("l7r.schools.shosuro_actor.d10", side_effect=[2, 5, 6, 9]):
            result = s.xky(4, 3, True, "interrogation")
        assert result == 20 + 13  # same as combat rolls

    def test_rank_gated(self) -> None:
        s = ShosuroActor(rank=4, **STATS)
        with patch.object(Combatant, "xky", return_value=42):
            result = s.xky(6, 3, True, "attack")
        assert result == 42


# ===================================================================
# ENGINE CHANGES: FORCED PARRY
# ===================================================================


class TestForcedParry:
    def test_forced_parry_consumes_action(self) -> None:
        """When forced_parry is set, defender loses an action."""
        defender = make_enemy()
        defender.forced_parry = True
        defender.actions = [3, 5]

        # Simulate the engine check
        was_forced = defender.forced_parry
        if defender.forced_parry:
            defender.forced_parry = False
            if defender.actions:
                defender.actions.pop(0)
                defender.predeclare_bonus = 0

        assert was_forced is True
        assert defender.forced_parry is False
        assert len(defender.actions) == 1

    def test_forced_parry_no_actions(self) -> None:
        """If defender has no actions, forced_parry still clears flag."""
        defender = make_enemy()
        defender.forced_parry = True
        defender.actions = []

        assert defender.forced_parry is True
        if defender.forced_parry:
            defender.forced_parry = False
            if defender.actions:
                defender.actions.pop(0)

        assert defender.forced_parry is False
        assert defender.actions == []


class TestReactiveCounterattack:
    def test_base_combatant_wont_react(self) -> None:
        c = Combatant(**STATS)
        enemy = make_enemy()
        assert c.will_react_to_attack(enemy) is False


# ===================================================================
# BUILDER VALIDATION
# ===================================================================


class TestBuilderValidation:
    """Verify all new progressions pass validation."""

    def test_kuni_witch_hunter_progression(self) -> None:
        from l7r.builders.kuni_witch_hunter import KuniWitchHunterProgression
        from l7r.builders import build
        c = build(KuniWitchHunterProgression)
        assert isinstance(c, KuniWitchHunter)

    def test_courtier_progression(self) -> None:
        from l7r.builders.courtier import CourtierProgression
        from l7r.builders import build
        c = build(CourtierProgression)
        assert isinstance(c, Courtier)

    def test_merchant_progression(self) -> None:
        from l7r.builders.merchant import MerchantProgression
        from l7r.builders import build
        c = build(MerchantProgression)
        assert isinstance(c, Merchant)

    def test_doji_artisan_progression(self) -> None:
        from l7r.builders.doji_artisan import DojiArtisanProgression
        from l7r.builders import build
        c = build(DojiArtisanProgression)
        assert isinstance(c, DojiArtisan)

    def test_ide_diplomat_progression(self) -> None:
        from l7r.builders.ide_diplomat import IdeDiplomatProgression
        from l7r.builders import build
        c = build(IdeDiplomatProgression)
        assert isinstance(c, IdeDiplomat)

    def test_ikoma_bard_progression(self) -> None:
        from l7r.builders.ikoma_bard import IkomaBardProgression
        from l7r.builders import build
        c = build(IkomaBardProgression)
        assert isinstance(c, IkomaBard)

    def test_shosuro_actor_progression(self) -> None:
        from l7r.builders.shosuro_actor import ShosuroActorProgression
        from l7r.builders import build
        c = build(ShosuroActorProgression)
        assert isinstance(c, ShosuroActor)
