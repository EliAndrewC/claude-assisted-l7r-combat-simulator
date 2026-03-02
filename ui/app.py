"""Streamlit combat simulator UI.

Run with: PYTHONPATH=. streamlit run ui/app.py
"""

from __future__ import annotations

import re

import streamlit as st

import l7r.builders as builders_mod
from l7r.builders import ProfessionalProgression, build
from l7r.engine import Engine
from l7r.formations import Surround


def get_progressions() -> dict[str, type]:
    """Return {display_name: class} for all progressions, schools first."""
    schools: dict[str, type] = {}
    professionals: dict[str, type] = {}
    for name in sorted(builders_mod.__all__):
        cls = getattr(builders_mod, name)
        display = name.replace("Progression", "")
        display = re.sub(r"([a-z])([A-Z])", r"\1 \2", display)
        if issubclass(cls, ProfessionalProgression):
            professionals[display] = cls
        else:
            schools[display] = cls
    result: dict[str, type] = {}
    result.update(schools)
    result.update(professionals)
    return result


PROGRESSIONS = get_progressions()
PROGRESSION_NAMES = list(PROGRESSIONS.keys())
RINGS = ("air", "earth", "fire", "water", "void")
OVERRIDE_STATS = (*RINGS, "attack", "parry", "rank")


def _reset_overrides(label: str) -> None:
    """Rebuild baseline from current widget values and sync override keys.

    Called as an on_change callback when progression, XP, or non-combat %
    changes.  At callback time, session_state already holds the *new*
    widget values, so we can build a fresh baseline and update the override
    keys before the next rerun renders the number_input widgets.
    """
    progression_name = st.session_state[f"{label}_progression"]
    total_xp = st.session_state[f"{label}_xp"]
    non_combat_pct = st.session_state[f"{label}_noncombat"] / 100

    progression_cls = PROGRESSIONS[progression_name]
    baseline = build(
        progression_cls,
        xp=150,
        earned_xp=max(0, total_xp - 150),
        non_combat_pct=non_combat_pct,
    )

    for ring in RINGS:
        st.session_state[f"{label}_{ring}"] = getattr(baseline, ring)
    st.session_state[f"{label}_attack"] = baseline.attack
    st.session_state[f"{label}_parry"] = baseline.parry
    st.session_state[f"{label}_rank"] = baseline.rank


def _init_overrides(label: str, progression_name: str, total_xp: int,
                    non_combat_pct: float) -> None:
    """Set override session-state keys on first render (before widgets exist)."""
    sentinel = f"{label}_initialized"
    if sentinel in st.session_state:
        return
    st.session_state[sentinel] = True

    progression_cls = PROGRESSIONS[progression_name]
    baseline = build(
        progression_cls,
        xp=150,
        earned_xp=max(0, total_xp - 150),
        non_combat_pct=non_combat_pct,
    )

    for ring in RINGS:
        st.session_state[f"{label}_{ring}"] = getattr(baseline, ring)
    st.session_state[f"{label}_attack"] = baseline.attack
    st.session_state[f"{label}_parry"] = baseline.parry
    st.session_state[f"{label}_rank"] = baseline.rank


def fighter_config(label: str, default_index: int = 0) -> dict:
    """Render sidebar controls for one fighter and return config dict."""
    st.sidebar.subheader(label)

    # Seed override keys before any widgets with those keys are rendered.
    _init_overrides(label, PROGRESSION_NAMES[default_index], 150, 0.2)

    on_change = lambda: _reset_overrides(label)  # noqa: E731

    progression_name = st.sidebar.selectbox(
        "Progression",
        PROGRESSION_NAMES,
        index=default_index,
        key=f"{label}_progression",
        on_change=on_change,
    )
    total_xp = st.sidebar.slider(
        "XP", 150, 500, 150, key=f"{label}_xp",
        on_change=on_change,
    )
    non_combat_pct = st.sidebar.slider(
        "Non-combat XP %", 0, 50, 20, key=f"{label}_noncombat",
        on_change=on_change,
    ) / 100

    overrides: dict[str, int] = {}
    with st.sidebar.expander("Manual Overrides"):
        for ring in RINGS:
            overrides[ring] = st.number_input(
                ring.capitalize(),
                min_value=1,
                max_value=6,
                key=f"{label}_{ring}",
            )
        overrides["attack"] = st.number_input(
            "Attack",
            min_value=1,
            max_value=5,
            key=f"{label}_attack",
        )
        overrides["parry"] = st.number_input(
            "Parry",
            min_value=1,
            max_value=5,
            key=f"{label}_parry",
        )
        overrides["rank"] = st.number_input(
            "Rank",
            min_value=0,
            max_value=5,
            key=f"{label}_rank",
        )

    with st.sidebar.expander("Advantages / Disadvantages"):
        sote = st.checkbox(
            "Strength of Earth", key=f"{label}_sote"
        )
        great_destiny = st.checkbox(
            "Great Destiny", key=f"{label}_gd"
        )
        permanent_wound = st.checkbox(
            "Permanent Wound",
            key=f"{label}_pw",
            disabled=great_destiny,
        )
        if great_destiny:
            permanent_wound = False
        lucky = st.checkbox("Lucky", key=f"{label}_lucky")
        unlucky = st.checkbox("Unlucky", key=f"{label}_unlucky")

    return {
        "progression_name": progression_name,
        "total_xp": total_xp,
        "non_combat_pct": non_combat_pct,
        "overrides": overrides,
        "strength_of_the_earth": sote,
        "great_destiny": great_destiny,
        "permanent_wound": permanent_wound,
        "lucky": lucky,
        "unlucky": unlucky,
    }


