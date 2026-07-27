"""Unit tests for the STAB-pacing pass (scripts/stab_pacing.py).

Guards: ability-granted STAB detection, gap fill, and the L1<=4 / <=L70 caps.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ll = _load("learnset_ladder")
sp = _load("stab_pacing")


@pytest.mark.unit
def test_ability_grants_extra_stab() -> None:
    """Full Moon adds Dark+Fairy; Mystic Power grants no extra (own types only)."""
    fm = sp.stab_types({"types": ["Rock"], "abilities": {"secondary": "Full Moon"}})
    assert "Dark" in fm and "Fairy" in fm and "Rock" in fm
    mp = sp.stab_types({"types": ["Water"], "abilities": {"primary": "Mystic Power"}})
    assert mp == ["Water"]


@pytest.mark.unit
def test_split_follows_highest_attack_stat() -> None:
    assert sp.chosen_splits({"stats": {"atk": 130, "spa": 60}}) == ["physical"]
    assert sp.chosen_splits({"stats": {"atk": 50, "spa": 120}}) == ["special"]


@pytest.mark.unit
def test_normalize_caps_l1_and_level70() -> None:
    ctx = ll.Ctx()
    rows = [
        (1, "Harden"), (1, "Growl"), (1, "Leer"), (1, "Tackle"),
        (1, "Ember"), (1, "Scratch"),  # 6 at L1 -> only 4 may stay
        (80, "Overheat"),              # past L70 -> pulled to <=70
    ]
    out = sp.normalize(rows, ctx)
    assert sum(1 for lvl, _ in out if lvl == 1) == 4
    assert max(lvl for lvl, _ in out) <= 70
    assert len(out) == len(rows)  # nothing dropped, only relevelled


@pytest.mark.unit
def test_spread_gives_one_move_per_earned_level() -> None:
    """Collisions at level >= 2 spread to nearby free levels; L0/L1 may stack."""
    ctx = ll.Ctx()
    rows = [
        (1, "Growl"), (1, "Tackle"),          # L1 kit may share
        (39, "Wraithstrike"), (39, "Interment"),  # collision -> spread
        (70, "Double-Edge"), (70, "Last Resort"),  # collision at the cap
    ]
    out = sp.normalize(rows, ctx)
    earned = [lvl for lvl, _ in out if lvl >= 2]
    assert len(earned) == len(set(earned))  # all distinct
    assert max(lvl for lvl, _ in out) <= 70
    assert sum(1 for lvl, _ in out if lvl == 1) == 2  # L1 untouched


@pytest.mark.unit
def test_plan_fills_missing_band() -> None:
    """A Fire physical attacker missing its ≤50 rung gets one added in-window."""
    ctx = ll.Ctx()
    import json

    base = json.loads((ll.mc.RULESET / ".base" / "1.11.2.json").read_text("utf-8"))
    pool = ll.mc.build_pool()
    rung = sp.build_rung_map(pool, set(base["moves"]))
    mon = {"types": ["Fire"], "stats": {"atk": 120, "spa": 50}}
    rows = [(30, "Flare Blitz")]  # has only the >110 rung
    adds = sp.plan_species(mon, rows, ctx, rung)
    bands_added = {ctx.rung(m)[2] for _, m in adds if ctx.rung(m)}
    assert "≤50" in bands_added  # the low rung was filled
    assert all(1 <= lvl <= 70 for lvl, _ in adds)
