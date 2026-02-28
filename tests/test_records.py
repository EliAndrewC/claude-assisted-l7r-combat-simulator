"""Tests for structured combat records, detailed dice, and rendering."""

from unittest.mock import patch

from l7r.dice import d10_detailed, xky_detailed
from l7r.records import (
    ActionRecord,
    AttackRecord,
    CombatRecord,
    DamageRecord,
    DiceRoll,
    DieResult,
    DuelRecord,
    DuelRoundRecord,
    InitiativeRecord,
    Modifier,
    ParryRecord,
    Reroll,
    RoundRecord,
    WoundCheckRecord,
)


class TestDieResult:
    def test_basic_fields(self) -> None:
        d = DieResult(face=7, kept=True, exploded=False)
        assert d.face == 7
        assert d.kept is True
        assert d.exploded is False

    def test_exploded_die(self) -> None:
        d = DieResult(face=16, kept=True, exploded=True)
        assert d.face == 16
        assert d.exploded is True

    def test_unkept_die(self) -> None:
        d = DieResult(face=3, kept=False, exploded=False)
        assert d.kept is False


class TestDiceRoll:
    def test_basic_fields(self) -> None:
        dice = [
            DieResult(face=3, kept=False, exploded=False),
            DieResult(face=7, kept=True, exploded=False),
            DieResult(face=9, kept=True, exploded=False),
        ]
        dr = DiceRoll(roll=3, keep=2, reroll=True, dice=dice, overflow_bonus=0, total=16)
        assert dr.roll == 3
        assert dr.keep == 2
        assert dr.total == 16
        assert len(dr.dice) == 3

    def test_overflow_bonus(self) -> None:
        dr = DiceRoll(roll=10, keep=10, reroll=True, dice=[], overflow_bonus=4, total=65)
        assert dr.overflow_bonus == 4


class TestModifier:
    def test_basic(self) -> None:
        m = Modifier(source="R2T", value=5)
        assert m.source == "R2T"
        assert m.value == 5


class TestReroll:
    def test_basic(self) -> None:
        before = DiceRoll(roll=3, keep=2, reroll=True, dice=[], overflow_bonus=0, total=10)
        after = DiceRoll(roll=3, keep=2, reroll=True, dice=[], overflow_bonus=0, total=20)
        r = Reroll(reason="Lucky", before=before, after=after)
        assert r.reason == "Lucky"
        assert r.before.total == 10
        assert r.after.total == 20


class TestAttackRecord:
    def test_defaults(self) -> None:
        rec = AttackRecord(attacker="A", defender="B", knack="attack", phase=3, vps_spent=1)
        assert rec.attacker == "A"
        assert rec.defender == "B"
        assert rec.knack == "attack"
        assert rec.phase == 3
        assert rec.vps_spent == 1
        assert rec.dice is None
        assert rec.modifiers == []
        assert rec.total == 0
        assert rec.tn == 0
        assert rec.hit is False
        assert rec.children == []

    def test_nested_children(self) -> None:
        child = AttackRecord(attacker="B", defender="A", knack="counterattack", phase=3, vps_spent=0)
        parent = AttackRecord(
            attacker="A", defender="B", knack="attack", phase=3, vps_spent=1,
            children=[child],
        )
        assert len(parent.children) == 1
        assert parent.children[0].knack == "counterattack"


class TestParryRecord:
    def test_defaults(self) -> None:
        rec = ParryRecord(defender="D", attacker="A")
        assert rec.defender == "D"
        assert rec.attacker == "A"
        assert rec.success is False
        assert rec.predeclared is False


class TestDamageRecord:
    def test_defaults(self) -> None:
        rec = DamageRecord(attacker="A", defender="D")
        assert rec.light == 0
        assert rec.serious == 0
        assert rec.extra_rolled == 0


class TestWoundCheckRecord:
    def test_defaults(self) -> None:
        rec = WoundCheckRecord(combatant="C")
        assert rec.passed is False
        assert rec.serious_taken == 0
        assert rec.reroll is None
        assert rec.voluntary_serious is False


