"""Tests for formation logic: adjacency, deployment, and death.

Covers Formation base class (adjacency, death unlinking),
Surround deployment, link helper, leftmost, and death handling.
"""

from l7r.combatant import Combatant
from l7r.formations import Formation, Line, Surround


def make(name: str = "", **kw: int) -> Combatant:
    """Create a minimal Combatant for formation testing."""
    defaults = dict(
        air=3, earth=3, fire=3, water=3,
        void=3, attack=3, parry=3,
    )
    defaults.update(kw)
    c = Combatant(**defaults)
    if name:
        c.name = name
    return c


# -----------------------------------------------------------
# Formation base class
# -----------------------------------------------------------


class TestFormationBase:
    """Tests for Formation adjacency accessors."""

    def test_unknown_combatant_has_no_left(self) -> None:
        f = Formation()
        assert f.get_left(make()) is None

    def test_unknown_combatant_has_no_right(self) -> None:
        f = Formation()
        assert f.get_right(make()) is None

    def test_unknown_combatant_has_no_adjacent(self) -> None:
        f = Formation()
        assert f.adjacent(make()) == []

    def test_set_and_get_left(self) -> None:
        f = Formation()
        a, b = make("A"), make("B")
        f.set_left(a, b)
        assert f.get_left(a) is b

    def test_set_and_get_right(self) -> None:
        f = Formation()
        a, b = make("A"), make("B")
        f.set_right(a, b)
        assert f.get_right(a) is b

    def test_adjacent_both_sides(self) -> None:
        f = Formation()
        a, b, c = make("A"), make("B"), make("C")
        f.set_left(b, a)
        f.set_right(b, c)
        assert f.adjacent(b) == [a, c]

    def test_adjacent_left_only(self) -> None:
        f = Formation()
        a, b = make("A"), make("B")
        f.set_left(b, a)
        assert f.adjacent(b) == [a]

    def test_adjacent_right_only(self) -> None:
        f = Formation()
        a, b = make("A"), make("B")
        f.set_right(a, b)
        assert f.adjacent(a) == [b]

    def test_clear_neighbor_to_none(self) -> None:
        """Setting neighbor to None clears it."""
        f = Formation()
        a, b = make("A"), make("B")
        f.set_left(a, b)
        f.set_left(a, None)
        assert f.get_left(a) is None
        assert f.adjacent(a) == []


class TestFormationDeath:
    """Tests for Formation.death() — base unlinking."""

    def test_relinks_linear_neighbors(self) -> None:
        """A-B-C linear: B dies, A and C become
        neighbors."""
        f = Formation()
        a, b, c = make("A"), make("B"), make("C")
        f.set_right(a, b)
        f.set_left(b, a)
        f.set_right(b, c)
        f.set_left(c, b)
        f.death(b)
        assert f.get_right(a) is c
        assert f.get_left(c) is a

    def test_ring_of_three_becomes_pair(self) -> None:
        f = Formation()
        a, b, c = make("A"), make("B"), make("C")
        f.set_left(a, c)
        f.set_right(a, b)
        f.set_left(b, a)
        f.set_right(b, c)
        f.set_left(c, b)
        f.set_right(c, a)
        f.death(b)
        assert f.get_right(a) is c
        assert f.get_left(a) is c
        assert f.get_right(c) is a
        assert f.get_left(c) is a

    def test_ring_of_two_leaves_solo(self) -> None:
        f = Formation()
        a, b = make("A"), make("B")
        f.set_left(a, b)
        f.set_right(a, b)
        f.set_left(b, a)
        f.set_right(b, a)
        f.death(b)
        assert f.get_right(a) is None
        assert f.get_left(a) is None

    def test_removes_from_enemy_attackable(self) -> None:
        f = Formation()
        a, b = make("A"), make("B")
        a.attackable.add(b)
        b.attackable.add(a)
        f.death(b)
        assert b not in a.attackable

    def test_multiple_enemies_cleaned(self) -> None:
        f = Formation()
        a, b, c = make("A"), make("B"), make("C")
        a.attackable.add(c)
        b.attackable.add(c)
        c.attackable = {a, b}
        f.death(c)
        assert c not in a.attackable
        assert c not in b.attackable

    def test_no_neighbors_no_crash(self) -> None:
        """Dying with no links or enemies is fine."""
        f = Formation()
        f.death(make())

    def test_no_neighbors_still_cleans_attackable(self) -> None:
        f = Formation()
        a, b = make("A"), make("B")
        a.attackable.add(b)
        b.attackable.add(a)
        f.death(b)
        assert b not in a.attackable


