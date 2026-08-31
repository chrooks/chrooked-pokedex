"""Drift guards for the ability-fuel table (ability_fuel.json).

The fuel table is hand-keyed data keyed by ability chrooked_id — the source of
truth for which moves an ability demands in a learnset. Hand-keyed data rots
three ways, and each way has a tripwire here:

1. Vocabulary drift — a filter names a flag or field that doesn't exist:
   ``validate_fuel_table`` (also the load-time guard) must return no problems.
2. Membership drift — a table id no longer names a real ability, or a named
   move no longer exists in the pool.
3. Coverage drift — a NEW ability (base bump or a fresh custom) whose
   description looks fuel-shaped has no table entry. The description regex is
   deliberately a smoke detector, not the enforcement path: it fails the build
   naming the unclassified ability, and a human adds the entry (or the
   deliberate-exclusion note below).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from chrooked_pokedex.web import learnset_skeleton

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parent.parent
_FUEL_PATH = _ROOT / "src" / "chrooked_pokedex" / "web" / "ability_fuel.json"
_SNAPSHOT_PATH = _ROOT / "ruleset" / ".base" / "1.11.2.json"
_RULESET_ABILITIES = _ROOT / "ruleset" / "abilities"
_RULESET_MOVES = _ROOT / "ruleset" / "moves"

# Fuel-shaped description text. High-signal on purpose — the fuel table is the
# real classifier; this only has to catch an unclassified newcomer.
_FUEL_SHAPED = re.compile(
    r"sound|punch|\bbit(?:e|ing)\b|\bjaw|kick|slic|\bwind\b|\bwing\b|hammer"
    r"|pierc|\bbone|recoil|status move|normal(?:-type)? moves? (?:become|turn)"
    r"|multi[- ]?hit|drain|healing move|pulse",
    re.IGNORECASE,
)

# Abilities the detector flags that deliberately carry NO fuel entry — they are
# defensive (they react to the opponent's moves), so the species' own learnset
# owes them nothing. A new detector hit lands here only with a reason.
_DELIBERATELY_UNFUELED = {
    "soundproof",   # blocks incoming sound moves — defensive
    "magicbounce",  # reflects incoming status moves — defensive
    "liquidooze",   # punishes incoming drain moves — defensive
    "riposte",      # recoils contact damage at the attacker — defensive
}


def _all_abilities() -> dict[str, str]:
    """id → description for base ⊕ ruleset (ruleset wins)."""
    snap = json.loads(_SNAPSHOT_PATH.read_text("utf-8"))
    out = {
        aid: (entry.get("description") or "")
        for aid, entry in snap.get("abilities", {}).items()
    }
    for path in _RULESET_ABILITIES.glob("*.yaml"):
        data = yaml.safe_load(path.read_text("utf-8"))
        out[data.get("chrooked_id", path.stem)] = data.get("description") or ""
    return out


def _all_move_names() -> set[str]:
    """Casefolded move names for base ⊕ ruleset."""
    snap = json.loads(_SNAPSHOT_PATH.read_text("utf-8"))
    names = {
        (entry.get("name") or "").casefold()
        for entry in snap.get("moves", {}).values()
    }
    for path in _RULESET_MOVES.glob("*.yaml"):
        data = yaml.safe_load(path.read_text("utf-8"))
        if data.get("name"):
            names.add(data["name"].casefold())
    return names - {""}


def _fuel_table() -> dict[str, dict]:
    return json.loads(_FUEL_PATH.read_text("utf-8"))["abilities"]


def test_fuel_table_vocabulary_is_valid() -> None:
    """Every filter field, flag, and shape validates against the closed sets."""
    assert learnset_skeleton.validate_fuel_table() == []


def test_fuel_table_ids_are_real_abilities() -> None:
    """Every table key names an ability that exists in base or the Ruleset."""
    known = set(_all_abilities())
    stale = sorted(set(_fuel_table()) - known)
    assert not stale, f"fuel entries for nonexistent abilities: {stale}"


def test_fuel_table_named_moves_exist() -> None:
    """Every named_moves / filter.moves name is a real base-or-Ruleset move."""
    moves = _all_move_names()
    problems = []
    for aid, spec in _fuel_table().items():
        named = list(spec.get("named_moves") or [])
        named += list((spec.get("filter") or {}).get("moves") or [])
        for name in named:
            if name.casefold() not in moves:
                problems.append(f"{aid}: unknown move {name!r}")
    assert not problems, problems


def test_every_fuel_shaped_ability_is_classified() -> None:
    """The coverage tripwire: a fuel-shaped description must have a table entry.

    Failing here means a new ability landed without a fuel classification.
    Add it to ability_fuel.json (hard/soft/stab_grant), or — only if it is
    genuinely defensive — to _DELIBERATELY_UNFUELED with a reason.
    """
    table = _fuel_table()
    unclassified = sorted(
        aid
        for aid, desc in _all_abilities().items()
        if _FUEL_SHAPED.search(desc)
        and aid not in table
        and aid not in _DELIBERATELY_UNFUELED
    )
    assert not unclassified, (
        f"fuel-shaped abilities missing from ability_fuel.json: {unclassified}"
    )
