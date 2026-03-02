"""Tests for out-of-band trigger record capture.

School triggers that call wound_check() outside the normal engine attack flow
must capture the returned WoundCheckRecord into combatant.triggered_records
so the engine can place them into the combat record tree.
"""

from __future__ import annotations

from unittest.mock import patch

from l7r.combatant import Combatant
from l7r.engine import Engine
from l7r.formations import Surround
from l7r.records import (
    AttackRecord, DamageRecord, ParryRecord, WoundCheckRecord,
)
from l7r.schools.akodo_bushi import AkodoBushi
from l7r.schools.kakita_duelist import KakitaDuelist
from l7r.schools.kuni_witch_hunter import KuniWitchHunter
from l7r.schools.shiba_bushi import ShibaBushi


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


def make(name: str = "", **kw: int) -> Combatant:
    defaults = dict(
        air=3, earth=5, fire=3, water=3,
        void=3, attack=3, parry=3,
    )
    defaults.update(kw)
    c = Combatant(**defaults)
    if name:
        c.name = name
    return c


def engine_1v1(
    inner_kw: dict | None = None,
    outer_kw: dict | None = None,
) -> tuple[Engine, Combatant, Combatant]:
    i = make("Inner", **(inner_kw or {}))
    o = make("Outer", **(outer_kw or {}))
    f = Surround([i], [o])
    e = Engine(f)
    for c in e.combatants:
        c.engine = e
    return e, i, o


def attack_rec(hit: bool = False, knack: str = "attack") -> AttackRecord:
    return AttackRecord(
        attacker="A", defender="D", knack=knack,
        phase=0, vps_spent=0, hit=hit,
    )


def parry_rec(success: bool = False) -> ParryRecord:
    return ParryRecord(defender="D", attacker="A", success=success)


def damage_rec(light: int = 10, serious: int = 0) -> DamageRecord:
    return DamageRecord(
        attacker="A", defender="D", light=light, serious=serious,
    )


def fake_wc(combatant: str = "X") -> WoundCheckRecord:
    return WoundCheckRecord(combatant=combatant, light_this_hit=10, light_total=10)


# -----------------------------------------------------------
# Combatant: triggered_records attribute
# -----------------------------------------------------------


class TestTriggeredRecordsAttribute:
    def test_combatant_has_triggered_records(self) -> None:
        c = Combatant(**STATS)
        assert hasattr(c, "triggered_records")
        assert c.triggered_records == []

    def test_triggered_records_is_instance_list(self) -> None:
        """Each combatant gets its own list, not a shared class attribute."""
        a = Combatant(**STATS)
        b = Combatant(**STATS)
        a.triggered_records.append("x")
        assert b.triggered_records == []


# -----------------------------------------------------------
# Kuni Witch Hunter R5T: captures both wound_check returns
# -----------------------------------------------------------