# -----------------------------------------------------------
# Formation: link helper
# -----------------------------------------------------------


class TestFormationLink:
    """Tests for Formation.link() — adjacency setup."""

    def test_circular_three(self) -> None:
        """A→B→C→A ring."""
        f = Formation()
        a, b, c = make("A"), make("B"), make("C")
        f.link([a, b, c], circular=True)
        assert f.get_right(a) is b
        assert f.get_right(b) is c
        assert f.get_right(c) is a
        assert f.get_left(a) is c
        assert f.get_left(b) is a
        assert f.get_left(c) is b

    def test_linear_three(self) -> None:
        """A→B→C open ends."""
        f = Formation()
        a, b, c = make("A"), make("B"), make("C")
        f.link([a, b, c], circular=False)
        assert f.get_right(a) is b
        assert f.get_right(b) is c
        assert f.get_right(c) is None
        assert f.get_left(a) is None
        assert f.get_left(b) is a
        assert f.get_left(c) is b

    def test_single_gets_no_links(self) -> None:
        f = Formation()
        a = make("A")
        f.link([a], circular=True)
        assert f.get_left(a) is None
        assert f.get_right(a) is None

    def test_circular_two(self) -> None:
        """Two members point to each other."""
        f = Formation()
        a, b = make("A"), make("B")
        f.link([a, b], circular=True)
        assert f.get_right(a) is b
        assert f.get_left(a) is b
        assert f.get_right(b) is a
        assert f.get_left(b) is a


# -----------------------------------------------------------
# Line: deploy
# -----------------------------------------------------------


