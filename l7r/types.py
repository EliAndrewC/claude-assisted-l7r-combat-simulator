"""
Domain-specific type aliases for the L7R combat simulator.

These aren't used for runtime type checking — they exist to make function
signatures and variable annotations self-documenting. When you see a
parameter typed as RollType instead of str, you immediately know it's one
of the recognized dice roll categories, not an arbitrary string.
"""

from typing import Literal, TypeAlias

# The category of dice roll being made. Determines which pools of bonuses
# (always, auto_once, disc, multi, extra_dice) apply to the roll. Also
# used for school knack names, since knack skill levels are looked up with
# getattr(self, knack) and knack names double as roll type keys.
RollType: TypeAlias = Literal[
    "attack",
    "counterattack",
    "double_attack",
    "feint",
    "iaijutsu",
    "lunge",
    "parry",
    "wound_check",
    "damage",
    "initiative",
    # Non-combat roll types used by specific schools:
    "interrogation",
    "discern_honor",
    "presence",
    "detect_taint",
    "oppose_social",
    "oppose_knowledge",
    "worldliness",
    "athletics",
    "pontificate",
    # Non-combat knacks for new schools:
    "conviction",
    "otherworldliness",
    "absorb_void",
    "kharmic_spin",
]

# Keys for the auto_once bonus dict. Includes all RollType values (for
# bonuses that apply to specific roll types) plus damage sub-categories
# that modify the damage calculation independently of any dice roll.
BonusKey: TypeAlias = Literal[
    # Roll-type keys (same values as RollType):
    "attack",
    "counterattack",
    "double_attack",
    "feint",
    "iaijutsu",
    "lunge",
    "parry",
    "wound_check",
    "damage",
    "initiative",
    # Damage sub-categories — these adjust the damage dice pool rather
    # than adding a flat bonus to a roll result:
    "damage_rolled",  # extra rolled damage dice
    "damage_kept",  # extra kept damage dice
    "serious",  # automatic serious wounds added to damage
]

# Combat event names that handlers can be registered for via the
# self.events dict. Fired by the Engine and Combatant at specific
# points in the combat sequence.
EventName: TypeAlias = Literal[
    "pre_fight",
    "pre_combat",
    "pre_round",
    "post_round",
    "pre_attack",
    "post_attack",
    "successful_attack",
    "pre_defense",
    "post_defense",
    "successful_parry",
    "wound_check",
    "vps_spent",
    "death",
]
