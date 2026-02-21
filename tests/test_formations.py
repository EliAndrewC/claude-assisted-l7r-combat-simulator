"""Tests for formation logic: adjacency, deployment, and death.

Covers Formation base class (adjacency, death unlinking),
Surround deployment (single-inner and multi-inner paths),
link/engage/surround helpers, leftmost, and death handling.

Known bugs documented with xfail/skip:
- Multi-inner deploy: first batch of outer never engaged,
  link_outer() crashes on empty attackable intersections.
- Inner death: while loop never advances curr/right,
  causing infinite loop when 2+ outer exist.
"""

import pytest

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


def raw_surround(
    inner: list[Combatant], outer: list[Combatant],
) -> Surround:
    """Create a Surround bypassing __init__/deploy.

    Useful for testing individual methods in isolation
    without triggering the full deployment sequence.
    """
    s = object.__new__(Surround)
    Formation.__init__(s)
    s.inner = list(inner)
    s.outer = list(outer)
    return s


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


class TestLine:
    """Line is a stub — just verify it exists."""

    def test_is_formation(self) -> None:
        assert isinstance(Line(), Formation)


# -----------------------------------------------------------
# Surround: link helper
# -----------------------------------------------------------


class TestSurroundLink:
    """Tests for Surround.link() — adjacency setup."""

    def test_circular_three(self) -> None:
        """A→B→C→A ring."""
        s = raw_surround([], [])
        a, b, c = make("A"), make("B"), make("C")
        s.link([a, b, c], circular=True)
        assert s.get_right(a) is b
        assert s.get_right(b) is c
        assert s.get_right(c) is a
        assert s.get_left(a) is c
        assert s.get_left(b) is a
        assert s.get_left(c) is b

    def test_linear_three(self) -> None:
        """A→B→C open ends."""
        s = raw_surround([], [])
        a, b, c = make("A"), make("B"), make("C")
        s.link([a, b, c], circular=False)
        assert s.get_right(a) is b
        assert s.get_right(b) is c
        assert s.get_right(c) is None
        assert s.get_left(a) is None
        assert s.get_left(b) is a
        assert s.get_left(c) is b

    def test_single_gets_no_links(self) -> None:
        s = raw_surround([], [])
        a = make("A")
        s.link([a], circular=True)
        assert s.get_left(a) is None
        assert s.get_right(a) is None

    def test_circular_two(self) -> None:
        """Two members point to each other."""
        s = raw_surround([], [])
        a, b = make("A"), make("B")
        s.link([a, b], circular=True)
        assert s.get_right(a) is b
        assert s.get_left(a) is b
        assert s.get_right(b) is a
        assert s.get_left(b) is a


# -----------------------------------------------------------
# Surround: properties
# -----------------------------------------------------------


class TestSurroundProperties:
    """Basic construction and properties."""

    def test_combatants_includes_both_sides(self) -> None:
        inner = [make("I")]
        outer = [make("O1"), make("O2")]
        s = Surround(inner, outer)
        assert set(s.combatants) == set(inner + outer)

    def test_not_finished_initially(self) -> None:
        s = Surround([make()], [make()])
        assert s.one_side_finished is False

    def test_finished_when_inner_empty(self) -> None:
        s = Surround([make()], [make()])
        s.inner.clear()
        assert s.one_side_finished is True

    def test_finished_when_outer_empty(self) -> None:
        s = Surround([make()], [make()])
        s.outer.clear()
        assert s.one_side_finished is True

    def test_inner_larger_than_outer_asserts(self) -> None:
        with pytest.raises(AssertionError):
            Surround([make(), make()], [make()])


# -----------------------------------------------------------
# Surround: inner_pairs
# -----------------------------------------------------------