class TestLineDeploy:
    """Tests for Line deployment — attackable sets from positioning."""

    def test_3v2_attackable(self) -> None:
        """A: 0,1,2  B: 0.5,1.5 — verify exact attackable sets."""
        a = [make(f"A{i}") for i in range(3)]
        b = [make(f"B{j}") for j in range(2)]
        Line(a, b)
        # A0(pos 0) vs B0(pos 0.5): |0-0.5|=0.5 ≤ 1 → yes
        assert b[0] in a[0].attackable
        # A0 vs B1(pos 1.5): |0-1.5|=1.5 > 1 → no
        assert b[1] not in a[0].attackable
        # A1(pos 1) vs B0(pos 0.5): |1-0.5|=0.5 ≤ 1 → yes
        assert b[0] in a[1].attackable
        # A1 vs B1(pos 1.5): |1-1.5|=0.5 ≤ 1 → yes
        assert b[1] in a[1].attackable
        # A2(pos 2) vs B0(pos 0.5): |2-0.5|=1.5 > 1 → no
        assert b[0] not in a[2].attackable
        # A2 vs B1(pos 1.5): |2-1.5|=0.5 ≤ 1 → yes
        assert b[1] in a[2].attackable

    def test_3v3_attackable(self) -> None:
        """A: 0,1,2  B: 0,1,2 — equal sizes, same positions."""
        a = [make(f"A{i}") for i in range(3)]
        b = [make(f"B{j}") for j in range(3)]
        Line(a, b)
        # A0 vs B0: |0-0|=0 ≤ 1 → yes
        assert b[0] in a[0].attackable
        # A0 vs B1: |0-1|=1 ≤ 1 → yes
        assert b[1] in a[0].attackable
        # A0 vs B2: |0-2|=2 > 1 → no
        assert b[2] not in a[0].attackable
        # A1 vs all B: |1-0|=1, |1-1|=0, |1-2|=1 → all yes
        assert a[1].attackable == set(b)
        # A2 vs B0: |2-0|=2 > 1 → no
        assert b[0] not in a[2].attackable
        # A2 vs B1,B2: yes
        assert b[1] in a[2].attackable
        assert b[2] in a[2].attackable

    def test_1v1_attackable(self) -> None:
        """Simplest: each attacks the other."""
        a = [make("A")]
        b = [make("B")]
        Line(a, b)
        assert a[0].attackable == {b[0]}
        assert b[0].attackable == {a[0]}

    def test_2v1_attackable(self) -> None:
        """A: 0,1  B: 0.5 — both A attack B."""
        a = [make("A0"), make("A1")]
        b = [make("B0")]
        Line(a, b)
        assert b[0] in a[0].attackable
        assert b[0] in a[1].attackable
        assert a[0] in b[0].attackable
        assert a[1] in b[0].attackable

    def test_4v2_attackable(self) -> None:
        """A: 0,1,2,3  B: 1,2 (offset=1)."""
        a = [make(f"A{i}") for i in range(4)]
        b = [make(f"B{j}") for j in range(2)]
        Line(a, b)
        # B positions: 0+1=1, 1+1=2
        # A0(0) vs B0(1): |0-1|=1 ≤ 1 → yes
        assert b[0] in a[0].attackable
        # A0(0) vs B1(2): |0-2|=2 > 1 → no
        assert b[1] not in a[0].attackable
        # A1(1) vs B0(1): 0 → yes; B1(2): 1 → yes
        assert a[1].attackable == set(b)
        # A2(2) vs B0(1): 1 → yes; B1(2): 0 → yes
        assert a[2].attackable == set(b)
        # A3(3) vs B0(1): 2 → no; B1(2): 1 → yes
        assert b[0] not in a[3].attackable
        assert b[1] in a[3].attackable

    def test_symmetry(self) -> None:
        """If A can attack B then B can attack A."""
        a = [make(f"A{i}") for i in range(3)]
        b = [make(f"B{j}") for j in range(2)]
        Line(a, b)
        for ca in a:
            for cb in b:
                if cb in ca.attackable:
                    assert ca in cb.attackable
                else:
                    assert ca not in cb.attackable

    def test_same_side_adjacency_3(self) -> None:
        """In a 3-person side, middle has 2 neighbors, ends have 1."""
        a = [make(f"A{i}") for i in range(3)]
        b = [make("B")]
        f = Line(a, b)
        assert f.adjacent(a[0]) == [a[1]]
        assert set(f.adjacent(a[1])) == {a[0], a[2]}
        assert f.adjacent(a[2]) == [a[1]]

    def test_no_cross_side_adjacency(self) -> None:
        """Enemies are never adjacent (only same-side allies)."""
        a = [make(f"A{i}") for i in range(3)]
        b = [make(f"B{j}") for j in range(3)]
        f = Line(a, b)
        for ca in a:
            for cb in b:
                assert cb not in f.adjacent(ca)
                assert ca not in f.adjacent(cb)

    def test_single_combatant_per_side_no_adjacency(self) -> None:
        """1v1: neither has adjacent allies."""
        a = [make("A")]
        b = [make("B")]
        f = Line(a, b)
        assert f.adjacent(a[0]) == []
        assert f.adjacent(b[0]) == []


# -----------------------------------------------------------
# Line: properties
# -----------------------------------------------------------


