"""
A lot of our decisions need to make estimates about the percentage chance of
something happening.  For example, we might decide to spend a void point if it
improves our chances of taking only 1 serious wound by above a certain percent.
In order to do this, we need to be able to quickly look up things like:

"What is the average of 6k4 when rerolling 10s?"
or
"What is the chance of 5k4 getting at least 25 without rerolling 10s?"

We have run a monte carlo simulation to determine these chances and stored the
results in the probabilities.py file, which defines a single "prob" dict.

This dict looks like this:

    prob = {
        True: {  # this is where we store the values when we ARE rerolling 10s
            (1, 1): 5.5,  # this is the average of 1k1
            (1, 1, 0): 1.0,  # this is the % chance of 1k1 making at least 0
            (1, 1, 1): 1.0,  # this is the % chance of 1k1 making at least 1
            (1, 1, 2): 0.899,  # this is the % chance of 1k1 making at least 2
            ...
        },
        False: {  # this is where we store the values when NOT rerolling 10s
            (1, 1): 6.0942,
            (1, 1, 1): 1.0,
            (1, 1, 2): 0.899,
            ...
        }
    }

This allows us to do easy lookups like:

prob[True][10, 6, 45]
# returns the % chance of 10k6 making at least 45
# while rerolling 10s (as a float between 0 and 1)

prob[False][12, 4, 45]
# returns the % chance of 10k6 (which is what 12k4
# converts to) making at least 45 while NOT rerolling
# 10s

Note that someone who wants a reliable average should NOT do this:

prob[True][5, 3]   # returns the average of 5k3 when rerolling 10s
prob[False][5, 3]  # returns the average of 5k2 when NOT rerolling 10s

The reason is that even though this dict does contain those averages, someone
might need to look up the average of e.g. 11k10 which doesn't exist.  The "avg"
function in l7r/dice.py returns a reliable estimate for this edge case and is
therefore preferred to having someone directly look up the result from "prob".


We also have a second monte carlo simulation stored in wound_table.py, which
defines a single "wound_table" dict.  This maps (light, rolled, kept) to the
average number of serious wounds you'd expect to take when making a wound check
against that many light wounds with that dice pool (always rerolling 10s, since
wound checks always reroll).

The dict looks like this:

    wound_table = {
        (2, 1, 1): 0.10034,   # avg serious wounds from 2 light on 1k1
        (2, 2, 1): 0.00995,   # avg serious wounds from 2 light on 2k1
        ...
        (30, 4, 3): 1.29382,  # avg serious wounds from 30 light on 4k3
        ...
    }

This allows us to do lookups like:

wound_table[30, 4, 3]
# returns the average number of serious wounds when making
# a wound check of 4k3 against 30 light wounds

For example, wound_table[2, 2, 1] is approximately 0.01, which makes sense:
the only way to fail a TN of 2 on 2k1 is to roll a 1 on both dice, which is
exactly a 1% chance, and failing by less than 10 always gives exactly 1 serious
wound, so the expected value is 0.01.

The table covers light wound values from 1 to 150 and all valid roll/keep
combinations up to 10k10, plus overflow aliases (e.g. 11k5 stores the same
values as 10k6, matching the overflow convention used in prob).  Missing keys
default to 0.0 via defaultdict.  The expected_serious() method in Combatant
falls back to the staircase formula for light values above 150.

The key advantage over the old approach of plugging average values into the
staircase formula (calc_serious) is that the monte carlo captures the full
distribution of the wound check roll.  For example, calc_serious(30, avg(4k3))
returns 2 (an integer), but the true expected value from the monte carlo is
closer to 1.72 because some rolls beat the TN and take 0 serious wounds.  This
lets heuristic thresholds like sw_parry_threshold distinguish between values
like 1.6 and 1.9, which was impossible when everything was rounded to integers.
"""

from collections import defaultdict

from l7r.data.probabilities import prob
from l7r.data.wound_table import wound_table

# probabilities.py stores the results as a dict, but we want to convert to a
# defaultdict so that if someone looks up a value which doesn't exist, we can
# comfortably return zero for it on the basis that no roll out of ten thousand
# reached that number, e.g. prob[True][1, 1, 100] will return 0 because none of
# the rolls in our monte carlo simulation got to 100 on 1k1
for reroll in [True, False]:
    d = defaultdict(int)
    d.update(prob[reroll])
    prob[reroll] = d

wound_table = defaultdict(float, wound_table)