class TestSurroundInnerPairs:
    """Tests for inner_pairs() — circular pairing."""

    def test_single_inner_pairs_with_self(self) -> None:
        """[I] → [[I, I]]."""
        i = make("I")
        s = Surround([i], [make()])
        pairs = s.inner_pairs()
        assert len(pairs) == 1
        assert pairs[0] == [i, i]

    def test_two_inner(self) -> None:
        """[I1, I2] → [[I2, I1], [I1, I2]]."""
        i1, i2 = make("I1"), make("I2")
        s = raw_surround([i1, i2], [])
        pairs = s.inner_pairs()
        assert len(pairs) == 2
        assert pairs[0] == [i2, i1]
        assert pairs[1] == [i1, i2]

    def test_three_inner(self) -> None:
        """[I1, I2, I3] → [[I3, I1], [I1, I2],
        [I2, I3]]."""
        i1, i2, i3 = make("I1"), make("I2"), make("I3")
        s = raw_surround([i1, i2, i3], [])
        pairs = s.inner_pairs()
        assert len(pairs) == 3
        assert pairs[0] == [i3, i1]
        assert pairs[1] == [i1, i2]
        assert pairs[2] == [i2, i3]

    def test_four_inner(self) -> None:
        """Number of pairs equals number of inner."""
        inners = [make(f"I{i}") for i in range(4)]
        s = raw_surround(inners, [])
        assert len(s.inner_pairs()) == 4


# -----------------------------------------------------------
# Surround: engage
# -----------------------------------------------------------


class TestSurroundEngage:
    """Tests for engage() — mutual attackable setup."""

    def test_engage_adds_mutual_attackable(self) -> None:
        s = raw_surround([], [])
        i1, i2, o = make("I1"), make("I2"), make("O")
        s.engage([i1, i2], o)
        assert o in i1.attackable
        assert o in i2.attackable
        assert i1 in o.attackable
        assert i2 in o.attackable

    def test_engage_idempotent(self) -> None:
        """Engaging the same outer twice doesn't
        duplicate."""
        s = raw_surround([], [])
        i1, i2, o = make("I1"), make("I2"), make("O")
        s.engage([i1, i2], o)
        s.engage([i1, i2], o)
        assert len(i1.attackable) == 1


# -----------------------------------------------------------
# Surround: surround() distribution
# -----------------------------------------------------------


class TestSurroundDistribution:
    """Tests for surround() — excess outer distribution.

    Note: surround() only handles outer[len(pairs):].
    The first len(pairs) outer are supposed to be engaged
    by deploy() separately, but deploy() never does this
    for multi-inner (known bug).
    """

    def test_excess_engaged_with_inner_pairs(self) -> None:
        """Excess outer get attackable assignments."""
        i1, i2, i3 = make("I1"), make("I2"), make("I3")
        outers = [make(f"O{i}") for i in range(6)]
        s = raw_surround([i1, i2, i3], outers)
        s.link([i1, i2, i3], circular=True)
        s.surround()
        # Excess = outers[3:] = O3, O4, O5
        for o in outers[3:]:
            assert o.attackable, (
                f"{o.name} should have enemies"
            )

    def test_first_batch_not_engaged_by_surround(
        self,
    ) -> None:
        """surround() skips the first len(pairs) outer.

        This is by design — deploy() should handle them
        separately. But deploy() currently doesn't for
        multi-inner (separate bug).
        """
        i1, i2 = make("I1"), make("I2")
        outers = [make(f"O{i}") for i in range(4)]
        s = raw_surround([i1, i2], outers)
        s.link([i1, i2], circular=True)
        s.surround()
        # First 2 outer (len(pairs)=2) are untouched
        assert not outers[0].attackable
        assert not outers[1].attackable
        # Excess outer are engaged
        assert outers[2].attackable
        assert outers[3].attackable

    def test_even_distribution_three_inner(self) -> None:
        """With 3 inner and 6 outer, each inner pair
        gets exactly one excess outer."""
        i1, i2, i3 = make("I1"), make("I2"), make("I3")
        outers = [make(f"O{i}") for i in range(6)]
        s = raw_surround([i1, i2, i3], outers)
        s.link([i1, i2, i3], circular=True)
        s.surround()
        # Each of the 3 excess should be engaged with
        # a different pair
        engaged = [o for o in outers[3:] if o.attackable]
        assert len(engaged) == 3