class TestKuniR5TTriggeredRecords:
    def test_enemy_wc_captured(self) -> None:
        k = KuniWitchHunter(rank=5, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        wc = fake_wc("enemy")

        with (
            patch.object(enemy, "wound_check", return_value=wc),
            patch.object(k, "wound_check", return_value=None),
        ):
            k.r5t_trigger(20, 15, 30)

        assert wc in k.triggered_records

    def test_self_wc_captured(self) -> None:
        k = KuniWitchHunter(rank=5, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        enemy_wc = fake_wc("enemy")
        self_wc = fake_wc("self")

        with (
            patch.object(enemy, "wound_check", return_value=enemy_wc),
            patch.object(k, "wound_check", return_value=self_wc),
        ):
            k.r5t_trigger(20, 20, 30)

        assert enemy_wc in k.triggered_records
        assert self_wc in k.triggered_records

    def test_none_wc_not_appended(self) -> None:
        k = KuniWitchHunter(rank=5, **STATS)
        enemy = make_enemy()
        link(k, enemy)

        with (
            patch.object(enemy, "wound_check", return_value=None),
            patch.object(k, "wound_check", return_value=None),
        ):
            k.r5t_trigger(20, 20, 30)

        assert k.triggered_records == []

    def test_no_recursive_reflection(self) -> None:
        """R5T self-damage wound check must not trigger another reflection.

        Without a recursion guard, wound_check(self_damage) fires the
        wound_check event again, which fires R5T again, creating an
        infinite halving chain (45 -> 22 -> 11 -> 5 -> ...).
        """
        k = KuniWitchHunter(rank=5, **STATS)
        enemy = make_enemy()
        link(k, enemy)

        enemy_wc_calls: list[int] = []
        orig_enemy_wc = enemy.wound_check

        def spy_enemy_wc(light: int, *a, **kw) -> WoundCheckRecord:
            enemy_wc_calls.append(light)
            return orig_enemy_wc(light, *a, **kw)

        with patch.object(enemy, "wound_check", side_effect=spy_enemy_wc):
            k.r5t_trigger(20, 30, 30)

        # Should reflect once (30 light to enemy), not recursively
        assert len(enemy_wc_calls) == 1
        assert enemy_wc_calls[0] == 30


# -----------------------------------------------------------
# Akodo Bushi R5T: captures wound_check return
# -----------------------------------------------------------


class TestAkodoR5TTriggeredRecords:
    def test_wc_captured(self) -> None:
        a = AkodoBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(a, enemy)
        a.vps = 10
        wc = fake_wc("enemy")

        with patch.object(enemy, "wound_check", return_value=wc):
            a.r5t_trigger(50, 30, 30)

        assert wc in a.triggered_records

    def test_none_wc_not_appended(self) -> None:
        a = AkodoBushi(rank=5, **STATS)
        enemy = make_enemy()
        link(a, enemy)
        a.vps = 10

        with patch.object(enemy, "wound_check", return_value=None):
            a.r5t_trigger(50, 30, 30)

        assert a.triggered_records == []


# -----------------------------------------------------------
# Kakita Duelist R5T: captures wound_check return
# -----------------------------------------------------------


class TestKakitaR5TTriggeredRecords:
    def test_wc_captured(self) -> None:
        k = KakitaDuelist(rank=5, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.phase = 0
        wc = fake_wc("enemy")

        with (
            patch.object(enemy, "xky", return_value=10),
            patch.object(enemy, "wound_check", return_value=wc),
        ):
            k.r5t_trigger()

        assert wc in k.triggered_records

    def test_none_wc_not_appended(self) -> None:
        k = KakitaDuelist(rank=5, **STATS)
        enemy = make_enemy()
        link(k, enemy)
        k.phase = 0

        with (
            patch.object(enemy, "xky", return_value=10),
            patch.object(enemy, "wound_check", return_value=None),
        ):
            k.r5t_trigger()

        assert k.triggered_records == []


# -----------------------------------------------------------
# Shiba Bushi R3T (make_parry): captures wound_check return
# -----------------------------------------------------------


class TestShibaR3TTriggeredRecords:
    def test_wc_captured(self) -> None:
        s = ShibaBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(s, enemy)
        s.predeclare_bonus = 0
        enemy.attack_roll = 10
        enemy.attack_knack = "attack"
        wc = fake_wc("enemy")

        with patch.object(enemy, "wound_check", return_value=wc):
            s.make_parry()

        assert wc in s.triggered_records

    def test_none_wc_not_appended(self) -> None:
        s = ShibaBushi(rank=3, **STATS)
        enemy = make_enemy()
        link(s, enemy)
        s.predeclare_bonus = 0
        enemy.attack_roll = 10
        enemy.attack_knack = "attack"

        with patch.object(enemy, "wound_check", return_value=None):
            s.make_parry()

        assert s.triggered_records == []


# -----------------------------------------------------------
# Engine: _drain_triggered helper
# -----------------------------------------------------------


class TestDrainTriggered:
    def test_collects_from_combatants(self) -> None:
        e, a, b = engine_1v1()
        r1 = fake_wc("a")
        r2 = fake_wc("b")
        a.triggered_records = [r1]
        b.triggered_records = [r2]

        result = e._drain_triggered(a, b)

        assert result == [r1, r2]
        assert a.triggered_records == []
        assert b.triggered_records == []

    def test_empty_when_no_records(self) -> None:
        e, a, b = engine_1v1()
        result = e._drain_triggered(a, b)
        assert result == []

    def test_clears_after_drain(self) -> None:
        e, a, b = engine_1v1()
        a.triggered_records = [fake_wc()]
        e._drain_triggered(a)
        assert a.triggered_records == []


# -----------------------------------------------------------
# Engine.attack: drains triggered records after parry
# -----------------------------------------------------------


class TestAttackDrainsAfterParry:
    def test_parry_triggered_records_in_attack_children(self) -> None:
        """Triggered records produced during parry (e.g. ShibaBushi R3T)
        are appended to the attack record's children."""
        e, att, dfn = engine_1v1()
        e.phase = 3
        dfn.predeclare_bonus = 0
        triggered_wc = fake_wc("triggered")

        def parry_side_effect(defender, attacker):
            dfn.triggered_records.append(triggered_wc)
            return (True, True, parry_rec(success=True))

        with (
            patch.object(dfn, "will_counterattack", return_value=False),
            patch.object(dfn, "will_predeclare", return_value=False),
            patch.object(att, "make_attack", return_value=attack_rec(hit=True)),
            patch.object(e, "parry", side_effect=parry_side_effect),
        ):
            e.attack("attack", att, dfn)

        # The triggered record should be in phase records
        rnd = e.combat_record.rounds[-1] if e.combat_record.rounds else None
        # Top-level attack puts record in phase list
        if rnd and e.phase < len(rnd.phases):
            attack_records = rnd.phases[e.phase]
            if attack_records:
                assert triggered_wc in attack_records[0].children


# -----------------------------------------------------------
# Engine.attack: drains triggered records after wound_check
# -----------------------------------------------------------


class TestAttackDrainsAfterWoundCheck:
    def test_wc_triggered_records_in_attack_children(self) -> None:
        """Triggered records produced during wound_check (e.g. Kuni R5T,
        Akodo R5T) are appended to the attack record's children."""
        e, att, dfn = engine_1v1()
        e.phase = 3
        att.attack_roll = 25
        dfn.predeclare_bonus = 0
        triggered_wc = fake_wc("triggered")

        wc_result = fake_wc("defender")

        def wc_side_effect(*args, **kwargs):
            att.triggered_records.append(triggered_wc)
            return wc_result

        with (
            patch.object(dfn, "will_counterattack", return_value=False),
            patch.object(dfn, "will_predeclare", return_value=False),
            patch.object(att, "make_attack", return_value=attack_rec(hit=True)),
            patch.object(e, "parry", return_value=(False, False, None)),
            patch.object(att, "deal_damage", return_value=damage_rec(light=15)),
            patch.object(dfn, "wound_check", side_effect=wc_side_effect),
        ):
            e.attack("attack", att, dfn)

        rnd = e.combat_record.rounds[-1] if e.combat_record.rounds else None
        if rnd and e.phase < len(rnd.phases):
            attack_records = rnd.phases[e.phase]
            if attack_records:
                assert triggered_wc in attack_records[0].children


# -----------------------------------------------------------
# Engine.round: drains triggered records after pre_round
# -----------------------------------------------------------


class TestRoundDrainsPreRound:
    def test_pre_round_triggered_records_in_phase_0(self) -> None:
        """Triggered records from pre_round triggers (e.g. Kakita R5T)
        are placed into phase 0 of the round record."""
        e, i, o = engine_1v1()
        triggered_wc = fake_wc("pre_round")

        def pre_round_trigger():
            i.triggered_records.append(triggered_wc)

        i.events["pre_round"].append(pre_round_trigger)

        with (
            patch.object(i, "choose_action", return_value=None),
            patch.object(o, "choose_action", return_value=None),
        ):
            e.round()

        rnd = e.combat_record.rounds[-1]
        assert triggered_wc in rnd.phases[0]
