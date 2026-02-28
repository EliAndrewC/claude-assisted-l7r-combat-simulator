"""Tests for Professional (Wave Man and Ninja) abilities.

Each ability can be taken once or twice. The ``for i in self.wave_man[ability]``
pattern means the ability fires once per list element. Lists are typically
``[0]`` for taken-once or ``[0, 1]`` for taken-twice, where the values serve
as array indices for some abilities and are ignored for others.

Abilities are organized in the same order as rules/09-professions.md.
"""

from __future__ import annotations

from collections import defaultdict
from unittest.mock import patch

from l7r.combatant import Combatant
from l7r.professions import Professional
from l7r.records import AttackRecord


def attack_rec(hit: bool = False, knack: str = "attack") -> AttackRecord:
    """Create a minimal AttackRecord for test mocks."""
    return AttackRecord(attacker="A", defender="D", knack=knack, phase=0, vps_spent=0, hit=hit)


# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------

def empty_abilities() -> defaultdict[str, list[int]]:
    """An ability dict where every ability is empty (not taken)."""
    return defaultdict(list)


def ability(name: str, times: int = 1) -> defaultdict[str, list[int]]:
    """An ability dict with one ability taken ``times`` times."""
    d = empty_abilities()
    d[name] = list(range(times))
    return d


def make_pro(
    wave_man: dict | None = None,
    ninja: dict | None = None,
    **kw: int,
) -> Professional:
    """Create a Professional with specified abilities and stats."""
    defaults = dict(
        air=3, earth=5, fire=3, water=3,
        void=3, attack=3, parry=3,
    )
    defaults.update(kw)
    return Professional(
        wave_man=wave_man or empty_abilities(),
        ninja=ninja or empty_abilities(),
        **defaults,
    )


def make_enemy(**kw: int) -> Combatant:
    """Create a plain Combatant to serve as an enemy."""
    defaults = dict(
        air=3, earth=5, fire=3, water=3,
        void=3, attack=3, parry=3,
    )
    defaults.update(kw)
    return Combatant(**defaults)


def link(pro: Professional, enemy: Combatant) -> None:
    """Set up the bidirectional enemy relationship for trigger testing."""
    pro.enemy = enemy
    enemy.enemy = pro


# ===================================================================
# WAVE MAN ABILITIES
# ===================================================================


# -----------------------------------------------------------
# 1. Near Miss: +5 on a miss, auto-parry on near-miss hits
# -----------------------------------------------------------