class TestInitiativeRecord:
    def test_defaults(self) -> None:
        rec = InitiativeRecord(combatant="C")
        assert rec.dice == []
        assert rec.kept == []
        assert rec.modifications == []


class TestDuelRoundRecord:
    def test_defaults(self) -> None:
        rec = DuelRoundRecord(round_num=1)
        assert rec.round_num == 1
        assert rec.attacks == []
        assert rec.resheathe is False


class TestRoundRecord:
    def test_defaults(self) -> None:
        rec = RoundRecord(round_num=1)
        assert rec.initiatives == []
        assert rec.phases == []


class TestDuelRecord:
    def test_basic(self) -> None:
        rec = DuelRecord(a_name="A", b_name="B")
        assert rec.rounds == []


class TestCombatRecord:
    def test_defaults(self) -> None:
        rec = CombatRecord()
        assert rec.duel is None
        assert rec.rounds == []
        assert rec.winner == ""


class TestD10Detailed:
    def test_non_exploding(self) -> None:
        with patch("l7r.dice.randrange", return_value=7):
            result = d10_detailed(reroll=True)
        assert result.face == 7
        assert result.kept is True
        assert result.exploded is False

    def test_explodes_once(self) -> None:
        with patch("l7r.dice.randrange", side_effect=[10, 6]):
            result = d10_detailed(reroll=True)
        assert result.face == 16
        assert result.exploded is True

    def test_no_reroll(self) -> None:
        with patch("l7r.dice.randrange", return_value=10):
            result = d10_detailed(reroll=False)
        assert result.face == 10
        assert result.exploded is False

    def test_multiple_explosions(self) -> None:
        with patch("l7r.dice.randrange", side_effect=[10, 10, 3]):
            result = d10_detailed(reroll=True)
        assert result.face == 23
        assert result.exploded is True


class TestXkYDetailed:
    def test_basic_3k2(self) -> None:
        with patch("l7r.dice.randrange", side_effect=[2, 8, 5]):
            result = xky_detailed(3, 2, reroll=False)
        assert result.roll == 3
        assert result.keep == 2
        assert result.reroll is False
        assert len(result.dice) == 3
        assert result.total == 13  # 8 + 5
        assert result.overflow_bonus == 0

    def test_kept_marking(self) -> None:
        with patch("l7r.dice.randrange", side_effect=[2, 8, 5]):
            result = xky_detailed(3, 2, reroll=False)
        # dice sorted ascending: [2, 5, 8] - top 2 are kept
        kept = [d for d in result.dice if d.kept]
        unkept = [d for d in result.dice if not d.kept]
        assert len(kept) == 2
        assert len(unkept) == 1
        assert unkept[0].face == 2

    def test_overflow_bonus(self) -> None:
        # 14k8 -> actual_xky -> 10k10+2
        dice_values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        with patch("l7r.dice.randrange", side_effect=dice_values):
            result = xky_detailed(14, 8, reroll=False)
        assert result.roll == 10
        assert result.keep == 10
        assert result.overflow_bonus == 2
        # total = sum of all 10 dice + 2 overflow bonus
        assert result.total == 55 + 2

    def test_total_matches_xky(self) -> None:
        """xky_detailed total should match what xky() would produce with same dice."""
        from l7r.dice import xky
        dice_values = [3, 7, 1, 9, 5]
        with patch("l7r.dice.randrange", side_effect=dice_values):
            detailed = xky_detailed(5, 3, reroll=False)
        with patch("l7r.dice.randrange", side_effect=dice_values):
            plain = xky(5, 3, reroll=False)
        assert detailed.total == plain

    def test_reroll_flag_passed(self) -> None:
        with patch("l7r.dice.randrange", side_effect=[10, 6, 3]):
            result = xky_detailed(2, 1, reroll=True)
        # first die: 10+6=16 (exploded), second die: 3 (not)
        assert result.total == 16
        exploded = [d for d in result.dice if d.exploded]
        assert len(exploded) == 1
        assert exploded[0].face == 16

    def test_1k1(self) -> None:
        with patch("l7r.dice.randrange", return_value=7):
            result = xky_detailed(1, 1, reroll=False)
        assert result.total == 7
        assert len(result.dice) == 1
        assert result.dice[0].kept is True


