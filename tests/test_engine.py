"""Tests for the Engine: orchestration, attack resolution,
round lifecycle, and full combat integration.

These tests verify the ENGINE's orchestration logic —
calling combatant methods in the right order, branching
on hit/miss/parry, TN mutation during counterattacks,
death handling, and round/fight lifecycle. Combatant
internals are mocked to keep tests focused.
"""

import random
from unittest.mock import patch

from l7r.combatant import Combatant
from l7r.engine import Engine
from l7r.formations import Surround


def make(name: str = "", **kw: int) -> Combatant:
    """Create a minimal Combatant for engine testing."""
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
    """1v1 Surround with Engine, engine set on all."""
    i = make("Inner", **(inner_kw or {}))
    o = make("Outer", **(outer_kw or {}))
    f = Surround([i], [o])
    e = Engine(f)
    for c in e.combatants:
        c.engine = e
    return e, i, o


def engine_1v3() -> (
    tuple[Engine, Combatant, list[Combatant]]
):
    """1 inner vs 3 outer, engine set on all."""
    i = make("Inner")
    outers = [make(f"O{n}") for n in range(3)]
    f = Surround([i], outers)
    e = Engine(f)
    for c in e.combatants:
        c.engine = e
    return e, i, outers


# -----------------------------------------------------------
# Init, log, finished
# -----------------------------------------------------------


class TestEngineInit:
    def test_stores_formation(self) -> None:
        f = Surround([make()], [make()])
        e = Engine(f)
        assert e.formation is f

    def test_combatants_from_formation(self) -> None:
        i, o = make(), make()
        f = Surround([i], [o])
        e = Engine(f)
        assert set(e.combatants) == {i, o}

    def test_empty_messages(self) -> None:
        e = Engine(Surround([make()], [make()]))
        assert e.messages == []


class TestEngineLog:
    def test_appends_to_messages(self) -> None:
        e = Engine(Surround([make()], [make()]))
        with patch("builtins.print"):
            e.log("hello")
        assert e.messages == ["hello"]

    def test_accumulates(self) -> None:
        e = Engine(Surround([make()], [make()]))
        with patch("builtins.print"):
            e.log("a")
            e.log("b")
        assert e.messages == ["a", "b"]


class TestEngineFinished:
    def test_false_when_both_sides(self) -> None:
        e = Engine(Surround([make()], [make()]))
        assert e.finished is False

    def test_true_when_inner_empty(self) -> None:
        f = Surround([make()], [make()])
        e = Engine(f)
        f.inner.clear()
        assert e.finished is True


# -----------------------------------------------------------
# Parry delegation
# -----------------------------------------------------------


