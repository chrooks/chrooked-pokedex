"""Issue #38 — the engine-aware per-Target backdrop snapshot for Essentials.

`web/snapshot_essentials.py` reads an Essentials `PBS/` tree into the same
neutral snapshot dict the backdrop merge consumes, dialect-routed (16.2 vs
modern v21). `TargetState.snapshot_for` routes essentials targets to it and
leaves the pokeemerald path untouched.

One test per acceptance criterion (ac1–ac4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.web import snapshot as snapmod
from chrooked_pokedex.web import snapshot_essentials as snapesmod
from chrooked_pokedex.web import targets as targetsmod
from chrooked_pokedex.web.snapshot_essentials import build_snapshot_essentials
from chrooked_pokedex.web.targets import Target, TargetState

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "essentials_dialect"
_ENGLISH_162 = _FIXTURES / "english_162"
_MODERN_V21 = _FIXTURES / "modern_v21"


def _essentials_target(path: Path) -> Target:
    return Target(id="ess1", label="Essentials", path=str(path), engine="essentials")


def _empty_ruleset() -> Ruleset:
    return Ruleset()


# --- ac1 -------------------------------------------------------------------- #


def test_ac1_both_dialects_read_species_and_routing_dispatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """16.2 and modern v21 both populate species; snapshot_for routes essentials."""
    snap_162 = build_snapshot_essentials(_ENGLISH_162)
    snap_v21 = build_snapshot_essentials(_MODERN_V21)
    assert snap_162["species"], "16.2 fixture produced no species"
    assert snap_v21["species"], "modern v21 fixture produced no species"

    # snapshot_for(essentials_target) must dispatch to build_snapshot_essentials,
    # NOT build_snapshot.
    called: dict[str, bool] = {"essentials": False, "pokeemerald": False}

    def _spy_essentials(pbs_dir: Path) -> dict:
        called["essentials"] = True
        return {"version": "essentials", "species": {}, "abilities": {},
                "moves": {}, "type_chart": []}

    def _spy_pokeemerald(base_dir: Path) -> dict:
        called["pokeemerald"] = True
        return {"version": "1.11.2", "species": {}, "abilities": {},
                "moves": {}, "type_chart": []}

    monkeypatch.setattr(
        targetsmod.snapmod_essentials, "build_snapshot_essentials", _spy_essentials
    )
    monkeypatch.setattr(targetsmod.snapmod, "build_snapshot", _spy_pokeemerald)

    state = TargetState()
    state.snapshot_for(_essentials_target(_ENGLISH_162))
    assert called["essentials"] is True
    assert called["pokeemerald"] is False


# --- ac2 -------------------------------------------------------------------- #


def test_ac2_target_dex_renders_bulbasaur_correctly() -> None:
    """Backdrop dex contains Bulbasaur with its real types and HP (not just non-empty)."""
    state = TargetState()
    target = _essentials_target(_ENGLISH_162)
    dex = targetsmod.target_dex(target, _empty_ruleset(), state)
    assert dex, "essentials backdrop dex was empty"
    bulba = next((e for e in dex if e["chrooked_id"] == "bulbasaur"), None)
    assert bulba is not None, "bulbasaur not found in backdrop dex"
    assert bulba["types"] == ["Grass", "Poison"]
    assert bulba["stats"]["hp"] == 45
    # Speed-is-index-3 gotcha: BaseStats = 45,49,49,45,65,65 -> spe=45, spa=65.
    assert bulba["stats"]["spe"] == 45
    assert bulba["stats"]["spa"] == 65


# --- ac3 -------------------------------------------------------------------- #


def test_ac3_abilities_moves_typechart_render() -> None:
    """Abilities/moves non-empty; type-chart is the full 324-cell grid."""
    state = TargetState()
    target = _essentials_target(_ENGLISH_162)
    ruleset = _empty_ruleset()

    abilities = targetsmod.target_abilities(target, ruleset, state)
    moves = targetsmod.target_moves(target, ruleset, state)
    type_chart = targetsmod.target_type_chart(target, ruleset, state)

    assert abilities, "essentials backdrop abilities was empty"
    assert moves, "essentials backdrop moves was empty"
    assert len(type_chart) == 324, f"expected 324 cells, got {len(type_chart)}"

    # A meaningful interaction: Fire attacking Grass is 2.0 (Bulbasaur is Grass).
    fire_v_grass = next(
        c for c in type_chart
        if c["attacker"] == "Fire" and c["defender"] == "Grass"
    )
    assert fire_v_grass["multiplier"] == 2.0


# --- ac4 -------------------------------------------------------------------- #


def test_ac4_pokeemerald_path_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pokeemerald target still routes to build_snapshot, not the essentials path."""
    snap = build_snapshot_essentials(_ENGLISH_162)
    assert snap["species"], "english_162 fixture produced no species"

    called: dict[str, bool] = {"essentials": False, "pokeemerald": False}

    def _spy_essentials(pbs_dir: Path) -> dict:
        called["essentials"] = True
        return {"version": "essentials", "species": {}, "abilities": {},
                "moves": {}, "type_chart": []}

    def _spy_pokeemerald(base_dir: Path) -> dict:
        called["pokeemerald"] = True
        return {"version": "1.11.2", "species": {}, "abilities": {},
                "moves": {}, "type_chart": []}

    monkeypatch.setattr(
        targetsmod.snapmod_essentials, "build_snapshot_essentials", _spy_essentials
    )
    monkeypatch.setattr(targetsmod.snapmod, "build_snapshot", _spy_pokeemerald)

    state = TargetState()
    poke_target = Target(
        id="poke1", label="Poke", path="/tmp/does-not-matter", engine="pokeemerald"
    )
    state.snapshot_for(poke_target)
    assert called["pokeemerald"] is True
    assert called["essentials"] is False