class TestCombatantLastDiceRoll:
    def test_base_xky_captures_dice_roll(self) -> None:
        from l7r.combatant import Combatant
        c = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        result = c.xky(3, 2, True, "attack")
        assert hasattr(c, "last_dice_roll")
        assert c.last_dice_roll is not None
        assert c.last_dice_roll.total == result
        assert len(c.last_dice_roll.dice) == 3
        assert c.last_dice_roll.roll == 3
        assert c.last_dice_roll.keep == 2

    def test_hida_bushi_xky_captures_dice_roll(self) -> None:
        from l7r.schools.hida_bushi import HidaBushi
        c = HidaBushi(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3, rank=3)
        c.attack_knack = "counterattack"
        result = c.xky(5, 3, True, "counterattack")
        assert c.last_dice_roll is not None
        assert c.last_dice_roll.total == result

    def test_shosuro_actor_xky_captures_dice_roll(self) -> None:
        from l7r.schools.shosuro_actor import ShosuroActor
        c = ShosuroActor(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3, rank=5)
        result = c.xky(4, 3, True, "attack")
        assert c.last_dice_roll is not None
        assert c.last_dice_roll.total == result

    def test_merchant_xky_captures_dice_roll(self) -> None:
        from l7r.schools.merchant import Merchant
        c = Merchant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3, rank=3)
        result = c.xky(4, 3, True, "damage")
        assert c.last_dice_roll is not None
        assert c.last_dice_roll.total == result

    def test_professional_xky_captures_dice_roll(self) -> None:
        from collections import defaultdict
        from l7r.professions import Professional
        wm = defaultdict(list)
        ninja = defaultdict(list)
        c = Professional(
            air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3,
            wave_man=wm, ninja=ninja,
        )
        result = c.xky(4, 3, True, "attack")
        assert c.last_dice_roll is not None
        assert c.last_dice_roll.total == result


class TestBonusMethodsReturnModifiers:
    def test_att_bonus_returns_tuple(self) -> None:
        from l7r.combatant import Combatant
        c = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        c.attack_knack = "attack"
        c.enemy = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        bonus, mods = c.att_bonus(20, 15)
        assert isinstance(bonus, int)
        assert isinstance(mods, list)

    def test_att_bonus_always_source(self) -> None:
        from l7r.combatant import Combatant
        c = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        c.always["attack"] = 5
        c._always_sources["attack"] = "R2T"
        c.attack_knack = "attack"
        c.enemy = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        bonus, mods = c.att_bonus(20, 15)
        assert bonus >= 5
        sources = [m.source for m in mods]
        assert "R2T" in sources

    def test_parry_bonus_returns_tuple(self) -> None:
        from l7r.combatant import Combatant
        c = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        c.predeclare_bonus = 0
        c.enemy = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        bonus, mods = c.parry_bonus(20, 15)
        assert isinstance(bonus, int)
        assert isinstance(mods, list)

    def test_parry_bonus_predeclare(self) -> None:
        from l7r.combatant import Combatant
        c = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        c.predeclare_bonus = 5
        c.enemy = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        bonus, mods = c.parry_bonus(20, 10)
        sources = [m.source for m in mods]
        assert "predeclare" in sources

    def test_wc_bonus_returns_tuple(self) -> None:
        from l7r.combatant import Combatant
        c = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        bonus, mods = c.wc_bonus(20, 15)
        assert isinstance(bonus, int)
        assert isinstance(mods, list)

    def test_wc_bonus_strength_of_earth(self) -> None:
        from l7r.combatant import Combatant
        c = Combatant(
            air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3,
            strength_of_the_earth=True,
        )
        bonus, mods = c.wc_bonus(20, 10)
        sources = [m.source for m in mods]
        assert "Strength of Earth" in sources

    def test_always_sources_populated_from_r2t(self) -> None:
        from l7r.schools.akodo_bushi import AkodoBushi
        c = AkodoBushi(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3, rank=2)
        # AkodoBushi r2t_rolls = "wound_check"
        assert "wound_check" in c._always_sources
        assert c._always_sources["wound_check"] == "R2T"


