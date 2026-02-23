#!/usr/bin/env python3
"""Generate the wound-check lookup table used by expected_serious().

Runs Monte Carlo simulations to produce l7r/data/wound_table.py,
which maps (light, wc_roll, wc_keep) -> average serious wounds.

Usage:
    python tools/generate_wound_table.py [output_file]

If no output file is given, writes to /tmp/wound_table.py.
"""

import sys
from collections import defaultdict
from pprint import pprint

from l7r.dice import xky

ROLLS = 100000


def main() -> None:
    [fname] = sys.argv[1:2] or ["/tmp/wound_table.py"]
    wound_table: dict[tuple[int, int, int], int] = defaultdict(int)

    for i in range(ROLLS):
        for rolled in range(1, 11):
            for kept in range(1, rolled + 1):
                check = xky(rolled, kept, reroll=True)

                # collect all keys that share this roll result
                keys = [(rolled, kept)]
                # overflow aliases: e.g. 10k6 also stored as 11k5, 12k4, etc
                if rolled == 10:
                    for j in range(kept - 1, 1, -1):
                        keys.append((rolled + j, kept - j))

                # calc_serious = ceil(max(0, light - check) / 10)
                # which is 0 for light <= check, so start at check + 1
                start = max(1, check + 1)
                for light in range(start, 151):
                    sw = (light - check + 9) // 10
                    for r, k in keys:
                        wound_table[light, r, k] += sw

    wound_table = {
        key: val / ROLLS for key, val in wound_table.items()
    }

    with open(fname, "w") as f:
        f.write("wound_table = ")
        pprint(wound_table, stream=f, width=120)


if __name__ == "__main__":
    main()
