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
"""

from collections import defaultdict

from l7r.data.probabilities import prob

# probabilities.py stores the results as a dict, but we want to convert to a
# defaultdict so that if someone looks up a value which doesn't exist, we can
# comfortably return zero for it on the basis that no roll out of ten thousand
# reached that number, e.g. prob[True][1, 1, 100] will return 0 because none of
# the rolls in our monte carlo simulation got to 100 on 1k1
for reroll in [True, False]:
    d = defaultdict(int)
    d.update(prob[reroll])
    prob[reroll] = d