class TestActionRecordsPopulated:
    """Verify that combat methods populate action records."""

    def _make(self, **kw):
        from l7r.combatant import Combatant
        defaults = dict(air=3, earth=5, fire=3, water=3, void=3, attack=3, parry=3)
        defaults.update(kw)
        return Combatant(**defaults)

    def test_make_attack_populates_record(self) -> None:
        from l7r.records import AttackRecord
        a = self._make()
        d = self._make()
        a.attack_knack = "attack"
        a.enemy = d
        a.phase = 3
        rec = a.make_attack()
        assert isinstance(rec, AttackRecord)
        assert rec.attacker == a.name
        assert rec.defender == d.name
        assert rec.dice is not None
        assert rec.total == a.attack_roll

    def test_make_parry_populates_record(self) -> None:
        from l7r.records import ParryRecord
        a = self._make()
        d = self._make()
        d.enemy = a
        d.predeclare_bonus = 0
        a.attack_roll = 20
        a.attack_knack = "attack"
        rec = d.make_parry()
        assert isinstance(rec, ParryRecord)
        assert rec.defender == d.name
        assert rec.tn == a.attack_roll

    def test_deal_damage_populates_record(self) -> None:
        from l7r.records import DamageRecord
        a = self._make()
        d = self._make()
        a.enemy = d
        a.attack_roll = 25
        a.attack_knack = "attack"
        a.was_parried = False
        rec = a.deal_damage(20)
        assert isinstance(rec, DamageRecord)
        assert rec.light > 0 or rec.light == 0
        assert rec.serious >= 0

    def test_wound_check_populates_record(self) -> None:
        from l7r.records import WoundCheckRecord
        c = self._make()
        rec = c.wound_check(15, 0)
        assert isinstance(rec, WoundCheckRecord)
        assert rec.combatant == c.name
        assert rec.light_this_hit == 15

    def test_initiative_populates_record(self) -> None:
        from l7r.records import InitiativeRecord
        c = self._make()
        rec = c.initiative()
        assert isinstance(rec, InitiativeRecord)
        assert rec.combatant == c.name
        assert len(rec.kept) > 0


class TestEngineActionStack:
    """Verify Engine populates combat_record with action records."""

    def _make(self, name="", **kw):
        from l7r.combatant import Combatant
        defaults = dict(air=3, earth=5, fire=3, water=3, void=3, attack=3, parry=3)
        defaults.update(kw)
        c = Combatant(**defaults)
        if name:
            c.name = name
        return c

    def test_engine_has_combat_record(self) -> None:
        from l7r.engine import Engine
        from l7r.formations import Surround
        from l7r.records import CombatRecord
        e = Engine(Surround([self._make()], [self._make()]))
        assert isinstance(e.combat_record, CombatRecord)

    def test_engine_has_renderer(self) -> None:
        from l7r.engine import Engine
        from l7r.formations import Surround
        from l7r.renderers import TextRenderer
        e = Engine(Surround([self._make()], [self._make()]))
        assert isinstance(e.renderer, TextRenderer)

    def test_engine_has_action_stack(self) -> None:
        from l7r.engine import Engine
        from l7r.formations import Surround
        e = Engine(Surround([self._make()], [self._make()]))
        assert e._action_stack == []

    def test_round_populates_round_record(self) -> None:
        from l7r.engine import Engine
        from l7r.formations import Surround
        from l7r.records import RoundRecord
        a = self._make("A")
        b = self._make("B")
        e = Engine(Surround([a], [b]))
        for c in e.combatants:
            c.engine = e
        e.round()
        assert len(e.combat_record.rounds) == 1
        rec = e.combat_record.rounds[0]
        assert isinstance(rec, RoundRecord)
        assert len(rec.initiatives) == 2

    def test_fight_populates_winner(self) -> None:
        from l7r.engine import Engine
        from l7r.formations import Surround
        e = Engine(Surround([self._make("A")], [self._make("B")]))
        e.fight()
        assert e.combat_record.winner in ("side_a", "side_b")

    def test_duel_populates_duel_record(self) -> None:
        from l7r.engine import Engine
        from l7r.formations import Surround
        from l7r.records import DuelRecord
        a = self._make("A")
        b = self._make("B")
        e = Engine(Surround([a], [b]))
        for c in e.combatants:
            c.engine = e
        e.duel()
        assert e.combat_record.duel is not None
        assert isinstance(e.combat_record.duel, DuelRecord)
        assert len(e.combat_record.duel.rounds) >= 1