class TestLineProperties:
    """Tests for Line.combatants and Line.one_side_finished."""

    def test_combatants_includes_both_sides(self) -> None:
        a = [make("A0"), make("A1")]
        b = [make("B0"), make("B1"), make("B2")]
        f = Line(a, b)
        assert set(f.combatants) == set(a + b)

    def test_not_finished_initially(self) -> None:
        f = Line([make()], [make()])
        assert f.one_side_finished is False

    def test_finished_when_side_a_empty(self) -> None:
        f = Line([make()], [make()])
        f.side_a.clear()
        assert f.one_side_finished is True

    def test_finished_when_side_b_empty(self) -> None:
        f = Line([make()], [make()])
        f.side_b.clear()
        assert f.one_side_finished is True


# -----------------------------------------------------------
# Line: death
# -----------------------------------------------------------


class TestLineDeath:
    """Tests for Line.death() — restructuring after deaths."""

    def test_death_removes_from_side(self) -> None:
        a = [make("A0"), make("A1"), make("A2")]
        b = [make("B0"), make("B1")]
        f = Line(a, b)
        f.death(a[1])
        assert a[1] not in f.side_a

    def test_3v2_kill_center_becomes_2v2(self) -> None:
        """3v2 → kill A1 → 2v2, positions recalculated."""
        a = [make("A0"), make("A1"), make("A2")]
        b = [make("B0"), make("B1")]
        f = Line(a, b)
        f.death(a[1])
        # Now 2v2: A: 0,1  B: 0,1 — everyone attacks everyone
        remaining_a = [a[0], a[2]]
        for ca in remaining_a:
            assert ca.attackable == set(b)
        for cb in b:
            assert cb.attackable == set(remaining_a)

    def test_sequential_deaths(self) -> None:
        """Kill combatants one by one."""
        a = [make("A0"), make("A1"), make("A2")]
        b = [make("B0"), make("B1")]
        f = Line(a, b)
        f.death(a[0])
        assert len(f.side_a) == 2
        assert not f.one_side_finished
        f.death(a[1])
        assert len(f.side_a) == 1
        assert not f.one_side_finished

    def test_last_on_side_death(self) -> None:
        """Killing the last combatant on a side → one_side_finished."""
        a = [make("A")]
        b = [make("B")]
        f = Line(a, b)
        f.death(a[0])
        assert f.one_side_finished is True
        assert f.side_a == []

    def test_last_on_side_no_deploy_crash(self) -> None:
        """When one side is emptied, deploy() is not called (no crash)."""
        a = [make("A")]
        b = [make("B0"), make("B1")]
        f = Line(a, b)
        f.death(a[0])
        assert f.one_side_finished is True

    def test_death_cleans_attackable(self) -> None:
        """Dead combatant is removed from all enemies' attackable."""
        a = [make("A0"), make("A1")]
        b = [make("B0"), make("B1")]
        f = Line(a, b)
        f.death(a[0])
        for cb in b:
            assert a[0] not in cb.attackable

    def test_death_from_side_b(self) -> None:
        """Death on side_b works correctly."""
        a = [make("A0"), make("A1")]
        b = [make("B0"), make("B1")]
        f = Line(a, b)
        f.death(b[0])
        assert b[0] not in f.side_b
        for ca in a:
            assert b[0] not in ca.attackable


# -----------------------------------------------------------
# Surround: properties
# -----------------------------------------------------------


class TestSurroundProperties:
    """Basic construction and properties."""

    def test_combatants_includes_both_sides(self) -> None:
        a = [make("A")]
        b = [make("B1"), make("B2")]
        s = Surround(a, b)
        assert set(s.combatants) == set(a + b)

    def test_not_finished_initially(self) -> None:
        s = Surround([make()], [make()])
        assert s.one_side_finished is False

    def test_finished_when_side_a_empty(self) -> None:
        s = Surround([make()], [make()])
        s.side_a.clear()
        assert s.one_side_finished is True

    def test_finished_when_side_b_empty(self) -> None:
        s = Surround([make()], [make()])
        s.side_b.clear()
        assert s.one_side_finished is True

    def test_is_surrounding_1v2(self) -> None:
        s = Surround([make()], [make(), make()])
        assert s.is_surrounding is True

    def test_not_surrounding_2v2(self) -> None:
        s = Surround([make(), make()], [make(), make()])
        assert s.is_surrounding is False

    def test_not_surrounding_1v1(self) -> None:
        s = Surround([make()], [make()])
        assert s.is_surrounding is False


