#!/usr/bin/env python3
"""Run a quick demo combat: a generic mook vs a Bayushi Bushi."""

from l7r.combatant import Combatant
from l7r.engine import Engine
from l7r.formations import Surround
from l7r.schools import BayushiBushi

mook = Combatant(
    air=5, earth=5, fire=5, water=5, void=5,
    attack=4, parry=5, base_damage_rolled=3,
)
bushi = BayushiBushi(
    air=3, earth=5, fire=6, water=5, void=5,
    attack=4, parry=5, rank=5,
)
formation = Surround([mook], [bushi])
engine = Engine(formation)
engine.fight()
print(
    f"mook ends the combat with {mook.serious} serious"
    f" wounds compared to the bushi with {bushi.serious}"
)