class TestTextRenderer:
    def test_render_initiative(self) -> None:
        from l7r.renderers import TextRenderer
        rec = InitiativeRecord(combatant="Alice", kept=[2, 5, 8])
        r = TextRenderer()
        text = r.render_initiative(rec)
        assert "Alice" in text
        assert "[2, 5, 8]" in text

    def test_render_attack(self) -> None:
        from l7r.renderers import TextRenderer
        rec = AttackRecord(
            attacker="A", defender="B", knack="attack",
            phase=3, vps_spent=1, total=25, tn=20, hit=True,
        )
        r = TextRenderer()
        lines = r.render_attack(rec)
        assert any("Phase #3" in line for line in lines)
        assert any("25 attack roll" in line for line in lines)

    def test_render_wound_check(self) -> None:
        from l7r.renderers import TextRenderer
        rec = WoundCheckRecord(
            combatant="C", light_total=20, total=22, serious_taken=0,
        )
        r = TextRenderer()
        lines = r.render_action(rec)
        assert any("wound check" in line for line in lines)
        assert any("20" in line for line in lines)

    def test_render_damage(self) -> None:
        from l7r.renderers import TextRenderer
        rec = DamageRecord(attacker="A", defender="D", light=15, serious=1)
        r = TextRenderer()
        lines = r.render_action(rec)
        assert any("15 light" in line for line in lines)
        assert any("1 serious" in line for line in lines)

    def test_render_round(self) -> None:
        from l7r.renderers import TextRenderer
        from l7r.records import RoundRecord
        init = InitiativeRecord(combatant="A", kept=[3, 7])
        attack = AttackRecord(
            attacker="A", defender="B", knack="attack",
            phase=3, vps_spent=0, total=20, tn=15, hit=True,
        )
        rnd = RoundRecord(round_num=1, initiatives=[init], phases=[[], [], [], [attack]])
        r = TextRenderer()
        lines = r.render_round(rnd)
        assert any("initiative" in line for line in lines)
        assert any("Phase #3" in line for line in lines)

    def test_render_duel_round(self) -> None:
        from l7r.renderers import TextRenderer
        from l7r.records import DuelRoundRecord, DiceRoll
        contested_a = DiceRoll(roll=5, keep=3, reroll=False, dice=[], overflow_bonus=0, total=22)
        contested_b = DiceRoll(roll=5, keep=3, reroll=False, dice=[], overflow_bonus=0, total=18)
        rec = DuelRoundRecord(
            round_num=1, a_name="A", b_name="B",
            contested_a=contested_a, contested_b=contested_b,
        )
        r = TextRenderer()
        lines = r.render_duel_round(rec)
        assert any("Duel round 1" in line for line in lines)
        assert any("Contested" in line for line in lines)

    def test_render_duel_round_resheathe(self) -> None:
        from l7r.renderers import TextRenderer
        from l7r.records import DuelRoundRecord
        rec = DuelRoundRecord(round_num=1, a_name="A", b_name="B", resheathe=True)
        r = TextRenderer()
        lines = r.render_duel_round(rec)
        assert any("Resheathe" in line for line in lines)

    def test_render_parry(self) -> None:
        from l7r.renderers import TextRenderer
        rec = ParryRecord(defender="D", attacker="A", total=25, success=True)
        r = TextRenderer()
        lines = r.render_action(rec)
        assert any("parry roll" in line for line in lines)
        assert any("D" in line for line in lines)

    def test_render_combat_with_duel(self) -> None:
        from l7r.renderers import TextRenderer
        from l7r.records import CombatRecord, DuelRecord, DuelRoundRecord, DiceRoll
        contested_a = DiceRoll(roll=5, keep=3, reroll=False, dice=[], overflow_bonus=0, total=22)
        contested_b = DiceRoll(roll=5, keep=3, reroll=False, dice=[], overflow_bonus=0, total=18)
        duel_round = DuelRoundRecord(
            round_num=1, a_name="A", b_name="B",
            contested_a=contested_a, contested_b=contested_b,
        )
        duel = DuelRecord(a_name="A", b_name="B", rounds=[duel_round])
        combat = CombatRecord(duel=duel)
        r = TextRenderer()
        lines = r.render_combat(combat)
        assert any("Duel round 1" in line for line in lines)

    def test_render_attack_with_children(self) -> None:
        from l7r.renderers import TextRenderer
        child_parry = ParryRecord(defender="B", attacker="A", total=18, success=False)
        child_damage = DamageRecord(attacker="A", defender="B", light=10, serious=0)
        child_wc = WoundCheckRecord(combatant="B", light_total=10, total=15, serious_taken=0)
        rec = AttackRecord(
            attacker="A", defender="B", knack="attack",
            phase=3, vps_spent=0, total=25, tn=20, hit=True,
            children=[child_parry, child_damage, child_wc],
        )
        r = TextRenderer()
        lines = r.render_attack(rec)
        assert any("parry roll" in line for line in lines)
        assert any("deals 10 light" in line for line in lines)
        assert any("wound check" in line for line in lines)