# -----------------------------------------------------------
# Surround: deploy (single inner)
# -----------------------------------------------------------


class TestSurroundDeploySingleInner:
    """Tests for deployment with a single inner combatant.

    This is the common and working path.
    """

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
        # Walk the ring rightward
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

    def test_single_inner_no_adjacency(self) -> None:
        """One inner has no left/right neighbors."""
        inner = [make("I")]
        outer = [make("O1"), make("O2")]
        s = Surround(inner, outer)
        assert s.get_left(inner[0]) is None
        assert s.get_right(inner[0]) is None

    def test_one_vs_one(self) -> None:
        """Minimum formation: 1 inner, 1 outer."""
        inner = [make("I")]
        outer = [make("O")]
        Surround(inner, outer)
        assert inner[0].attackable == {outer[0]}
        assert outer[0].attackable == {inner[0]}

    def test_one_vs_five(self) -> None:
        """Classic surrounded: 1 vs many."""
        inner = [make("I")]
        outer = [make(f"O{i}") for i in range(5)]
        Surround(inner, outer)
        assert inner[0].attackable == set(outer)
        for o in outer:
            assert o.attackable == {inner[0]}

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


# -----------------------------------------------------------
# Surround: deploy (multi-inner) — known bugs
# -----------------------------------------------------------


class TestSurroundDeployMultiInner:
    """Multi-inner deployment has known bugs.

    deploy() never calls engage() for the first
    len(pairs) outer combatants. Only excess outer
    (via surround()) get attackable assignments.
    Then link_outer() crashes because it relies on
    non-empty attackable intersections between inner
    pairs.
    """

    @pytest.mark.xfail(
        reason="First batch of outer never engaged; "
        "link_outer crashes on empty intersections",
        raises=IndexError,
        strict=True,
    )
    def test_two_inner_two_outer_crashes(self) -> None:
        """Minimum multi-inner case crashes."""
        Surround(
            [make("I1"), make("I2")],
            [make("O1"), make("O2")],
        )

    @pytest.mark.xfail(
        reason="First batch of outer never engaged; "
        "link_outer crashes on empty intersections",
        raises=IndexError,
        strict=True,
    )
    def test_three_inner_five_outer_crashes(self) -> None:
        """Even with excess outer, link_outer crashes
        because some inner pairs share no enemies."""
        Surround(
            [make(f"I{i}") for i in range(3)],
            [make(f"O{i}") for i in range(5)],
        )


# -----------------------------------------------------------
# Surround: leftmost
# -----------------------------------------------------------


class TestSurroundLeftmost:
    """Tests for leftmost() — finding the leftmost
    contiguous enemy of a corpse."""

    def test_single_outer_returns_it(self) -> None:
        """With one outer, leftmost returns that outer."""
        inner = [make("I")]
        outer = [make("O")]
        s = Surround(inner, outer)
        assert s.leftmost(inner[0]) is outer[0]

    def test_walks_full_ring(self) -> None:
        """With all outer as enemies, leftmost walks
        the ring and returns a valid outer member."""
        inner = [make("I")]
        outer = [make("O1"), make("O2"), make("O3")]
        s = Surround(inner, outer)
        result = s.leftmost(inner[0])
        assert result in outer

    def test_partial_enemies(self) -> None:
        """When only some outer are enemies, leftmost
        finds the left boundary."""
        s = raw_surround([], [])
        a, b, c, d = (
            make("A"), make("B"),
            make("C"), make("D"),
        )
        # Ring: A→B→C→D→A
        s.link([a, b, c, d], circular=True)
        # Corpse's enemies are B and C (contiguous)
        corpse = make("corpse")
        corpse.attackable = {b, c}
        result = s.leftmost(corpse)
        # Should be B (leftmost of the contiguous B,C)
        assert result is b


# -----------------------------------------------------------
# Surround: death (outer)
# -----------------------------------------------------------


