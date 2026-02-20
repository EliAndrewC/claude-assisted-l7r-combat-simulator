from collections import defaultdict


class Formation:
    def death(self, corpse):
        if corpse.left:
            corpse.left.right = None if corpse.left == corpse.right else corpse.right
        if corpse.right:
            corpse.right.left = None if corpse.right == corpse.left else corpse.left

        for enemy in corpse.attackable:
            enemy.attackable.remove(corpse)


class Line(Formation):
    pass


class Surround(Formation):
    def __init__(self, inner, outer):
        assert len(inner) <= len(outer)
        self.inner, self.outer = inner, outer
        self.deploy()

    @property
    def combatants(self):
        return self.inner + self.outer

    @property
    def one_side_finished(self):
        return 0 in [len(self.inner), len(self.outer)]

    def inner_pairs(self):
        pairs = [[self.inner[-1], self.inner[0]]]
        for i in range(len(self.inner) - 1):
            pairs.append(self.inner[i:i + 1])
        return pairs

    def link(self, combatants, circular=True):
        if len(combatants) > 1:
            if circular:
                combatants[0].left = combatants[-1]
                combatants[-1].right = combatants[0]
            for i in range(1, len(combatants)):
                combatants[i].left = combatants[i - 1]
            for i in range(len(combatants) - 1):
                combatants[i].right = combatants[i + 1]

    def link_outer(self):
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

    def engage(self, pair, outer):
        for inner in pair:
            inner.attackable.add(outer)
            outer.attackable.add(inner)

    def surround(self):
        next = 0
        pairs = self.inner_pairs()
        opponents = defaultdict(int)
        remaining = self.outer[len(pairs):]
        while remaining:
            opponents[next] += 1
            outer = remaining.pop()
            for inner in pairs[next]:
                inner.attackable.add(outer)
                outer.attackable.add(inner)

            next = (next + 2) % len(pairs)
            if opponents[next] > min(opponents.values()):
                next = (next + 1) % len(pairs)

    def deploy(self):
        if len(self.inner) == 1:
            self.link(self.outer, circular=True)
            self.inner[0].attackable.update(set(self.outer))
            for combatant in self.outer:
                combatant.attackable.add(self.inner[0])
        else:
            self.link(self.inner, circular=True)
            self.surround()
            self.link_outer()

    def leftmost(self, corpse):
        start = curr = next(iter(corpse.attackable))
        while curr.left and curr.left != start and curr.left in corpse.attackable:
            curr = curr.left
        return curr

    def death(self, corpse):
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