# -----------------------------------------------------------
# Surround: deploy (encirclement mode)
# -----------------------------------------------------------


class TestSurroundDeploy:
    """Tests for Surround deployment in surround mode."""

    def test_all_outer_attack_inner(self) -> None:
        inner = [make("I")]
        outer = [make("O1"), make("O2"), make("O3")]
        Surround(inner, outer)
        for o in outer:
            assert inner[0] in o.attackable

    def test_inner_attacks_all_outer(self) -> None:
        inner = [make("I")]
        outer = [make("O1"), make("O2"), make("O3")]
        Surround(inner, outer)
        assert inner[0].attackable == set(outer)

    def test_outer_forms_ring(self) -> None:
        inner = [make("I")]
        outer = [make("O1"), make("O2"), make("O3")]
        s = Surround(inner, outer)
        start = outer[0]
        visited = [start]
        curr = s.get_right(start)
        while curr is not start:
            visited.append(curr)
            curr = s.get_right(curr)
        assert set(visited) == set(outer)

    def test_outer_ring_two_members(self) -> None:
        inner = [make("I")]
        outer = [make("O1"), make("O2")]
        s = Surround(inner, outer)
        assert s.get_right(outer[0]) is outer[1]
        assert s.get_right(outer[1]) is outer[0]
        assert s.get_left(outer[0]) is outer[1]
        assert s.get_left(outer[1]) is outer[0]

    def test_inner_no_adjacency(self) -> None:
        """Surrounded combatant has no same-side neighbors."""
        inner = [make("I")]
        outer = [make("O1"), make("O2")]
        s = Surround(inner, outer)
        assert s.get_left(inner[0]) is None
        assert s.get_right(inner[0]) is None

    def test_one_vs_one(self) -> None:
        """1v1: no surround, falls through to line."""
        inner = [make("I")]
        outer = [make("O")]
        s = Surround(inner, outer)
        assert inner[0].attackable == {outer[0]}
        assert outer[0].attackable == {inner[0]}
        assert s.is_surrounding is False

    def test_one_vs_five(self) -> None:
        """Classic surrounded: 1 vs many."""
        inner = [make("I")]
        outer = [make(f"O{i}") for i in range(5)]
        s = Surround(inner, outer)
        assert inner[0].attackable == set(outer)
        for o in outer:
            assert o.attackable == {inner[0]}
        assert s.is_surrounding is True

    def test_outer_dont_attack_each_other(self) -> None:
        """Outer combatants on the same side can't
        attack each other."""
        inner = [make("I")]
        outer = [make("O1"), make("O2"), make("O3")]
        Surround(inner, outer)
        for o in outer:
            for other in outer:
                if other is not o:
                    assert other not in o.attackable

    def test_2v2_is_line_not_surround(self) -> None:
        """Even sides use line formation, not surround."""
        a = [make("A0"), make("A1")]
        b = [make("B0"), make("B1")]
        s = Surround(a, b)
        assert s.is_surrounding is False
        # Line: 2v2, all attack each other
        for ca in a:
            assert ca.attackable == set(b)

    def test_2v1_surrounds_solo_side(self) -> None:
        """2v1: the solo side_b combatant is surrounded."""
        a = [make("A0"), make("A1")]
        b = [make("B0")]
        s = Surround(a, b)
        assert s.is_surrounding is True
        assert s._surrounded is b[0]


# -----------------------------------------------------------
# Surround: transitions
# -----------------------------------------------------------