class TestEngineParry:
    """Tests for engine.parry() — who gets to parry."""

    def test_defender_parries_success(self) -> None:
        e, _, defender = engine_1v1()
        defender.enemy = make("E")
        defender.predeclare_bonus = 0
        defender.enemy.attack_roll = 20

        with (
            patch.object(
                defender, "will_parry", return_value=True
            ),
            patch.object(
                defender, "make_parry", return_value=True
            ),
        ):
            ok, tried = e.parry(defender, defender.enemy)
        assert ok is True
        assert tried is True

    def test_defender_parries_failure(self) -> None:
        e, _, defender = engine_1v1()
        defender.enemy = make("E")
        defender.predeclare_bonus = 0
        defender.enemy.attack_roll = 99

        with (
            patch.object(
                defender, "will_parry", return_value=True
            ),
            patch.object(
                defender,
                "make_parry",
                return_value=False,
            ),
        ):
            ok, tried = e.parry(defender, defender.enemy)
        assert ok is False
        assert tried is True

    def test_no_parry_no_allies(self) -> None:
        """1v1 inner defender has no adjacent allies."""
        e, _, defender = engine_1v1()
        defender.predeclare_bonus = 0

        with patch.object(
            defender, "will_parry", return_value=False
        ):
            ok, tried = e.parry(defender, make("E"))
        assert ok is False
        assert tried is False

    def test_ally_parries(self) -> None:
        """Defender declines, adjacent ally steps in."""
        e, inner, outers = engine_1v3()
        defender = outers[0]
        attacker = inner
        defender.enemy = attacker
        attacker.attack_roll = 20

        with (
            patch.object(
                defender, "will_parry", return_value=False
            ),
            patch.object(
                outers[1],
                "will_parry_for",
                return_value=True,
            ),
            patch.object(
                outers[1],
                "make_parry_for",
                return_value=True,
            ),
        ):
            ok, tried = e.parry(defender, attacker)
        assert ok is True
        assert tried is True

    def test_defender_priority_over_ally(self) -> None:
        """If defender parries, allies not consulted."""
        e, inner, outers = engine_1v3()
        defender = outers[0]
        defender.enemy = inner
        defender.predeclare_bonus = 0
        inner.attack_roll = 20

        with (
            patch.object(
                defender, "will_parry", return_value=True
            ),
            patch.object(
                defender, "make_parry", return_value=True
            ),
            patch.object(
                outers[1], "will_parry_for"
            ) as mock_ally,
        ):
            e.parry(defender, inner)
        mock_ally.assert_not_called()


# -----------------------------------------------------------
# Attack flow: hit / miss / parry branching
# -----------------------------------------------------------