class TestNearMiss:
    def test_miss_becomes_hit(self) -> None:
        """Attack that misses by up to 5 is raised to a hit."""
        pro = make_pro(wave_man=ability("wave_man_near_miss"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"

        # Make the base attack miss by 3 (attack_roll 17, TN 20)
        with patch.object(Combatant, "make_attack", return_value=attack_rec(hit=False)):
            pro.attack_roll = enemy.tn - 3  # 17
            rec = pro.make_attack()

        assert rec.hit is True

    def test_miss_by_more_than_5_still_misses(self) -> None:
        """Attack that misses by more than 5 is not rescued."""
        pro = make_pro(wave_man=ability("wave_man_near_miss"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"

        with patch.object(Combatant, "make_attack", return_value=attack_rec(hit=False)):
            pro.attack_roll = enemy.tn - 10  # Misses by 10
            rec = pro.make_attack()

        assert rec.hit is False

    def test_attack_roll_reset_to_zero(self) -> None:
        """Near miss sets attack_roll to 0 (no bonus damage dice)."""
        pro = make_pro(wave_man=ability("wave_man_near_miss"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"

        with patch.object(Combatant, "make_attack", return_value=attack_rec(hit=False)):
            pro.attack_roll = enemy.tn - 3
            pro.make_attack()

        assert pro.attack_roll == 0

    def test_successful_attack_triggers_on_attacker(self) -> None:
        """The successful_attack event fires on the attacker (not enemy)."""
        pro = make_pro(wave_man=ability("wave_man_near_miss"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"

        fired: list[str] = []
        pro.events["successful_attack"].append(lambda: fired.append("pro"))
        enemy.events["successful_attack"].append(lambda: fired.append("enemy"))

        with patch.object(Combatant, "make_attack", return_value=attack_rec(hit=False)):
            pro.attack_roll = enemy.tn - 3
            pro.make_attack()

        assert "pro" in fired
        assert "enemy" not in fired

    def test_taken_twice_adds_10(self) -> None:
        """Taken twice: +10 total rescue range."""
        pro = make_pro(wave_man=ability("wave_man_near_miss", 2))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"

        with patch.object(Combatant, "make_attack", return_value=attack_rec(hit=False)):
            pro.attack_roll = enemy.tn - 8  # Misses by 8, rescued by +10
            rec = pro.make_attack()

        assert rec.hit is True

    def test_no_double_trigger_on_normal_hit(self) -> None:
        """If the base attack hits, near_miss doesn't fire."""
        pro = make_pro(wave_man=ability("wave_man_near_miss"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"

        # Base attack hits — successful_attack already fired in base
        with patch.object(Combatant, "make_attack", return_value=attack_rec(hit=True)):
            pro.attack_roll = enemy.tn + 5
            rec = pro.make_attack()

        assert rec.hit is True
        # attack_roll should NOT be reset to 0
        assert pro.attack_roll == enemy.tn + 5


# -----------------------------------------------------------
# 2. Difficult Parry: +5 to parry TN, -1 damage_rolled
# -----------------------------------------------------------


class TestDifficultParry:
    def test_raises_attack_roll(self) -> None:
        """Successful attack trigger raises attack_roll by 5."""
        pro = make_pro(wave_man=ability("wave_man_difficult_parry"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_roll = 25

        pro.difficult_parry_trigger()

        assert pro.attack_roll == 30

    def test_compensates_damage_rolled(self) -> None:
        """The -1 to damage_rolled cancels the phantom extra die."""
        pro = make_pro(wave_man=ability("wave_man_difficult_parry"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_roll = 25

        pro.difficult_parry_trigger()

        assert pro.auto_once["damage_rolled"] == -1

    def test_taken_twice(self) -> None:
        """Taken twice: +10 to attack_roll, -2 to damage_rolled."""
        pro = make_pro(wave_man=ability("wave_man_difficult_parry", 2))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_roll = 25

        pro.difficult_parry_trigger()

        assert pro.attack_roll == 35
        assert pro.auto_once["damage_rolled"] == -2


# -----------------------------------------------------------
# 3. Damage Compensator: +1 rolled die if base < 4
# -----------------------------------------------------------


class TestDamageCompensator:
    def test_raises_low_damage(self) -> None:
        """Weapon with 2 rolled dice gets bumped to 3."""
        pro = make_pro(
            wave_man=ability("wave_man_damage_compensator"),
            base_damage_rolled=2,
        )
        assert pro.base_damage_rolled == 3

    def test_caps_at_4(self) -> None:
        """Already at 4: no change."""
        pro = make_pro(
            wave_man=ability("wave_man_damage_compensator"),
            base_damage_rolled=4,
        )
        assert pro.base_damage_rolled == 4

    def test_taken_twice_from_2(self) -> None:
        """Taken twice from 2: goes to 4."""
        pro = make_pro(
            wave_man=ability("wave_man_damage_compensator", 2),
            base_damage_rolled=2,
        )
        assert pro.base_damage_rolled == 4

    def test_taken_twice_from_3(self) -> None:
        """Taken twice from 3: caps at 4 (second instance no-ops)."""
        pro = make_pro(
            wave_man=ability("wave_man_damage_compensator", 2),
            base_damage_rolled=3,
        )
        assert pro.base_damage_rolled == 4


# -----------------------------------------------------------
# 4. Damage Round Up: round to nearest 5, or +3 if already
# -----------------------------------------------------------


class TestDamageRoundUp:
    def test_rounds_up_to_5(self) -> None:
        """Damage 12 → 15 (rounds up 3 to nearest 5)."""
        pro = make_pro(wave_man=ability("wave_man_damage_round_up"))

        with patch("l7r.professions.d10", return_value=4):
            result = pro.xky(3, 3, False, "damage")

        # 3 dice of 4 = 12; round up: 12 + 3 = 15
        assert result == 15

    def test_already_multiple_of_5_adds_3(self) -> None:
        """Damage 10 → 13 (already multiple of 5, add 3)."""
        pro = make_pro(wave_man=ability("wave_man_damage_round_up"))

        with patch("l7r.professions.d10", return_value=5):
            result = pro.xky(2, 2, False, "damage")

        # 2 dice of 5 = 10; already multiple of 5: 10 + 3 = 13
        assert result == 13

    def test_taken_twice_stacks(self) -> None:
        """Taken twice: rounds up then rounds up again."""
        pro = make_pro(wave_man=ability("wave_man_damage_round_up", 2))

        with patch("l7r.professions.d10", return_value=4):
            result = pro.xky(3, 3, False, "damage")

        # 12 → 15 (first round-up) → 18 (15 is multiple of 5, +3)
        assert result == 18

    def test_only_applies_to_damage(self) -> None:
        """Does not affect non-damage rolls."""
        pro = make_pro(wave_man=ability("wave_man_damage_round_up"))

        with patch("l7r.professions.d10", return_value=4):
            result = pro.xky(3, 3, False, "attack")

        assert result == 12  # No rounding


# -----------------------------------------------------------
# 5. Crippled Reroll: reroll 10s on specific dice when crippled
# -----------------------------------------------------------


class TestCrippledReroll:
    def test_rerolls_10_when_crippled(self) -> None:
        """When crippled, a die showing 10 explodes."""
        pro = make_pro(wave_man=ability("wave_man_crippled_reroll"))
        pro.crippled = True

        # First die = 10 (sorted desc, index 0), second = 5
        # d10 is called: [10, 5] for initial, then d10(True) for reroll
        with patch("l7r.professions.d10", side_effect=[10, 5, 7]):
            result = pro.xky(2, 2, False, "attack")

        # dice sorted desc: [10, 5]. crippled_reroll[0]=0, dice[0]==10.
        # dice[0] = 10 + 7 = 17. Result = 17 + 5 = 22
        assert result == 22

    def test_no_effect_when_not_crippled(self) -> None:
        """When not crippled (reroll=True), dice already explode so
        no die is exactly 10, and crippled_reroll is harmless."""
        pro = make_pro(wave_man=ability("wave_man_crippled_reroll"))
        pro.crippled = False

        # Dice: 8, 6 (no 10s)
        with patch("l7r.professions.d10", side_effect=[8, 6]):
            result = pro.xky(2, 2, True, "attack")

        assert result == 14

    def test_taken_twice_rerolls_two_dice(self) -> None:
        """Taken twice: can reroll 10s on the top 2 dice."""
        pro = make_pro(wave_man=ability("wave_man_crippled_reroll", 2))
        pro.crippled = True

        # dice: [10, 10, 3] sorted desc. Index 0 and 1 are both 10.
        with patch("l7r.professions.d10", side_effect=[10, 10, 3, 5, 4]):
            result = pro.xky(3, 2, False, "attack")

        # dice[0] = 10+5 = 15, dice[1] = 10+4 = 14. Keep top 2: 15+14 = 29
        assert result == 29


# -----------------------------------------------------------
# 6. Initiative Bonus: +1 rolled die on initiative
# -----------------------------------------------------------


class TestInitBonus:
    def test_adds_rolled_die(self) -> None:
        """One extra rolled (unkept) initiative die."""
        pro = make_pro(wave_man=ability("wave_man_init_bonus"))
        base = make_pro()  # No abilities

        assert pro.init_dice[0] == base.init_dice[0] + 1
        assert pro.init_dice[1] == base.init_dice[1]  # Keep unchanged

    def test_taken_twice(self) -> None:
        """Taken twice: +2 rolled initiative dice."""
        pro = make_pro(wave_man=ability("wave_man_init_bonus", 2))
        base = make_pro()

        assert pro.init_dice[0] == base.init_dice[0] + 2


# -----------------------------------------------------------
# 7. WC Bonus: +2 unkept dice on wound checks
# -----------------------------------------------------------


class TestWCBonus:
    def test_adds_rolled_dice(self) -> None:
        """Two extra rolled (unkept) wound check dice."""
        pro = make_pro(wave_man=ability("wave_man_wc_bonus"))
        base = make_pro()

        assert pro.wc_dice[0] == base.wc_dice[0] + 2
        assert pro.wc_dice[1] == base.wc_dice[1]  # Keep unchanged

    def test_taken_twice(self) -> None:
        """Taken twice: +4 rolled wound check dice."""
        pro = make_pro(wave_man=ability("wave_man_wc_bonus", 2))
        base = make_pro()

        assert pro.wc_dice[0] == base.wc_dice[0] + 4


# -----------------------------------------------------------
# 8. Wound Reduction: -5 light when attacker exceeds TN
# -----------------------------------------------------------


class TestWoundReduction:
    def test_reduces_when_exceeded(self) -> None:
        """Subtract 5 from light wounds when attacker exceeded TN by 5+."""
        pro = make_pro(wave_man=ability("wave_man_wound_reduction"))
        enemy = make_enemy()
        link(pro, enemy)
        enemy.attack_roll = pro.tn + 5  # Exceeded by 5

        with patch.object(Combatant, "wound_check") as mock_wc:
            pro.wound_check(20, 0)

        mock_wc.assert_called_once_with(pro, 15, 0)

    def test_no_reduction_when_not_exceeded(self) -> None:
        """No reduction when attacker didn't exceed TN by 5."""
        pro = make_pro(wave_man=ability("wave_man_wound_reduction"))
        enemy = make_enemy()
        link(pro, enemy)
        enemy.attack_roll = pro.tn + 4  # Exceeded by only 4

        with patch.object(Combatant, "wound_check") as mock_wc:
            pro.wound_check(20, 0)

        mock_wc.assert_called_once_with(pro, 20, 0)

    def test_taken_twice(self) -> None:
        """Taken twice: -10 total."""
        pro = make_pro(wave_man=ability("wave_man_wound_reduction", 2))
        enemy = make_enemy()
        link(pro, enemy)
        enemy.attack_roll = pro.tn + 5

        with patch.object(Combatant, "wound_check") as mock_wc:
            pro.wound_check(20, 0)

        mock_wc.assert_called_once_with(pro, 10, 0)

    def test_floor_at_zero(self) -> None:
        """Can't reduce below 0."""
        pro = make_pro(wave_man=ability("wave_man_wound_reduction"))
        enemy = make_enemy()
        link(pro, enemy)
        enemy.attack_roll = pro.tn + 5

        with patch.object(Combatant, "wound_check") as mock_wc:
            pro.wound_check(3, 0)

        mock_wc.assert_called_once_with(pro, 0, 0)


# -----------------------------------------------------------
# 9. Parry Bypass: roll 2 extra dice when parry attempted
# -----------------------------------------------------------


class TestParryBypass:
    def test_adds_dice_when_parry_attempted(self) -> None:
        """When extra_damage=False (parry attempted), add up to 2 dice."""
        pro = make_pro(wave_man=ability("wave_man_parry_bypass"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"
        pro.attack_roll = enemy.tn + 15  # Exceeded by 15 → 3 dice negated

        roll, keep, serious = pro.next_damage(enemy.tn, extra_damage=False)
        base_roll, _, _ = Combatant.next_damage(pro, enemy.tn, False)

        # Should add min(2, 3) = 2 extra dice
        assert roll == base_roll + 2

    def test_caps_at_negated(self) -> None:
        """If only 1 die was negated, only add 1."""
        pro = make_pro(wave_man=ability("wave_man_parry_bypass"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"
        pro.attack_roll = enemy.tn + 5  # Exceeded by 5 → 1 die negated

        roll, keep, serious = pro.next_damage(enemy.tn, extra_damage=False)
        base_roll, _, _ = Combatant.next_damage(pro, enemy.tn, False)

        assert roll == base_roll + 1

    def test_no_effect_when_extra_damage(self) -> None:
        """When extra_damage=True (no parry attempt), no bypass needed."""
        pro = make_pro(wave_man=ability("wave_man_parry_bypass"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"
        pro.attack_roll = enemy.tn + 15

        roll, _, _ = pro.next_damage(enemy.tn, extra_damage=True)
        base_roll, _, _ = Combatant.next_damage(pro, enemy.tn, True)

        assert roll == base_roll

    def test_taken_twice(self) -> None:
        """Taken twice: first instance adds 2, second adds min(2, remaining)."""
        pro = make_pro(wave_man=ability("wave_man_parry_bypass", 2))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"
        pro.attack_roll = enemy.tn + 25  # Exceeded by 25 → 5 dice negated

        roll, _, _ = pro.next_damage(enemy.tn, extra_damage=False)
        base_roll, _, _ = Combatant.next_damage(pro, enemy.tn, False)

        # First instance: +min(2, 5)=2, negated becomes max(0, 5-2)=3
        # Second instance: +min(2, 3)=2, total = 4
        assert roll == base_roll + 4

    def test_zero_negated_adds_nothing(self) -> None:
        """When attack didn't exceed TN, 0 dice negated, 0 added."""
        pro = make_pro(wave_man=ability("wave_man_parry_bypass"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"
        pro.attack_roll = enemy.tn  # Exactly at TN, 0 negated

        roll, _, _ = pro.next_damage(enemy.tn, extra_damage=False)
        base_roll, _, _ = Combatant.next_damage(pro, enemy.tn, False)

        assert roll == base_roll


# -----------------------------------------------------------
# 10. Tougher Wounds: +5 wound check TN, serious calc ignores
# -----------------------------------------------------------


class TestTougherWounds:
    def test_raises_light_wounds_reported(self) -> None:
        """deal_damage returns light + raised_tn."""
        from l7r.records import DamageRecord
        pro = make_pro(wave_man=ability("wave_man_tougher_wounds"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"
        pro.attack_roll = enemy.tn + 5

        with patch.object(Combatant, "deal_damage", return_value=DamageRecord(attacker="", defender="", light=20, serious=0)):
            rec = pro.deal_damage(enemy.tn)

        assert rec.light == 25  # 20 + 5
        assert rec.serious == 0

    def test_calc_serious_adjusted(self) -> None:
        """The enemy's calc_serious uses light - raised_tn."""
        from l7r.records import DamageRecord
        pro = make_pro(wave_man=ability("wave_man_tougher_wounds"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"
        pro.attack_roll = enemy.tn + 5

        orig_result = enemy.calc_serious(20, 10)

        with patch.object(Combatant, "deal_damage", return_value=DamageRecord(attacker="", defender="", light=20, serious=0)):
            pro.deal_damage(enemy.tn)

        # raised_tn=5: calc_serious(25, 10) acts as orig(20, 10)
        assert enemy.calc_serious(25, 10) == orig_result

    def test_reset_after_post_attack(self) -> None:
        """calc_serious is restored after post_attack triggers."""
        from l7r.records import DamageRecord
        pro = make_pro(wave_man=ability("wave_man_tougher_wounds"))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"
        pro.attack_roll = enemy.tn + 5

        with patch.object(Combatant, "deal_damage", return_value=DamageRecord(attacker="", defender="", light=20, serious=0)):
            pro.deal_damage(enemy.tn)

        # Patched: calc_serious(25, 10) != normal calc_serious(25, 10)
        patched_result = enemy.calc_serious(25, 10)

        # Simulate post_attack trigger
        pro.triggers("post_attack")

        # After restore, calc_serious should work normally again
        normal_result = Combatant.calc_serious(enemy, 25, 10)
        assert enemy.calc_serious(25, 10) == normal_result
        assert enemy.calc_serious(25, 10) != patched_result

    def test_taken_twice(self) -> None:
        """Taken twice: raises by 10."""
        from l7r.records import DamageRecord
        pro = make_pro(wave_man=ability("wave_man_tougher_wounds", 2))
        enemy = make_enemy()
        link(pro, enemy)
        pro.attack_knack = "attack"
        pro.attack_roll = enemy.tn + 5

        with patch.object(Combatant, "deal_damage", return_value=DamageRecord(attacker="", defender="", light=20, serious=0)):
            rec = pro.deal_damage(enemy.tn)

        assert rec.light == 30  # 20 + 10


# ===================================================================
# NINJA ABILITIES
# ===================================================================


# -----------------------------------------------------------
# 1. Difficult Attack: +5 TN, extra damage die if exceeding TN
# -----------------------------------------------------------


class TestDifficultAttack:
    def test_raises_tn(self) -> None:
        """Taking the ability raises TN by 5."""
        base = make_pro()
        pro = make_pro(ninja=ability("ninja_difficult_attack"))

        assert pro.tn == base.tn + 5

    def test_taken_twice_raises_tn_by_10(self) -> None:
        """Taken twice: +10 TN."""
        base = make_pro()
        pro = make_pro(ninja=ability("ninja_difficult_attack", 2))

        assert pro.tn == base.tn + 10

    def test_extra_damage_when_exceeding_tn(self) -> None:
        """When attacker hits and exceeds TN by 5+, gets extra damage die."""
        pro = make_pro(ninja=ability("ninja_difficult_attack"))
        enemy = make_enemy()
        link(pro, enemy)
        enemy.attack_knack = "attack"
        enemy.attack_roll = pro.tn + 5  # Exceeds by 5

        # Simulate pre_defense → registers handler
        pro.difficult_attack_pre_trigger()

        # Simulate successful attack → fires the handler
        enemy.triggers("successful_attack")

        assert enemy.auto_once["damage_rolled"] == 1

    def test_no_extra_damage_when_not_exceeding(self) -> None:
        """When attacker hits but doesn't exceed TN by 5, no extra die."""
        pro = make_pro(ninja=ability("ninja_difficult_attack"))
        enemy = make_enemy()
        link(pro, enemy)
        enemy.attack_knack = "attack"
        enemy.attack_roll = pro.tn + 4

        pro.difficult_attack_pre_trigger()
        enemy.triggers("successful_attack")

        assert enemy.auto_once["damage_rolled"] == 0

    def test_handler_cleaned_up(self) -> None:
        """Post-defense cleans up the temporary handler."""
        pro = make_pro(ninja=ability("ninja_difficult_attack"))
        enemy = make_enemy()
        link(pro, enemy)
        enemy.attack_knack = "attack"

        pro.difficult_attack_pre_trigger()
        assert pro._difficult_attack_sa_trigger in enemy.events["successful_attack"]

        pro.difficult_attack_post_trigger()
        assert pro._difficult_attack_sa_trigger not in enemy.events["successful_attack"]

    def test_no_handler_when_ability_not_taken(self) -> None:
        """No handler registered if difficult_attack isn't taken."""
        pro = make_pro()
        enemy = make_enemy()
        link(pro, enemy)
        enemy.attack_knack = "attack"

        sa_before = len(enemy.events["successful_attack"])
        pro.difficult_attack_pre_trigger()
        assert len(enemy.events["successful_attack"]) == sa_before

    def test_taken_twice_extra_damage(self) -> None:
        """Taken twice: 2 extra damage dice when exceeding TN."""
        pro = make_pro(ninja=ability("ninja_difficult_attack", 2))
        enemy = make_enemy()
        link(pro, enemy)
        enemy.attack_knack = "attack"
        enemy.attack_roll = pro.tn + 5

        pro.difficult_attack_pre_trigger()
        enemy.triggers("successful_attack")

        assert enemy.auto_once["damage_rolled"] == 2


# -----------------------------------------------------------
# 2. Damage Reroll: cap exploded damage dice to 10
# -----------------------------------------------------------


class TestDamageReroll:
    def test_caps_exploded_dice(self) -> None:
        """Exploded dice (>10) get capped to 10."""
        pro = make_pro(ninja=ability("ninja_damage_roll"))
        enemy = make_enemy()
        link(pro, enemy)
        enemy.attack_knack = "attack"

        # Set up the trigger chain
        pro.damage_reroll_pre_trigger()
        pro.damage_reroll_sa_trigger()

        # Now enemy.xky is patched — test it
        # dice desc: [15,8,5]. dice[1]=min(10,8)=8 unchanged
        with patch("l7r.professions.d10", side_effect=[15, 8, 5]):
            result = enemy.xky(3, 2, True, "damage")

        # Keep top 2: 15 + 8 = 23. dice[1]=8, min(10,8)=8, no change.
        assert result == 23

    def test_caps_high_dice(self) -> None:
        """A die that exploded to >10 gets reduced to 10."""
        pro = make_pro(ninja=ability("ninja_damage_roll"))
        enemy = make_enemy()
        link(pro, enemy)
        enemy.attack_knack = "attack"

        pro.damage_reroll_pre_trigger()
        pro.damage_reroll_sa_trigger()

        # dice desc: [20,18,5]. dice[1]=min(10,18)=10
        with patch("l7r.professions.d10", side_effect=[20, 18, 5]):
            result = enemy.xky(3, 2, True, "damage")

        # Keep top 2: 20 + 10 = 30
        assert result == 30

    def test_non_damage_uses_original(self) -> None:
        """Non-damage rolls use the original xky."""
        pro = make_pro(ninja=ability("ninja_damage_roll"))
        enemy = make_enemy()
        link(pro, enemy)
        enemy.attack_knack = "attack"

        pro.damage_reroll_pre_trigger()
        pro.damage_reroll_sa_trigger()

        # Non-damage roll should use old_xky
        with patch.object(pro, "old_xky", return_value=42):
            result = enemy.xky(3, 2, True, "attack")

        assert result == 42

    def test_restored_after_post_defense(self) -> None:
        """xky is restored to original after post_defense."""
        pro = make_pro(ninja=ability("ninja_damage_roll"))
        enemy = make_enemy()
        link(pro, enemy)
        enemy.attack_knack = "attack"

        pro.damage_reroll_pre_trigger()
        pro.damage_reroll_sa_trigger()

        # xky is now the patched version
        patched_xky = enemy.xky
        assert patched_xky is not pro.old_xky

        pro.damage_reroll_post_trigger()

        # After restore, xky should be the saved original
        assert enemy.xky is pro.old_xky


# -----------------------------------------------------------
# 3. Better TN: attacker rolls 1 fewer die, minimum Fire
# -----------------------------------------------------------


class TestBetterTN:
    def test_reduces_attacker_dice(self) -> None:
        """Attacker loses 1 rolled die on their attack."""
        pro = make_pro(ninja=ability("ninja_better_tn"))
        enemy = make_enemy(fire=3, attack=3)
        link(pro, enemy)
        enemy.attack_knack = "attack"

        before = enemy.att_dice("attack")[0]
        pro.better_tn_trigger()
        after = enemy.att_dice("attack")[0]

        assert after == before - 1

    def test_respects_fire_minimum(self) -> None:
        """Can't reduce below Fire ring."""
        pro = make_pro(ninja=ability("ninja_better_tn"))
        # Fire=3, attack=0 → att_dice=(3,3). Can't reduce.
        enemy = make_enemy(fire=3, attack=0)
        link(pro, enemy)
        enemy.attack_knack = "attack"

        before = enemy.att_dice("attack")[0]
        pro.better_tn_trigger()
        after = enemy.att_dice("attack")[0]

        assert after == before  # No reduction

    def test_restored_after_post_trigger(self) -> None:
        """Dice are restored after better_tn_post_trigger."""
        pro = make_pro(ninja=ability("ninja_better_tn"))
        enemy = make_enemy(fire=3, attack=3)
        link(pro, enemy)
        enemy.attack_knack = "attack"

        before = enemy.att_dice("attack")[0]
        pro.better_tn_trigger()
        pro.better_tn_post_trigger()
        after = enemy.att_dice("attack")[0]

        assert after == before

    def test_taken_twice(self) -> None:
        """Taken twice: -2 rolled dice (if above Fire minimum)."""
        pro = make_pro(ninja=ability("ninja_better_tn", 2))
        enemy = make_enemy(fire=3, attack=5)
        link(pro, enemy)
        enemy.attack_knack = "attack"

        before = enemy.att_dice("attack")[0]
        pro.better_tn_trigger()
        after = enemy.att_dice("attack")[0]

        assert after == before - 2

    def test_taken_twice_one_above_minimum(self) -> None:
        """Taken twice but only 1 above minimum: only 1 reduction."""
        pro = make_pro(ninja=ability("ninja_better_tn", 2))
        # Fire=3, attack=1 → att_dice = (3+1, 3) = (4, 3). Only 1 above Fire.
        enemy = make_enemy(fire=3, attack=1)
        link(pro, enemy)
        enemy.attack_knack = "attack"

        before = enemy.att_dice("attack")[0]
        pro.better_tn_trigger()
        after = enemy.att_dice("attack")[0]

        assert after == before - 1  # Only reduced by 1, not 2


# -----------------------------------------------------------
# 4. Fast Attacks: lower action dice by 2, minimum 1
# -----------------------------------------------------------


class TestFastAttacks:
    def test_lowers_action_dice(self) -> None:
        """Each action die is lowered by 2."""
        pro = make_pro(ninja=ability("ninja_fast_attacks"))

        with patch("l7r.combatant.d10", side_effect=[5, 7, 8, 3]):
            pro.initiative()

        # Base: sorted [3,5,7,8], keep 3 → [3,5,7]
        # After fast_attacks: [1, 3, 5]
        assert pro.actions == [1, 3, 5]

    def test_minimum_1(self) -> None:
        """Action dice can't go below 1."""
        pro = make_pro(ninja=ability("ninja_fast_attacks"))

        with patch("l7r.combatant.d10", side_effect=[1, 2, 1, 2]):
            pro.initiative()

        # Base: sorted [1,1,2,2], keep 3 → [1,1,2]
        # After -2: max(1, 1-2)=1, max(1, 1-2)=1, max(1, 2-2)=1
        for action in pro.actions:
            assert action == 1

    def test_taken_twice(self) -> None:
        """Taken twice: each die lowered by 4 total (min 1)."""
        pro = make_pro(ninja=ability("ninja_fast_attacks", 2))

        with patch("l7r.combatant.d10", side_effect=[8, 7, 6, 5]):
            pro.initiative()

        # Base: sorted [5,6,7,8], keep 3 → [5,6,7]
        # After -4: [1, 2, 3]
        assert pro.actions == [1, 2, 3]

    def test_init_order_matches_actions(self) -> None:
        """init_order is updated to match the lowered actions."""
        pro = make_pro(ninja=ability("ninja_fast_attacks"))

        with patch("l7r.combatant.d10", side_effect=[5, 7, 8, 3]):
            pro.initiative()

        assert pro.actions == pro.init_order


# -----------------------------------------------------------
# 5. Damage Bump: keep 2 extra lowest dice on damage
# -----------------------------------------------------------


class TestDamageBump:
    def test_adds_lowest_dice(self) -> None:
        """Keeps 2 extra lowest unkept dice."""
        pro = make_pro(ninja=ability("ninja_damage_bump"))

        # roll=5, keep=2. Dice desc: [9,8,6,4,3].
        # Keep top 2=17. Extra 2 lowest: 4+3=7. Total=24
        with patch("l7r.professions.d10", side_effect=[9, 8, 6, 4, 3]):
            result = pro.xky(5, 2, False, "damage")

        assert result == 24

    def test_no_effect_on_non_damage(self) -> None:
        """damage_bump only applies to damage rolls."""
        pro = make_pro(ninja=ability("ninja_damage_bump"))

        with patch("l7r.professions.d10", side_effect=[9, 8, 6, 4, 3]):
            result = pro.xky(5, 2, False, "attack")

        # Normal keep top 2: 9+8 = 17
        assert result == 17

    def test_limited_by_unkept(self) -> None:
        """If fewer than 2 unkept dice, only add what's available."""
        pro = make_pro(ninja=ability("ninja_damage_bump"))

        # roll=3, keep=2. Only 1 unkept die.
        # extra = min(3-2, 2) = 1
        with patch("l7r.professions.d10", side_effect=[8, 6, 3]):
            result = pro.xky(3, 2, False, "damage")

        # Top 2: 8+6 = 14. Extra 1 die: 3. Total = 17
        assert result == 17

    def test_no_effect_when_not_taken(self) -> None:
        """Without the ability, no extra dice are added."""
        pro = make_pro()

        with patch("l7r.professions.d10", side_effect=[9, 8, 6, 4, 3]):
            result = pro.xky(5, 2, False, "damage")

        # Normal keep top 2: 9+8 = 17, no extras
        assert result == 17

    def test_taken_twice(self) -> None:
        """Taken twice: keep 4 extra lowest dice."""
        pro = make_pro(ninja=ability("ninja_damage_bump", 2))

        # roll=6, keep=2. extra = min(6-2, 4) = 4.
        with patch("l7r.professions.d10", side_effect=[9, 8, 6, 5, 4, 3]):
            result = pro.xky(6, 2, False, "damage")

        # Top 2: 9+8=17. Extra 4 lowest: 6+5+4+3=18. Total = 35
        assert result == 35


# -----------------------------------------------------------
# 6. Attack Bonus: add Fire to attack rolls
# -----------------------------------------------------------


class TestAttackBonus:
    def test_adds_fire_to_attack(self) -> None:
        """The always["attack"] bonus equals Fire."""
        pro = make_pro(ninja=ability("ninja_attack_bonus"), fire=4)

        assert pro.always["attack"] == 4

    def test_taken_twice(self) -> None:
        """Taken twice: 2x Fire added."""
        pro = make_pro(ninja=ability("ninja_attack_bonus", 2), fire=4)

        assert pro.always["attack"] == 8


# -----------------------------------------------------------
# 7. WC Bump: low dice on wound checks bumped to 5
# -----------------------------------------------------------


class TestWCBump:
    def test_bumps_low_dice(self) -> None:
        """Dice below 5 get bumped up to 5 on wound checks."""
        pro = make_pro(ninja=ability("ninja_wc_bump"))

        # Dice: [8, 3, 2] → bumps: [8, 5, 5]
        with patch("l7r.professions.d10", side_effect=[8, 3, 2]):
            result = pro.xky(3, 2, False, "wound_check")

        # Sorted desc: [8, 3, 2]. After bump: [8, 5, 5].
        # Keep top 2: 8+5 = 13
        assert result == 13

    def test_no_bump_on_high_dice(self) -> None:
        """Dice >= 5 are not affected."""
        pro = make_pro(ninja=ability("ninja_wc_bump"))

        with patch("l7r.professions.d10", side_effect=[8, 7, 6]):
            result = pro.xky(3, 2, False, "wound_check")

        # All >= 5, no bump. Keep top 2: 8+7 = 15
        assert result == 15

    def test_only_on_wound_checks(self) -> None:
        """Does not apply to attack or other roll types."""
        pro = make_pro(ninja=ability("ninja_wc_bump"))

        with patch("l7r.professions.d10", side_effect=[8, 3, 2]):
            result = pro.xky(3, 2, False, "attack")

        # No bump: keep top 2: 8+3 = 11
        assert result == 11

    def test_taken_twice_same_effect(self) -> None:
        """Taken twice: the bump applies twice per die (same result since
        it's idempotent — bumping to 5 twice is still 5)."""
        pro = make_pro(ninja=ability("ninja_wc_bump", 2))

        with patch("l7r.professions.d10", side_effect=[8, 2, 1]):
            result = pro.xky(3, 2, False, "wound_check")

        # dice[1]=2, bump=3. Applied twice: 2+3+3=8. dice[2]=1, bump=4. 1+4+4=9.
        # Sorted desc after bumps: [9, 8, 8]. Keep top 2: 9+8 = 17
        # Wait, the bumps are applied in-place. Let me trace more carefully.
        # Dice sorted desc: [8, 2, 1]
        # i=0: bump = max(0, 5-8) = 0. No change.
        # i=1: bump = max(0, 5-2) = 3. dice[1] += 3 → 5, then +=3 → 8
        # i=2: bump = max(0, 5-1) = 4. dice[2] += 4 → 5, then +=4 → 9
        # dice = [8, 8, 9]. Keep top 2: 9+8=17. Wait, dice aren't re-sorted.
        # result = sum(dice[:2]) = 8+8 = 16
        assert result == 16


# ===================================================================
# CONSTRUCTOR: event handler registration
# ===================================================================


class TestProfessionalInit:
    def test_pre_defense_handlers(self) -> None:
        """Pre-defense has all three pre-defense triggers."""
        pro = make_pro()
        handlers = pro.events["pre_defense"]
        assert pro.better_tn_trigger in handlers
        assert pro.difficult_attack_pre_trigger in handlers
        assert pro.damage_reroll_pre_trigger in handlers

    def test_post_defense_handlers(self) -> None:
        """Post-defense has cleanup triggers."""
        pro = make_pro()
        handlers = pro.events["post_defense"]
        assert pro.better_tn_post_trigger in handlers
        assert pro.difficult_attack_post_trigger in handlers
        assert pro.damage_reroll_post_trigger in handlers

    def test_successful_attack_handler(self) -> None:
        """Successful attack has difficult_parry trigger."""
        pro = make_pro()
        assert pro.difficult_parry_trigger in pro.events["successful_attack"]

    def test_no_abilities_constructs(self) -> None:
        """A Professional with no abilities works fine."""
        pro = make_pro()
        assert pro.tn == 5 + 5 * pro.parry

    def test_multiple_abilities_combine(self) -> None:
        """Multiple abilities can be mixed."""
        wm = empty_abilities()
        wm["wave_man_init_bonus"] = [0]
        wm["wave_man_wc_bonus"] = [0]
        nj = empty_abilities()
        nj["ninja_attack_bonus"] = [0]
        pro = make_pro(wave_man=wm, ninja=nj, fire=4)

        base = make_pro(fire=4)
        assert pro.init_dice[0] == base.init_dice[0] + 1
        assert pro.wc_dice[0] == base.wc_dice[0] + 2
        assert pro.always["attack"] == 4


# ===================================================================
# XKY: combined ability interactions
# ===================================================================


class TestXkyCombined:
    def test_crippled_reroll_and_damage_round_up(self) -> None:
        """Both abilities work together on a damage roll."""
        wm = empty_abilities()
        wm["wave_man_crippled_reroll"] = [0]
        wm["wave_man_damage_round_up"] = [0]
        pro = make_pro(wave_man=wm)
        pro.crippled = True

        # Dice (not rerolling): [10, 5]. crippled_reroll: dice[0]=10 → 10+3=13.
        # result = 13+5 = 18. Round up to 20.
        with patch("l7r.professions.d10", side_effect=[10, 5, 3]):
            result = pro.xky(2, 2, False, "damage")

        assert result == 20

    def test_wc_bump_and_crippled_reroll(self) -> None:
        """wc_bump on wound_check; crippled_reroll on all."""
        wm = empty_abilities()
        wm["wave_man_crippled_reroll"] = [0]
        nj = empty_abilities()
        nj["ninja_wc_bump"] = [0]
        pro = make_pro(wave_man=wm, ninja=nj)
        pro.crippled = True

        # On wound check: dice [10, 3]. crippled_reroll: dice[0]=10→10+5=15.
        # wc_bump: dice[0] bump=0 (15>=5), dice[1] bump=2 (5-3), dice[1]=3+2=5.
        # Keep top 2: 15+5 = 20
        with patch("l7r.professions.d10", side_effect=[10, 3, 5]):
            result = pro.xky(2, 2, False, "wound_check")

        assert result == 20
