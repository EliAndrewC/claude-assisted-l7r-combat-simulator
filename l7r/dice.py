import sys
from pprint import pprint
from random import randrange
from collections import defaultdict

from l7r.data import prob


def avg(reroll, roll, keep):
    """
    Since we only record averages up to 10k10, if someone asks for the average
    of something higher than that, we need to estimate a value.  Since anything
    above 10k10 just rolls 10k10 and gets a bonus of 2 times the number of extra
    rolled and kept dice, and we know 10k10 is ~61, we return that estimate.
    """
    return prob[reroll][roll, keep] or (61 + 2 * (roll + keep - 20))


def d10(reroll=True):
    total = die = randrange(1, 11)
    while reroll and die == 10:
        die = randrange(1, 11)
        total += die
    return total


def actual_xky(roll, keep):
    bonus = 0
    if roll > 10:
        keep += roll - 10
        roll = 10
    if keep > 10:
        bonus = keep - 10
        keep = 10

    return roll, keep, bonus


def xky(roll, keep, reroll=True):
    roll, keep, bonus = actual_xky(roll, keep)
    return bonus + sum(sorted(d10(reroll) for i in range(roll))[-keep:])


# this is how we make the probilities.py we save as l7r/data/probabilities.py
if __name__ == "__main__":
    [fname] = sys.argv[1:2] or ['/tmp/probabilities.py']
    ROLLS = 100000
    prob = {True: defaultdict(int), False: defaultdict(int)}
    for i in range(ROLLS):
        for rolled in range(1, 11):
            for kept in range(1, rolled + 1):
                for reroll in [True, False]:
                    result = xky(rolled, kept, reroll)
                    prob[reroll][rolled, kept] += result
                    for tn in range(result + 1):
                        prob[reroll][rolled, kept, tn] += 1

                    # to make lookups easier, store the results of e.g. 10k6 as 11k5 as well (and 12k4, and 13k3, etc)
                    if rolled == 10:
                        for j in range(kept - 1, 1, -1):
                            prob[reroll][rolled + j, kept - j] += result
                            for tn in range(result + 1):
                                prob[reroll][rolled + j, kept - j, tn] += 1

    for reroll in [True, False]:
        prob[reroll] = {key: val / ROLLS for key, val in prob[reroll].items()}

    with open(fname, 'w') as f:
        f.write('prob = ')
        pprint(prob, stream=f)