class TestFullIntegration:
    """Full integration tests: run a combat and verify both messages
    and combat_record are populated."""

    def test_fight_produces_records(self) -> None:
        from l7r.combatant import Combatant
        from l7r.engine import Engine
        from l7r.formations import Surround
        a = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        a.name = "Fighter_A"
        b = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        b.name = "Fighter_B"
        e = Engine(Surround([a], [b]))
        e.fight()
        # Combat record should have rounds
        assert len(e.combat_record.rounds) >= 1
        # Winner should be set
        assert e.combat_record.winner in ("side_a", "side_b")

    def test_duel_produces_records(self) -> None:
        from l7r.combatant import Combatant
        from l7r.engine import Engine
        from l7r.formations import Surround
        a = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        a.name = "Duelist_A"
        b = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        b.name = "Duelist_B"
        e = Engine(Surround([a], [b]))
        e.fight(duel=True)
        # Duel record should exist
        assert e.combat_record.duel is not None
        assert len(e.combat_record.duel.rounds) >= 1

    def test_renderer_can_render_full_combat(self) -> None:
        from l7r.combatant import Combatant
        from l7r.engine import Engine
        from l7r.formations import Surround
        a = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        b = Combatant(air=3, earth=3, fire=3, water=3, void=3, attack=3, parry=3)
        e = Engine(Surround([a], [b]))
        e.fight()
        lines = e.renderer.render_combat(e.combat_record)
        assert isinstance(lines, list)
        # Should have at least some lines (initiative + actions)
        assert len(lines) > 0


class TestActionRecordUnion:
    def test_attack_is_action_record(self) -> None:
        rec: ActionRecord = AttackRecord(attacker="A", defender="B", knack="attack", phase=1, vps_spent=0)
        assert isinstance(rec, AttackRecord)

    def test_parry_is_action_record(self) -> None:
        rec: ActionRecord = ParryRecord(defender="D", attacker="A")
        assert isinstance(rec, ParryRecord)

    def test_damage_is_action_record(self) -> None:
        rec: ActionRecord = DamageRecord(attacker="A", defender="D")
        assert isinstance(rec, DamageRecord)

    def test_wound_check_is_action_record(self) -> None:
        rec: ActionRecord = WoundCheckRecord(combatant="C")
        assert isinstance(rec, WoundCheckRecord)