def build_fighter(config: dict):
    """Build a Combatant from a fighter config dict.

    Overrides (rings, attack, parry, rank) are passed through to the
    constructor via build()'s ``**extra``, so derived values like TN,
    VPs, and knack levels are computed from the overridden stats.
    """
    progression_cls = PROGRESSIONS[config["progression_name"]]

    extras: dict[str, object] = {}
    for adv in (
        "strength_of_the_earth",
        "great_destiny",
        "permanent_wound",
        "lucky",
        "unlucky",
    ):
        if config[adv]:
            extras[adv] = True

    extras.update(config.get("overrides", {}))

    total_xp = config["total_xp"]
    return build(
        progression_cls,
        xp=150,
        earned_xp=max(0, total_xp - 150),
        non_combat_pct=config.get("non_combat_pct", 0.2),
        **extras,
    )


def show_stats(fighter, label: str) -> None:
    """Display a fighter's stats in a compact layout."""
    st.markdown(f"**{label}: {fighter.name}**")
    cols = st.columns(7)
    for i, ring in enumerate(RINGS):
        cols[i].metric(ring.capitalize(), getattr(fighter, ring))
    cols[5].metric("Attack", fighter.attack)
    cols[6].metric("Parry", fighter.parry)
    extra = []
    if fighter.rank:
        extra.append(f"Rank {fighter.rank}")
    extra.append(f"{fighter.vps} VPs")
    extra.append(f"{fighter.xp} XP")
    st.caption(" · ".join(extra))


def main() -> None:
    st.set_page_config(page_title="L7R Combat Simulator", layout="wide")
    st.title("L7R Combat Simulator")

    st.sidebar.header("Fighter Configuration")

    config_a = fighter_config("Fighter A", default_index=0)
    st.sidebar.divider()
    config_b = fighter_config(
        "Fighter B",
        default_index=min(1, len(PROGRESSION_NAMES) - 1),
    )

    st.sidebar.divider()
    st.sidebar.subheader("Combat Options")
    duel = st.sidebar.checkbox("Include duel")
    fight_clicked = st.sidebar.button("Fight!", type="primary")

    if fight_clicked:
        fighter_a = build_fighter(config_a)
        fighter_b = build_fighter(config_b)

        col_a, col_b = st.columns(2)
        with col_a:
            show_stats(fighter_a, "Fighter A")
        with col_b:
            show_stats(fighter_b, "Fighter B")

        st.divider()

        formation = Surround([fighter_a], [fighter_b])
        engine = Engine(formation)
        engine.fight(duel=duel)

        lines = engine.renderer.render_combat(engine.combat_record)
        st.subheader("Combat Log")
        st.code("\n".join(lines))

        st.subheader("Result")
        winner = engine.combat_record.winner
        winner_label = "Fighter A" if winner == "side_a" else "Fighter B"
        st.success(f"Winner: {winner_label}")

        res_a, res_b = st.columns(2)
        with res_a:
            st.metric("Fighter A — Serious Wounds", fighter_a.serious)
            st.metric("Fighter A — Light Wounds", fighter_a.light)
        with res_b:
            st.metric("Fighter B — Serious Wounds", fighter_b.serious)
            st.metric("Fighter B — Light Wounds", fighter_b.light)


if __name__ == "__main__":
    main()