class TestSurroundDeathOuter:
    """Tests for when an outer combatant dies."""

    def test_removed_from_outer_list(self) -> None:
        inner = [make("I")]
        o1, o2, o3 = make("O1"), make("O2"), make("O3")
        s = Surround(inner, [o1, o2, o3])
        s.death(o2)
        assert o2 not in s.outer

    def test_removed_from_inner_attackable(self) -> None:
        inner = [make("I")]
        o1, o2, o3 = make("O1"), make("O2"), make("O3")
        s = Surround(inner, [o1, o2, o3])
        s.death(o2)
        assert o2 not in inner[0].attackable

    def test_neighbors_relinked(self) -> None:
        inner = [make("I")]
        o1, o2, o3 = make("O1"), make("O2"), make("O3")
        s = Surround(inner, [o1, o2, o3])
        s.death(o2)
        assert s.get_right(o1) is o3
        assert s.get_left(o3) is o1

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

    def test_ring_shrinks_after_death(self) -> None:
        """After killing middle of 3, remaining 2 form
        a pair."""
        inner = [make("I")]
        o1, o2, o3 = make("O1"), make("O2"), make("O3")
        s = Surround(inner, [o1, o2, o3])
        s.death(o2)
        assert s.get_right(o1) is o3
        assert s.get_left(o1) is o3
        assert s.get_right(o3) is o1
        assert s.get_left(o3) is o1

    def test_last_outer_dies(self) -> None:
        """When the sole outer dies, inner has no
        enemies."""
        inner = [make("I")]
        outer = [make("O")]
        s = Surround(inner, outer)
        s.death(outer[0])
        assert inner[0].attackable == set()
        assert s.outer == []


# -----------------------------------------------------------
# Surround: death (inner) — partially broken
# -----------------------------------------------------------


class TestSurroundDeathInner:
    """Tests for when an inner combatant dies.

    The 1v1 case works because the while loop condition
    is never True (single outer has no right neighbor
    in its attackable). With 2+ outer, the loop hangs.
    """

    def test_one_vs_one_inner_death_works(self) -> None:
        """1v1: inner dies, outer list intact, inner
        removed."""
        i, o = make("I"), make("O")
        s = Surround([i], [o])
        s.death(i)
        assert s.inner == []
        # Outer's attackable was cleaned by
        # Formation.death
        assert i not in o.attackable

    def test_inner_death_bug_preconditions(self) -> None:
        """Verify the infinite loop bug preconditions.

        With 1 inner and 3 outer, after Formation.death:
        - corpse.attackable still has all outer (not
          cleared by Formation.death)
        - get_right of leftmost enemy is in
          corpse.attackable
        - The while loop would run forever because
          neither curr nor right advance.

        We call Formation.death manually to verify
        preconditions without triggering the hang.
        """
        inner = [make("I")]
        o1, o2, o3 = make("O1"), make("O2"), make("O3")
        s = Surround(inner, [o1, o2, o3])

        corpse = inner[0]
        # corpse.attackable = {o1, o2, o3}
        assert corpse.attackable == {o1, o2, o3}

        # Call only the base Formation.death
        Formation.death(s, corpse)

        # corpse.attackable is NOT cleared
        assert corpse.attackable == {o1, o2, o3}

        # Enemies have been cleaned
        for o in [o1, o2, o3]:
            assert corpse not in o.attackable

        # The leftmost walk finds an outer member
        s.inner.remove(corpse)
        curr = s.leftmost(corpse)
        right = s.get_right(curr)

        # right is in corpse.attackable — the while
        # loop condition is True and would never
        # terminate because curr/right don't advance
        assert right is not None
        assert right in corpse.attackable

    def test_inner_death_bug_even_with_two_outer(
        self,
    ) -> None:
        """Same bug triggers with just 2 outer.

        In the outer ring of 2 (O1↔O2), leftmost
        returns one, and its right neighbor is the
        other — which is in corpse.attackable.
        """
        inner = [make("I")]
        o1, o2 = make("O1"), make("O2")
        s = Surround(inner, [o1, o2])

        corpse = inner[0]
        Formation.death(s, corpse)
        s.inner.remove(corpse)

        curr = s.leftmost(corpse)
        right = s.get_right(curr)
        assert right in corpse.attackable