class TestEngineAttackFlow:
    """Tests for engine.attack() orchestration."""

    def test_hit_no_parry_deals_damage(self) -> None:
        e, att, dfn = engine_1v1()
        e.phase = 3
        att.attack_roll = 25
        dfn.predeclare_bonus = 0

        with (
            patch.object(
                dfn,
                "will_counterattack",
                return_value=False,
            ),
            patch.object(
                dfn,
                "will_predeclare",
                return_value=False,
            ),
            patch.object(
                att, "make_attack", return_value=True
            ),
            patch.object(
                e,
                "parry",
                return_value=(False, False),
            ),
            patch.object(
                att,
                "deal_damage",
                return_value=(15, 0),
            ) as mock_dd,
            patch.object(dfn, "wound_check") as mock_wc,
        ):
            e.attack("attack", att, dfn)
        mock_dd.assert_called_once_with(
            dfn.tn, extra_damage=True
        )
        mock_wc.assert_called_once_with(15, 0)

    def test_hit_parry_succeeds_no_damage(self) -> None:
        e, att, dfn = engine_1v1()
        e.phase = 3
        dfn.predeclare_bonus = 0

        with (
            patch.object(
                dfn,
                "will_counterattack",
                return_value=False,
            ),
            patch.object(
                dfn,
                "will_predeclare",
                return_value=False,
            ),
            patch.object(
                att, "make_attack", return_value=True
            ),
            patch.object(
                e,
                "parry",
                return_value=(True, True),
            ),
            patch.object(att, "deal_damage") as mock_dd,
        ):
            e.attack("attack", att, dfn)
        mock_dd.assert_not_called()

    def test_failed_parry_no_extra_damage(self) -> None:
        """Attempted but failed parry: extra_damage=False
        (precision bonus negated)."""
        e, att, dfn = engine_1v1()
        e.phase = 3
        att.attack_roll = 25
        dfn.predeclare_bonus = 0

        with (
            patch.object(
                dfn,
                "will_counterattack",
                return_value=False,
            ),
            patch.object(
                dfn,
                "will_predeclare",
                return_value=False,
            ),
            patch.object(
                att, "make_attack", return_value=True
            ),
            patch.object(
                e,
                "parry",
                return_value=(False, True),
            ),
            patch.object(
                att,
                "deal_damage",
                return_value=(10, 0),
            ) as mock_dd,
            patch.object(dfn, "wound_check"),
        ):
            e.attack("attack", att, dfn)
        mock_dd.assert_called_once_with(
            dfn.tn, extra_damage=False
        )

    def test_miss_no_damage(self) -> None:
        e, att, dfn = engine_1v1()
        e.phase = 3
        dfn.predeclare_bonus = 0

        with (
            patch.object(
                dfn,
                "will_counterattack",
                return_value=False,
            ),
            patch.object(
                dfn,
                "will_predeclare",
                return_value=False,
            ),
            patch.object(
                att, "make_attack", return_value=False
            ),
            patch.object(att, "deal_damage") as mock_dd,
        ):
            e.attack("attack", att, dfn)
        mock_dd.assert_not_called()

    def test_miss_predeclare_triggers_parry(self) -> None:
        """On miss, predeclared defender gets a free
        parry."""
        e, att, dfn = engine_1v1()
        e.phase = 3
        att.attack_roll = 10

        def set_predeclare():
            dfn.predeclare_bonus = 5
            return True

        with (
            patch.object(
                dfn,
                "will_counterattack",
                return_value=False,
            ),
            patch.object(
                dfn,
                "will_predeclare",
                side_effect=set_predeclare,
            ),
            patch.object(
                att, "make_attack", return_value=False
            ),
            patch.object(
                dfn, "make_parry", return_value=True
            ) as mp,
        ):
            e.attack("attack", att, dfn)
        mp.assert_called_once()

    def test_sets_knack_and_enemy(self) -> None:
        e, att, dfn = engine_1v1()
        e.phase = 3
        dfn.predeclare_bonus = 0

        with (
            patch.object(
                dfn,
                "will_counterattack",
                return_value=False,
            ),
            patch.object(
                dfn,
                "will_predeclare",
                return_value=False,
            ),
            patch.object(
                att, "make_attack", return_value=False
            ),
        ):
            e.attack("double_attack", att, dfn)
        assert att.attack_knack == "double_attack"
        assert att.enemy is dfn
        assert dfn.enemy is att

    def test_post_defense_skipped_when_dead(self) -> None:
        e, att, dfn = engine_1v1()
        e.phase = 3
        dfn.predeclare_bonus = 0
        post_defense = []
        dfn.events["post_defense"].append(
            lambda: post_defense.append(True)
        )

        def kill_defender(light, serious):
            dfn.dead = True

        with (
            patch.object(
                dfn,
                "will_counterattack",
                return_value=False,
            ),
            patch.object(
                dfn,
                "will_predeclare",
                return_value=False,
            ),
            patch.object(
                att, "make_attack", return_value=True
            ),
            patch.object(
                e,
                "parry",
                return_value=(False, False),
            ),
            patch.object(
                att,
                "deal_damage",
                return_value=(100, 10),
            ),
            patch.object(
                dfn,
                "wound_check",
                side_effect=kill_defender,
            ),
        ):
            e.attack("attack", att, dfn)
        assert not post_defense

    def test_logs_attack_header(self) -> None:
        e, att, dfn = engine_1v1()
        e.phase = 5
        dfn.predeclare_bonus = 0

        with (
            patch.object(
                dfn,
                "will_counterattack",
                return_value=False,
            ),
            patch.object(
                dfn,
                "will_predeclare",
                return_value=False,
            ),
            patch.object(
                att, "make_attack", return_value=False
            ),
        ):
            e.attack("attack", att, dfn)
        assert any(
            "Phase #5" in m and att.name in m
            for m in e.messages
        )

    def test_attacker_dead_returns_early(self) -> None:
        e, att, dfn = engine_1v1()
        e.phase = 3
        att.dead = True

        with (
            patch.object(
                dfn,
                "will_counterattack",
                return_value=False,
            ),
            patch.object(att, "make_attack") as mock_ma,
        ):
            e.attack("attack", att, dfn)
        mock_ma.assert_not_called()


# -----------------------------------------------------------
# Counterattack TN mutation
# -----------------------------------------------------------


