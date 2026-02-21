#!/usr/bin/env python3
"""Generate the probability lookup tables used by the dice system.

Runs Monte Carlo simulations to produce l7r/data/probabilities.py,
which contains pre-computed averages and CDF data for XkY dice pools.

Usage:
    python tools/generate_probabilities.py [output_file]

If no output file is given, writes to /tmp/probabilities.py.
"""

import sys
from collections import defaultdict
from pprint import pprint

from l7r.dice import xky

ROLLS = 100000


def main() -> None:
    [fname] = sys.argv[1:2] or ["/tmp/probabilities.py"]
    prob: dict = {True: defaultdict(int), False: defaultdict(int)}
    for i in range(ROLLS):
        for rolled in range(1, 11):
            for kept in range(1, rolled + 1):
                for reroll in [True, False]:
                    result = xky(rolled, kept, reroll)
                    prob[reroll][rolled, kept] += result
                    for tn in range(result + 1):
                        prob[reroll][rolled, kept, tn] += 1

                    # to make lookups easier, store the results of
                    # e.g. 10k6 as 11k5 as well (and 12k4, 13k3, etc)
                    if rolled == 10:
                        for j in range(kept - 1, 1, -1):
                            prob[reroll][rolled + j, kept - j] += result
                            for tn in range(result + 1):
                                prob[reroll][rolled + j, kept - j, tn] += 1

    for reroll in [True, False]:
        prob[reroll] = {
            key: val / ROLLS for key, val in prob[reroll].items()
        }

    with open(fname, "w") as f:
        f.write("prob = ")
        pprint(prob, stream=f)


if __name__ == "__main__":
    main()
