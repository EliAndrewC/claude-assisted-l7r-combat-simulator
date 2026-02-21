"""
Battlefield formations: how combatants are physically arranged.

Formations determine who can attack whom (the `attackable` set on each
combatant) and who is adjacent (the `left`/`right` links used for parrying
on behalf of allies). When a combatant dies, the formation restructures
to fill gaps.

Currently implements Surround (a group encircling another group) and has
a stub for Line formations.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from l7r.combatant import Combatant


class Formation:
    """Base class for battlefield formations.

    Handles the universal death logic: unlinking a corpse from its
    neighbors and removing it from all enemies' attackable sets.
    """

    def death(self, corpse: Combatant) -> None:
        if corpse.left:
            corpse.left.right = None if corpse.left == corpse.right else corpse.right
        if corpse.right:
            corpse.right.left = None if corpse.right == corpse.left else corpse.left

        for enemy in corpse.attackable:
            enemy.attackable.remove(corpse)


class Line(Formation):
    """Simple line formation. (Stub — not yet fully implemented.)"""

    pass


class Surround(Formation):
    """A surround formation: an inner group encircled by an outer group.

    The inner group forms a ring (each member adjacent to two others),
    and the outer group surrounds them. Each outer combatant can attack
    the inner members they're positioned near (typically 1-2), and vice
    versa. When there's only one inner combatant, everyone in the outer
    group can attack them (a classic "surrounded by enemies" scenario).

    The formation handles deployment (initial positioning), engagement
    (who can attack whom), and restructuring when combatants die.
    """

    def __init__(self, inner: list[Combatant], outer: list[Combatant]) -> None:
        assert len(inner) <= len(outer)
        self.inner = inner
        self.outer = outer
        self.deploy()

    @property
    def combatants(self) -> list[Combatant]:
        return self.inner + self.outer

    @property
    def one_side_finished(self) -> bool:
        return 0 in [len(self.inner), len(self.outer)]

    def inner_pairs(self) -> list[list[Combatant]]:
        """Return adjacent pairs of inner combatants (as a circular ring).

        Each pair shares the outer combatants positioned between them.
        Used to determine which outer combatants can attack which inner ones.
        """
        pairs = [[self.inner[-1], self.inner[0]]]
        for i in range(len(self.inner) - 1):
            pairs.append(self.inner[i : i + 1])
        return pairs

    def link(
        self, combatants: list[Combatant] | tuple[Combatant, ...], circular: bool = True
    ) -> None:
        """Set up left/right adjacency links between combatants.

        If circular, the first and last are linked (forming a ring).
        Otherwise, the ends are left open (for a line segment).
        """
        if len(combatants) > 1:
            if circular:
                combatants[0].left = combatants[-1]
                combatants[-1].right = combatants[0]
            for i in range(1, len(combatants)):
                combatants[i].left = combatants[i - 1]
            for i in range(len(combatants) - 1):
                combatants[i].right = combatants[i + 1]

    def link_outer(self) -> None:
        """Establish left/right adjacency links among outer combatants.

        Groups outer combatants by which inner pair they're between,
        links each group internally, then connects adjacent groups.
        """
        pairs = self.inner_pairs()
        groups = defaultdict(set)
        for pair in pairs:
            group = tuple(pair[0].attackable.intersection(pair[1].attackable))
            if len(group) > 1:
                self.link(group, circular=False)
            groups[pair[0]].add(group)
            groups[pair[1]].add(group)

        for pair in pairs:
            left, right = pair
            all = groups[left] + groups[right]
            left_group = list(all - groups[right])[0]
            right_group = list(all - groups[left])[0]
            middle_group = list(groups[left] & groups[right])[0]

            left_group[-1].right = middle_group[0]
            middle_group[0].left = left_group[-1]
            middle_group[-1].right = right_group[0]
            right_group[0].left = left_group[-1]

    def engage(self, pair: list[Combatant], outer: Combatant) -> None:
        """Mark an outer combatant as able to attack (and be attacked by)
        both members of an inner pair."""
        for inner in pair:
            inner.attackable.add(outer)
            outer.attackable.add(inner)

    def surround(self) -> None:
        """Distribute excess outer combatants evenly around the inner ring.

        After assigning one outer combatant per inner pair, the remaining
        outer combatants are distributed by alternating between gaps,
        keeping the numbers as even as possible.
        """
        next = 0
        pairs = self.inner_pairs()
        opponents = defaultdict(int)
        remaining = self.outer[len(pairs) :]
        while remaining:
            opponents[next] += 1
            outer = remaining.pop()
            for inner in pairs[next]:
                inner.attackable.add(outer)
                outer.attackable.add(inner)

            next = (next + 2) % len(pairs)
            if opponents[next] > min(opponents.values()):
                next = (next + 1) % len(pairs)

    def deploy(self) -> None:
        """Set up the initial formation: link combatants and determine
        who can attack whom based on positioning."""
        if len(self.inner) == 1:
            self.link(self.outer, circular=True)
            self.inner[0].attackable.update(set(self.outer))
            for combatant in self.outer:
                combatant.attackable.add(self.inner[0])
        else:
            self.link(self.inner, circular=True)
            self.surround()
            self.link_outer()

    def leftmost(self, corpse: Combatant) -> Combatant:
        """Find the leftmost outer combatant that was engaged with the
        corpse. Used during restructuring to walk the linked list of
        enemies and redistribute attackable sets."""
        start = curr = next(iter(corpse.attackable))
        while curr.left and curr.left != start and curr.left in corpse.attackable:
            curr = curr.left
        return curr

    def death(self, corpse: Combatant) -> None:
        """Handle a death in the surround formation.

        When an inner combatant dies, their enemies gain the ability to
        attack the adjacent inner combatants (the gap is filled). When an
        outer combatant dies, we check if any inner combatant has lost all
        enemies (which would trigger a formation change).
        """
        Formation.death(self, corpse)

        if corpse in self.inner:
            self.inner.remove(corpse)
            curr = self.leftmost(corpse)
            while curr.right in corpse.attackable:
                curr.attackable.update(curr.right.attackable)

        if corpse in self.outer:
            self.outer.remove(corpse)
            for enemy in corpse.attackable:
                if not enemy.attackable:
                    # change to line formation
                    return