class TestSurroundTransitions:
    """Tests for mode transitions between line and surround."""

    def test_1v2_starts_surrounded(self) -> None:
        s = Surround([make("I")], [make("O1"), make("O2")])
        assert s.is_surrounding is True

    def test_2v2_starts_as_line(self) -> None:
        s = Surround([make("A0"), make("A1")], [make("B0"), make("B1")])
        assert s.is_surrounding is False

    def test_3v2_kill_2_triggers_surround(self) -> None:
        """3v2 → kill 2 from side_a → 1v2 → triggers surround."""
        a = [make("A0"), make("A1"), make("A2")]
        b = [make("B0"), make("B1")]
        s = Surround(a, b)
        assert s.is_surrounding is False
        s.death(a[0])
        assert s.is_surrounding is False  # 2v2 → line
        s.death(a[1])
        assert s.is_surrounding is True  # 1v2 → surround
        assert s._surrounded is a[2]

    def test_1v3_kill_2_outer_drops_to_line(self) -> None:
        """1v3 (surround) → kill 2 outer → 1v1 → line."""
        a = [make("I")]
        b = [make("O1"), make("O2"), make("O3")]
        s = Surround(a, b)
        assert s.is_surrounding is True
        s.death(b[0])
        assert s.is_surrounding is True  # 1v2 → still surrounded
        s.death(b[1])
        assert s.is_surrounding is False  # 1v1 → line

    def test_1v5_kill_1_outer_stays_surround(self) -> None:
        """1v5 → kill 1 outer → 1v4 → still surrounded."""
        a = [make("I")]
        b = [make(f"O{i}") for i in range(5)]
        s = Surround(a, b)
        assert s.is_surrounding is True
        s.death(b[2])
        assert s.is_surrounding is True
        assert len(s.side_b) == 4

    def test_inner_dies_no_deploy(self) -> None:
        """Inner dies → side empty → one_side_finished, no crash."""
        i = make("I")
        o1, o2 = make("O1"), make("O2")
        s = Surround([i], [o1, o2])
        s.death(i)
        assert s.one_side_finished is True
        assert s.side_a == []


# -----------------------------------------------------------
# Surround: bonuses
# -----------------------------------------------------------


ATTACK_ROLL_TYPES = (
    "attack", "counterattack", "double_attack",
    "feint", "iaijutsu", "lunge",
)


class TestSurroundBonuses:
    """Tests for surround attack bonuses."""

    def test_1v2_bonus_is_15(self) -> None:
        """1v2 → bonus = 5 * (1 + 2) = 15."""
        inner = [make("I")]
        outer = [make("O1"), make("O2")]
        Surround(inner, outer)
        for o in outer:
            for rt in ATTACK_ROLL_TYPES:
                assert o.always[rt] >= 15

    def test_1v6_bonus_is_35(self) -> None:
        """1v6 → bonus = 5 * (1 + 6) = 35."""
        inner = [make("I")]
        outer = [make(f"O{i}") for i in range(6)]
        Surround(inner, outer)
        for o in outer:
            for rt in ATTACK_ROLL_TYPES:
                assert o.always[rt] >= 35

    def test_inner_gets_no_bonus(self) -> None:
        """The surrounded combatant gets no bonus."""
        inner = [make("I")]
        outer = [make("O1"), make("O2")]
        Surround(inner, outer)
        for rt in ATTACK_ROLL_TYPES:
            assert inner[0].always[rt] == 0

    def test_bonus_removed_on_transition_to_line(self) -> None:
        """1v2 surround → kill 1 outer → 1v1 line: bonus removed."""
        inner = [make("I")]
        o1, o2 = make("O1"), make("O2")
        s = Surround(inner, [o1, o2])
        # Verify bonus is applied
        for rt in ATTACK_ROLL_TYPES:
            assert o1.always[rt] >= 15
        s.death(o2)
        # Now 1v1 line — bonus should be removed
        for rt in ATTACK_ROLL_TYPES:
            assert o1.always[rt] == 0

    def test_bonus_not_stacked_on_redeploy(self) -> None:
        """Killing an outer re-deploys; verify bonus isn't doubled."""
        inner = [make("I")]
        outer = [make(f"O{i}") for i in range(4)]
        s = Surround(inner, outer)
        bonus_before = outer[0].always["attack"]
        s.death(outer[1])
        bonus_after = outer[0].always["attack"]
        # New bonus = 5*(1+3) = 20, old was 5*(1+4) = 25
        assert bonus_after == 20
        assert bonus_after < bonus_before

    def test_bonus_decreases_when_outer_shrinks(self) -> None:
        """1v3 → kill 1 outer → 1v2: bonus decreases."""
        inner = [make("I")]
        outer = [make("O1"), make("O2"), make("O3")]
        s = Surround(inner, outer)
        # 1v3: bonus = 5*(1+3) = 20
        for o in outer:
            for rt in ATTACK_ROLL_TYPES:
                assert o.always[rt] >= 20
        s.death(outer[0])
        # 1v2: bonus = 5*(1+2) = 15
        for o in [outer[1], outer[2]]:
            for rt in ATTACK_ROLL_TYPES:
                assert o.always[rt] >= 15
                assert o.always[rt] < 20


