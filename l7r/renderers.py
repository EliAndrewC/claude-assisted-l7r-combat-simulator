"""Renderers that convert structured combat records into text output.

The TextRenderer produces terminal-friendly text matching the simulator's
existing output style. Additional renderers (e.g. StreamlitRenderer) can
consume the same record types for rich UI display.
"""

from __future__ import annotations

from l7r.records import AttackRecord, CombatRecord, DamageRecord, DuelRecord, DuelRoundRecord, InitiativeRecord, ParryRecord, RoundRecord, WoundCheckRecord


class TextRenderer:
    """Renders CombatRecord hierarchy to terminal text lines.

    Each render_* method returns a list of strings (one per log line)
    matching the original Engine/Combatant log output as closely as
    practical.
    """

    def render_combat(self, record: CombatRecord) -> list[str]:
        lines: list[str] = []
        if record.duel:
            lines.extend(self.render_duel(record.duel))
        for rnd in record.rounds:
            lines.extend(self.render_round(rnd))
        return lines

    def render_duel(self, record: DuelRecord) -> list[str]:
        lines: list[str] = []
        for dr in record.rounds:
            lines.extend(self.render_duel_round(dr))
        return lines

    def render_duel_round(self, record: DuelRoundRecord) -> list[str]:
        lines: list[str] = []
        lines.append(f"Duel round {record.round_num}: {record.a_name} vs {record.b_name}")
        if record.contested_a and record.contested_b:
            lines.append(f"  Contested: {record.a_name} {record.contested_a.total} vs {record.b_name} {record.contested_b.total}")
        if record.resheathe:
            lines.append("Resheathe — TNs reset, free raises awarded")
        return lines

    def render_round(self, record: RoundRecord) -> list[str]:
        lines: list[str] = []
        for init in record.initiatives:
            lines.append(self.render_initiative(init))
        for phase_actions in record.phases:
            for action in phase_actions:
                lines.extend(self.render_action(action))
        return lines

    def render_initiative(self, record: InitiativeRecord) -> str:
        return f"{record.combatant}: initiative: {record.kept}"

    def render_action(self, record: AttackRecord | ParryRecord | DamageRecord | WoundCheckRecord, indent: int = 0) -> list[str]:
        prefix = " " * indent
        if isinstance(record, AttackRecord):
            return self.render_attack(record, indent)
        elif isinstance(record, ParryRecord):
            return [f"{prefix}{record.defender}: {record.total} parry roll"]
        elif isinstance(record, DamageRecord):
            return [f"{prefix}{record.attacker}: deals {record.light} light and {record.serious} serious wounds"]
        elif isinstance(record, WoundCheckRecord):
            return [f"{prefix}{record.combatant}: {record.total} wound check vs {record.light_total} light wounds, takes {record.serious_taken} serious"]
        return []

    def render_attack(self, record: AttackRecord, indent: int = 0) -> list[str]:
        prefix = " " * indent
        lines: list[str] = []
        lines.append(f"{prefix}Phase #{record.phase}: {record.attacker} {record.knack} vs {record.defender}")
        lines.append(f"{prefix}    {record.attacker}: {record.total} {record.knack} roll ({record.vps_spent} vp) vs {record.tn} tn")
        for child in record.children:
            lines.extend(self.render_action(child, indent + 4))
        return lines
