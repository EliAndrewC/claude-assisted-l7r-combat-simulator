r"""
Battlefield formations: how combatants are physically arranged.

Formations determine two things:

1. **Who can attack whom** — the ``attackable`` set on each combatant.
2. **Who is adjacent** — left/right same-side neighbors, used for
   parrying or counterattacking on behalf of allies.

When a combatant dies the formation restructures to fill gaps.

Adjacency data is owned by the Formation — combatants do not store
mutable references to their neighbors.  Instead, ``Combatant.adjacent``
queries back through ``engine.formation``.

Two concrete formations are provided:

**Line** — two sides face each other.  Represents terrain where
surrounding is impossible (back to a wall, narrow corridor, etc.)::

    Side A:   1   2   3        positions 0, 1, 2
    Side B:     4   5          positions 0.5, 1.5

    Attackable pairs (distance <= 1):
      1<->4   2<->4   2<->5   3<->5

**Surround** — extends Line.  When one side drops to a single
combatant against >= 2, the formation switches to encirclement::

    Line mode (2v2):          Surround mode (1v3):

      A0  A1                         O1
       \  /                         / | \
      B0  B1                      O2--I--O3
                                    \ | /
                                     O4

In surround mode every outer combatant can attack the inner (and
vice-versa), the outer group forms an adjacency ring, and each
outer combatant receives an attack bonus of ``+5 * (1 + N)`` where
N is the number of surrounding enemies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from l7r.combatant import Combatant


class Formation:
    """Base class for battlefield formations.

    Owns the adjacency graph (who stands next to whom on the same side)
    and handles the universal death logic shared by all formations:
    unlinking a corpse from its neighbors and removing it from every
    enemy's attackable set.

    Adjacency is a doubly-linked list per side::

        A --- B --- C --- D        (linear, circular=False)
        A --- B --- C --- A        (ring,   circular=True)

    Subclasses (Line, Surround) call ``link()`` to build these chains
    and set up the cross-side ``attackable`` relationships.
    """

    def __init__(self) -> None:
        self._left: dict[Combatant, Combatant | None] = {}
        self._right: dict[Combatant, Combatant | None] = {}

    def get_left(self, c: Combatant) -> Combatant | None:
        """Return the ally to c's left, or None."""
        return self._left.get(c)

    def get_right(self, c: Combatant) -> Combatant | None:
        """Return the ally to c's right, or None."""
        return self._right.get(c)

    def set_left(self, c: Combatant, neighbor: Combatant | None) -> None:
        """Set or clear the ally to c's left."""
        self._left[c] = neighbor

    def set_right(self, c: Combatant, neighbor: Combatant | None) -> None:
        """Set or clear the ally to c's right."""
        self._right[c] = neighbor

    def adjacent(self, c: Combatant) -> list[Combatant]:
        """Return the list of allies standing next to c."""
        return [
            n for n in (self.get_left(c), self.get_right(c))
            if n is not None
        ]

    def link(
        self,
        combatants: list[Combatant] | tuple[Combatant, ...],
        circular: bool = True,
    ) -> None:
        """Set up left/right adjacency links between combatants.

        If circular, the first and last are linked (forming a ring).
        Otherwise, the ends are left open (for a line segment).
        """
        if len(combatants) > 1:
            if circular:
                self.set_left(combatants[0], combatants[-1])
                self.set_right(combatants[-1], combatants[0])
            for i in range(1, len(combatants)):
                self.set_left(combatants[i], combatants[i - 1])
            for i in range(len(combatants) - 1):
                self.set_right(combatants[i], combatants[i + 1])

    def death(self, corpse: Combatant) -> None:
        """Unlink a dead combatant from its neighbors and enemies."""
        left = self.get_left(corpse)
        right = self.get_right(corpse)

        if left:
            new_right = None if left == right else right
            self.set_right(left, new_right)
        if right:
            new_left = None if right == left else left
            self.set_left(right, new_left)

        for enemy in corpse.attackable:
            enemy.attackable.remove(corpse)