class TestEngineCounterattack:
    """Tests for the TN mutation during ally counterattack
    checks — key regression coverage for the future
    mutation refactor."""

    def test_ally_check_raises_tn(self) -> None:
        """During ally counterattack loop, attacker TN
        is raised by 5 * parry."""
        e, att, dfn = engine_1v1()
        e.phase = 3
        ally = make("Ally")
        ally.engine = e
        att.attackable.add(ally)

        original_tn = att.tn
        tn_during: list[int] = []

        def capture_tn(d, a):
            tn_during.append(att.tn)
            return False

        with (
            patch.object(
                dfn,
                "will_counterattack",
                return_value=False,
            ),
            patch.object(
                ally,
                "will_counterattack_for",
                side_effect=capture_tn,
            ),
            patch.object(
                att, "make_attack", return_value=False
            ),
            patch.object(
                dfn,
                "will_predeclare",
                return_value=False,
            ),
        ):
            dfn.predeclare_bonus = 0
            e.attack("attack", att, dfn)

        assert len(tn_during) == 1
        expected = original_tn + 5 * att.parry
        assert tn_during[0] == expected

    def test_tn_restored_after_check(self) -> None:
        """TN returns to original after the ally
        counterattack section."""
        e, att, dfn = engine_1v1()
        e.phase = 3
        ally = make("Ally")
        ally.engine = e
        att.attackable.add(ally)
        original_tn = att.tn

        with (
            patch.object(
                dfn,
                "will_counterattack",
                return_value=False,
            ),
            patch.object(
                ally,
                "will_counterattack_for",
                return_value=False,
            ),
            patch.object(
                att, "make_attack", return_value=False
            ),
            patch.object(
                dfn,
                "will_predeclare",
                return_value=False,
            ),
        ):
            dfn.predeclare_bonus = 0
            e.attack("attack", att, dfn)

        assert att.tn == original_tn

    def test_no_ally_check_on_counterattack(self) -> None:
        """Counterattacks skip the ally counterattack
        loop (prevents infinite recursion)."""
        e, att, dfn = engine_1v1()
        e.phase = 3
        ally = make("Ally")
        ally.engine = e
        att.attackable.add(ally)

        with (
            patch.object(
                dfn,
                "will_counterattack",
                return_value=False,
            ),
            patch.object(
                ally, "will_counterattack_for"
            ) as mock_cf,
            patch.object(
                att, "make_attack", return_value=False
            ),
            patch.object(
                dfn,
                "will_predeclare",
                return_value=False,
            ),
        ):
            dfn.predeclare_bonus = 0
            e.attack("counterattack", att, dfn)

        mock_cf.assert_not_called()

    def test_defender_counterattacks_recursively(
        self,
    ) -> None:
        """When defender counterattacks, the counter
        resolves before the original attack continues."""
        e, att, dfn = engine_1v1()
        e.phase = 3
        dfn.predeclare_bonus = 0
        att.predeclare_bonus = 0

        order: list[str] = []

        def track_att():
            order.append("attacker")
            return False

        def track_dfn():
            order.append("defender")
            return False

        with (
            patch.object(
                dfn,
                "will_counterattack",
                return_value=True,
            ),
            patch.object(
                att,
                "will_counterattack",
                return_value=False,
            ),
            patch.object(
                att,
                "will_predeclare",
                return_value=False,
            ),
            patch.object(
                dfn,
                "will_predeclare",
                return_value=False,
            ),
            patch.object(
                dfn,
                "make_attack",
                side_effect=track_dfn,
            ),
            patch.object(
                att,
                "make_attack",
                side_effect=track_att,
            ),
        ):
            e.attack("attack", att, dfn)

        assert order == ["defender", "attacker"]


# -----------------------------------------------------------
# Round lifecycle
# -----------------------------------------------------------


