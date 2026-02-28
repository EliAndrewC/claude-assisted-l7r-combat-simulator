"""Structured combat records for the L7R simulator.

These dataclasses capture the full context of each combat action — individual
dice results, bonus sources, nested counterattacks, etc. — enabling both
text rendering (now) and rich Streamlit UI rendering (later).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DieResult:
    """A single die rolled as part of a dice pool."""

    face: int
    """Final value after explosion (e.g. 10+6=16)."""

    kept: bool
    """Whether this die was in the kept set."""

    exploded: bool
    """Whether this die exploded (initial roll was 10 and 10s were
    rerolled on this type of roll).  A 10 on a non-rerolling roll
    (e.g. initiative or certain rolls made while crippled) will
    have exploded=False."""


@dataclass
class DiceRoll:
    """Full result of an XkY dice roll."""

    roll: int
    """X in XkY (after overflow adjustment)."""

    keep: int
    """Y in XkY (after overflow adjustment)."""

    reroll: bool
    """Whether 10s were exploded."""

    dice: list[DieResult]
    """Every die rolled, including unkept dice."""

    overflow_bonus: int
    """Flat bonus from kept dice exceeding 10 in actual_xky."""

    total: int
    """Final summed result: kept dice + overflow_bonus."""


@dataclass
class Modifier:
    """A labeled bonus applied to a roll result."""

    source: str
    """Human-readable label: 'R2T', 'Strength of Earth', 'predeclare', etc."""

    value: int
    """Bonus amount."""


@dataclass
class Reroll:
    """A reroll of a dice pool (e.g. Lucky advantage)."""

    reason: str
    """Why the reroll happened: 'Lucky', 'Hida R3T', 'Merchant R5T'."""

    before: DiceRoll
    """The original roll before rerolling."""

    after: DiceRoll
    """The new roll after rerolling."""


@dataclass
class AttackRecord:
    """Record of a single attack action."""

    attacker: str
    defender: str
    knack: str
    phase: int
    vps_spent: int
    dice: DiceRoll | None = None
    modifiers: list[Modifier] = field(default_factory=list)
    total: int = 0
    tn: int = 0
    hit: bool = False
    children: list[ActionRecord] = field(default_factory=list)


@dataclass
class ParryRecord:
    """Record of a parry attempt."""

    defender: str
    attacker: str
    vps_spent: int = 0
    dice: DiceRoll | None = None
    modifiers: list[Modifier] = field(default_factory=list)
    total: int = 0
    tn: int = 0
    success: bool = False
    predeclared: bool = False


@dataclass
class DamageRecord:
    """Record of damage dealt."""

    attacker: str
    defender: str
    dice: DiceRoll | None = None
    modifiers: list[Modifier] = field(default_factory=list)
    light: int = 0
    serious: int = 0
    extra_rolled: int = 0
    extra_kept: int = 0


@dataclass
class WoundCheckRecord:
    """Record of a wound check roll."""

    combatant: str
    light_this_hit: int = 0
    light_total: int = 0
    vps_spent: int = 0
    dice: DiceRoll | None = None
    modifiers: list[Modifier] = field(default_factory=list)
    total: int = 0
    passed: bool = False
    serious_taken: int = 0
    reroll: Reroll | None = None
    voluntary_serious: bool = False


@dataclass
class InitiativeRecord:
    """Record of initiative roll for one combatant."""

    combatant: str
    dice: list[DieResult] = field(default_factory=list)
    kept: list[int] = field(default_factory=list)
    modifications: list[Modifier] = field(default_factory=list)


@dataclass
class DuelRoundRecord:
    """Record of a single duel round."""

    round_num: int
    contested_a: DiceRoll | None = None
    contested_b: DiceRoll | None = None
    a_name: str = ""
    b_name: str = ""
    a_strikes: bool = False
    b_strikes: bool = False
    attacks: list[AttackRecord] = field(default_factory=list)
    damage: list[DamageRecord] = field(default_factory=list)
    wound_checks: list[WoundCheckRecord] = field(default_factory=list)
    resheathe: bool = False


ActionRecord = AttackRecord | ParryRecord | DamageRecord | WoundCheckRecord


@dataclass
class RoundRecord:
    """Record of a full combat round."""

    round_num: int
    initiatives: list[InitiativeRecord] = field(default_factory=list)
    phases: list[list[ActionRecord]] = field(default_factory=list)


@dataclass
class DuelRecord:
    """Record of a full iaijutsu duel."""

    a_name: str
    b_name: str
    rounds: list[DuelRoundRecord] = field(default_factory=list)


@dataclass
class CombatRecord:
    """Top-level record of an entire combat encounter."""

    duel: DuelRecord | None = None
    rounds: list[RoundRecord] = field(default_factory=list)
    winner: str = ""