# -----------------------------------------------------------
# Surround: death
# -----------------------------------------------------------


class TestSurroundDeath:
    """Tests for death handling in Surround."""

    def test_removed_from_side_list(self) -> None:
        inner = [make("I")]
        o1, o2, o3 = make("O1"), make("O2"), make("O3")
        s = Surround(inner, [o1, o2, o3])
        s.death(o2)
        assert o2 not in s.side_b

    def test_removed_from_attackable(self) -> None:
        inner = [make("I")]
        o1, o2, o3 = make("O1"), make("O2"), make("O3")
        s = Surround(inner, [o1, o2, o3])
        s.death(o2)
        assert o2 not in inner[0].attackable

    def test_inner_still_has_remaining_enemies(self) -> None:
        inner = [make("I")]
        o1, o2, o3 = make("O1"), make("O2"), make("O3")
        s = Surround(inner, [o1, o2, o3])
        s.death(o2)
        assert inner[0].attackable == {o1, o3}

    def test_sequential_outer_deaths(self) -> None:
        """Kill outer one by one."""
        inner = [make("I")]
        o1, o2, o3 = make("O1"), make("O2"), make("O3")
        s = Surround(inner, [o1, o2, o3])
        s.death(o1)
        assert inner[0].attackable == {o2, o3}
        s.death(o2)
        assert inner[0].attackable == {o3}
        s.death(o3)
        assert inner[0].attackable == set()

    def test_last_outer_dies(self) -> None:
        inner = [make("I")]
        outer = [make("O")]
        s = Surround(inner, outer)
        s.death(outer[0])
        assert inner[0].attackable == set()
        assert s.side_b == []

    def test_inner_death_1v1(self) -> None:
        i, o = make("I"), make("O")
        s = Surround([i], [o])
        s.death(i)
        assert s.side_a == []
        assert i not in o.attackable

    def test_inner_death_1v2(self) -> None:
        i = make("I")
        o1, o2 = make("O1"), make("O2")
        s = Surround([i], [o1, o2])
        s.death(i)
        assert s.side_a == []
        assert i not in o1.attackable
        assert i not in o2.attackable

    def test_inner_death_1v3(self) -> None:
        i = make("I")
        o1, o2, o3 = make("O1"), make("O2"), make("O3")
        s = Surround([i], [o1, o2, o3])
        s.death(i)
        assert s.side_a == []
        for o in [o1, o2, o3]:
            assert i not in o.attackable

    def test_one_side_finished_after_inner_death(self) -> None:
        i = make("I")
        o1, o2 = make("O1"), make("O2")
        s = Surround([i], [o1, o2])
        s.death(i)
        assert s.one_side_finished is True