class TestEngineRound:
    """Tests for engine.round() — initiative, phases,
    death cleanup, triggers."""

    def test_initiative_rolled(self) -> None:
        """All combatants get actions from initiative."""
        e, i, o = engine_1v1()

        with (
            patch.object(
                i, "choose_action", return_value=None
            ),
            patch.object(
                o, "choose_action", return_value=None
            ),
        ):
            e.round()

        assert hasattr(i, "actions")
        assert hasattr(o, "actions")

    def test_all_phases_visited(self) -> None:
        """Phases 0-10 are all visited."""
        e, i, o = engine_1v1()
        phases_seen: list[int] = []

        def track_phase():
            phases_seen.append(i.phase)
            return None

        with (
            patch.object(
                i,
                "choose_action",
                side_effect=track_phase,
            ),
            patch.object(
                o, "choose_action", return_value=None
            ),
        ):
            e.round()

        for p in range(11):
            assert p in phases_seen

    def test_dead_cleaned_between_phases(self) -> None:
        e, i, o = engine_1v1()
        o.dead = True

        with (
            patch.object(
                i, "choose_action", return_value=None
            ),
            patch.object(
                o, "choose_action", return_value=None
            ),
        ):
            e.round()

        assert o not in e.combatants

    def test_pre_round_fires(self) -> None:
        e, i, o = engine_1v1()
        fired: list[bool] = []
        i.events["pre_round"].append(
            lambda: fired.append(True)
        )

        with (
            patch.object(
                i, "choose_action", return_value=None
            ),
            patch.object(
                o, "choose_action", return_value=None
            ),
        ):
            e.round()

        assert fired

    def test_post_round_fires(self) -> None:
        e, i, o = engine_1v1()
        fired: list[bool] = []
        i.events["post_round"].append(
            lambda: fired.append(True)
        )

        with (
            patch.object(
                i, "choose_action", return_value=None
            ),
            patch.object(
                o, "choose_action", return_value=None
            ),
        ):
            e.round()

        assert fired

    def test_stops_when_finished(self) -> None:
        """Round exits early when one side eliminated."""
        e, att, dfn = engine_1v1()
        action_given = [False]

        def one_action():
            if not action_given[0]:
                action_given[0] = True
                return ("attack", dfn)
            return None

        def killing_attack(knack, a, d):
            d.dead = True

        with (
            patch.object(
                att,
                "choose_action",
                side_effect=one_action,
            ),
            patch.object(
                dfn, "choose_action", return_value=None
            ),
            patch.object(
                e, "attack", side_effect=killing_attack
            ),
        ):
            e.round()

        assert e.finished


# -----------------------------------------------------------
# Fight lifecycle
# -----------------------------------------------------------


class TestEngineFight:
    """Tests for engine.fight() — full combat lifecycle."""

    def test_sets_engine_on_combatants(self) -> None:
        i, o = make("I"), make("O")
        f = Surround([i], [o])
        e = Engine(f)

        assert i.engine is None

        def end_combat():
            f.outer.clear()

        with patch.object(
            e, "round", side_effect=end_combat
        ):
            e.fight()

        assert i.engine is e
        assert o.engine is e

    def test_pre_fight_triggers(self) -> None:
        i, o = make("I"), make("O")
        f = Surround([i], [o])
        e = Engine(f)
        fired: list[bool] = []
        i.events["pre_fight"].append(
            lambda: fired.append(True)
        )

        def end_combat():
            f.outer.clear()

        with patch.object(
            e, "round", side_effect=end_combat
        ):
            e.fight()

        assert fired

    def test_full_combat_resolves(self) -> None:
        """A complete 1v1 combat runs to completion."""
        random.seed(42)
        i = make("Inner", fire=5, earth=5, water=5)
        o = make("Outer", fire=5, earth=5, water=5)
        f = Surround([i], [o])
        e = Engine(f)

        with patch("builtins.print"):
            e.fight()

        assert e.finished
        assert i.dead or o.dead
        assert len(e.messages) > 0