class Line(Formation):
    """Two sides face each other in lines.

    Models terrain where surrounding is impossible — a narrow corridor,
    backs to a wall, a bridge, etc.  The shorter side is centered so
    that its members face the middle of the longer side.

    Position algorithm
    ~~~~~~~~~~~~~~~~~~
    Each combatant is assigned a numeric position along the line:

    - Side A positions: ``i`` for ``i in 0 .. n_a-1``
    - Side B positions: ``j + (n_a - n_b) / 2`` for ``j in 0 .. n_b-1``

    A pair can attack each other iff ``|pos_a - pos_b| <= 1``.

    Example — 3 vs 2::

        A0  A1  A2       positions  0    1    2
          B0  B1         positions  0.5  1.5

        Attackable pairs:  A0<->B0  A1<->B0  A1<->B1  A2<->B1

    Example — 3 vs 3 (equal sizes, same positions)::

        A0  A1  A2       positions  0  1  2
        B0  B1  B2       positions  0  1  2

        B0<->A0,A1   B1<->A0,A1,A2   B2<->A1,A2

    Same-side adjacency is a simple linear chain (not circular) —
    the ends have one neighbor, the middle has two.

    When a combatant dies the entire formation is redeployed because
    re-centering shifts everyone's positions.  Lists are small (< 10
    per side) so the cost is negligible.
    """

    def __init__(
        self,
        side_a: list[Combatant] | tuple[Combatant, ...],
        side_b: list[Combatant] | tuple[Combatant, ...],
    ) -> None:
        super().__init__()
        self.side_a: list[Combatant] = list(side_a)
        self.side_b: list[Combatant] = list(side_b)
        self.deploy()

    @property
    def combatants(self) -> list[Combatant]:
        return self.side_a + self.side_b

    @property
    def one_side_finished(self) -> bool:
        return 0 in (len(self.side_a), len(self.side_b))

    def deploy(self) -> None:
        """Set up line formation: link each side linearly, compute positions
        with centering offset, and set mutual attackable for pairs within
        distance <= 1."""
        self._left.clear()
        self._right.clear()
        for c in self.side_a + self.side_b:
            c.attackable = set()

        self.link(self.side_a, circular=False)
        self.link(self.side_b, circular=False)

        n_a = len(self.side_a)
        n_b = len(self.side_b)
        offset_b = (n_a - n_b) / 2

        for i, ca in enumerate(self.side_a):
            pos_a = i
            for j, cb in enumerate(self.side_b):
                pos_b = j + offset_b
                if abs(pos_a - pos_b) <= 1:
                    ca.attackable.add(cb)
                    cb.attackable.add(ca)

    def death(self, corpse: Combatant) -> None:
        """Handle a death in the line formation.

        Unlinks the corpse, removes from whichever side list, then
        does a full redeploy if both sides still have combatants
        (re-centering changes everyone's positions).
        """
        Formation.death(self, corpse)
        if corpse in self.side_a:
            self.side_a.remove(corpse)
        elif corpse in self.side_b:
            self.side_b.remove(corpse)
        if self.side_a and self.side_b:
            self.deploy()


class Surround(Line):
    r"""A formation that starts as a line but transitions to encirclement
    when one side drops to 1 combatant versus >= 2.

    In **line mode** (neither side is solo-vs-many) it behaves exactly
    like ``Line`` — two sides facing each other with position-based
    attackable sets::

        A0  A1  A2           A0  A1
         B0  B1               B0  B1

    In **surround mode** (1 vs >= 2) the lone combatant is encircled.
    Every outer combatant can attack the inner (and vice-versa), and
    the outer group forms a circular adjacency ring::

        1 vs 3:               1 vs 5:

           O1                 O1---O2
          / | \                |     |
        O2--I--O3            O5  I  O3
                               |     |
                              O4---O3

    Each surrounding combatant gets an attack bonus of
    ``+5 * (1 + N)`` where N is the number of surrounding enemies.
    The surrounded combatant gets no bonus.

    Transitions
    ~~~~~~~~~~~
    ``deploy()`` is called on every death (when both sides still have
    members) and automatically picks the right mode:

    - **3v3 (line) -> deaths -> 1v2** : triggers surround + bonuses
    - **1v3 (surround) -> outer dies -> 1v2** : re-surround, lower bonus
    - **1v2 (surround) -> outer dies -> 1v1** : drops to line, bonuses removed
    - **Inner dies -> side empty** : ``one_side_finished``, no redeploy
    """

    ATTACK_ROLL_TYPES: tuple[str, ...] = (
        "attack", "counterattack", "double_attack",
        "feint", "iaijutsu", "lunge",
    )

    def __init__(
        self,
        side_a: list[Combatant] | tuple[Combatant, ...],
        side_b: list[Combatant] | tuple[Combatant, ...],
    ) -> None:
        self._surrounded: Combatant | None = None
        self._surround_bonuses: dict[Combatant, int] = {}
        super().__init__(side_a, side_b)

    @property
    def is_surrounding(self) -> bool:
        """Whether the formation is currently in surround mode."""
        return self._surrounded is not None

    def deploy(self) -> None:
        """Deploy as surround if one side has 1 vs >= 2, else as line."""
        self._remove_surround_bonuses()
        self._surrounded = None
        if len(self.side_a) == 1 and len(self.side_b) >= 2:
            self._deploy_surround(self.side_a[0], self.side_b)
        elif len(self.side_b) == 1 and len(self.side_a) >= 2:
            self._deploy_surround(self.side_b[0], self.side_a)
        else:
            super().deploy()

    def _deploy_surround(
        self, inner: Combatant, outer: list[Combatant],
    ) -> None:
        """Set up encirclement: inner vs outer ring."""
        self._left.clear()
        self._right.clear()
        for c in self.side_a + self.side_b:
            c.attackable = set()

        self.link(outer, circular=True)
        inner.attackable = set(outer)
        for c in outer:
            c.attackable = {inner}
        self._surrounded = inner
        self._apply_surround_bonuses(outer)

    def _apply_surround_bonuses(self, surrounding: list[Combatant]) -> None:
        """Grant attack bonuses to all surrounding combatants."""
        bonus = 5 * (1 + len(surrounding))
        for c in surrounding:
            for rt in self.ATTACK_ROLL_TYPES:
                c.always[rt] += bonus
            self._surround_bonuses[c] = bonus

    def _remove_surround_bonuses(self) -> None:
        """Remove previously applied surround bonuses."""
        for c, bonus in self._surround_bonuses.items():
            for rt in self.ATTACK_ROLL_TYPES:
                c.always[rt] -= bonus
        self._surround_bonuses.clear()

    def death(self, corpse: Combatant) -> None:
        """Handle a death: unlink, remove from side, redeploy."""
        Formation.death(self, corpse)
        if corpse in self.side_a:
            self.side_a.remove(corpse)
        elif corpse in self.side_b:
            self.side_b.remove(corpse)
        if self.side_a and self.side_b:
            self.deploy()
