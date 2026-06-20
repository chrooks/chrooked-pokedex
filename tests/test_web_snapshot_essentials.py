"""Issue #38 + #40 — the engine-aware per-Target backdrop snapshot for Essentials.

`web/snapshot_essentials.py` reads an Essentials `PBS/` tree into the same
neutral snapshot dict the backdrop merge consumes, dialect-routed (16.2 vs
modern v21). `TargetState.snapshot_for` routes essentials targets to it and
leaves the pokeemerald path untouched.

#40 corrects two defects shipped by #38:

* the 16.2 moves reader read the FunctionCode column as the type (junk ``000``
  badge) and shifted every later column — fixed to the REAL Africanvs layout;
* the join key was ``slug(display Name)`` — localized, so a Spanish target
  produced foreign duplicates instead of overlaying the English base. The key
  is now ``slug(InternalName)``, the language-neutral symbol.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.seed import neutralize as nz
from chrooked_pokedex.web import snapshot as snapmod
from chrooked_pokedex.web import snapshot_essentials as snapesmod
from chrooked_pokedex.web import targets as targetsmod
from chrooked_pokedex.web.snapshot_essentials import build_snapshot_essentials
from chrooked_pokedex.web.targets import Target, TargetState

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "essentials_dialect"
_ENGLISH_162 = _FIXTURES / "english_162"
_SPANISH_162 = _FIXTURES / "spanish_162"
_MODERN_V21 = _FIXTURES / "modern_v21"


def _essentials_target(path: Path) -> Target:
    return Target(id="ess1", label="Essentials", path=str(path), engine="essentials")


def _empty_ruleset() -> Ruleset:
    return Ruleset()


# --- ac1: real 16.2 move columns; no junk '000' type ------------------------ #


def test_ac1_spanish_megahorn_reads_real_16_2_move_columns() -> None:
    """A Spanish-named move reads Type/Category/Power/Accuracy/PP from the REAL layout."""
    snap = build_snapshot_essentials(_SPANISH_162)
    megahorn = snap["moves"]["megahorn"]
    assert megahorn["type"] == "Bug"
    assert megahorn["category"] == "physical"
    assert megahorn["power"] == 120
    assert megahorn["accuracy"] == 85
    assert megahorn["pp"] == 10
    # The display label stays localized while the join key is language-neutral.
    assert megahorn["name"] == "Megacuerno"


def test_ac1_no_move_reads_function_code_as_type() -> None:
    """No move's type is the FunctionCode junk ('000') or empty — the #38 defect."""
    for fixture in (_ENGLISH_162, _SPANISH_162):
        snap = build_snapshot_essentials(fixture)
        assert snap["moves"], f"{fixture.name} produced no moves"
        for move in snap["moves"].values():
            assert move["type"] not in ("000", ""), (
                f"{fixture.name} move {move['chrooked_id']} has junk type {move['type']!r}"
            )


# --- ac2: InternalName join — overlay, not foreign duplicate ---------------- #


def test_ac2_internal_name_join_keys_equal_base_keys() -> None:
    """Spanish entries key on slug(InternalName), equal to the English base key."""
    snap = build_snapshot_essentials(_SPANISH_162)

    # MEGAHORN -> 'megahorn', STENCH -> 'stench', BULBASAUR -> 'bulbasaur'.
    assert "megahorn" in snap["moves"]
    assert "stench" in snap["abilities"]
    assert "bulbasaur" in snap["species"]

    # Each Essentials key equals slug(InternalName) — the exact chrooked_id the
    # pokeemerald base produces — so a localized target overlays, not duplicates.
    assert snap["moves"]["megahorn"]["chrooked_id"] == nz.slug("MEGAHORN")
    assert snap["abilities"]["stench"]["chrooked_id"] == nz.slug("STENCH")
    assert snap["species"]["bulbasaur"]["chrooked_id"] == nz.slug("BULBASAUR")

    # And NOT keyed on the localized display name (the #38 foreign-duplicate bug).
    assert "megacuerno" not in snap["moves"]
    assert "hedor" not in snap["abilities"]


def test_ac2_target_dex_renders_bulbasaur_correctly() -> None:
    """Backdrop dex contains Bulbasaur with its real types and stats."""
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


# --- ac3: rebuilt english_162 + new spanish fixture render ------------------ #


def test_ac3_english_162_real_schema_resolves_type() -> None:
    """The rebuilt english_162 (real columns) resolves MEGAHORN's Bug type."""
    snap = build_snapshot_essentials(_ENGLISH_162)
    megahorn = snap["moves"]["megahorn"]
    assert megahorn["type"] == "Bug"
    assert megahorn["power"] == 120
    assert megahorn["name"] == "Megahorn"


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


def test_ac3_both_dialects_read_species_and_routing_dispatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """16.2 and modern v21 both populate species; snapshot_for routes essentials."""
    snap_162 = build_snapshot_essentials(_ENGLISH_162)
    snap_v21 = build_snapshot_essentials(_MODERN_V21)
    assert snap_162["species"], "16.2 fixture produced no species"
    assert snap_v21["species"], "modern v21 fixture produced no species"

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


def test_ac3_v21_internal_name_is_the_join_key() -> None:
    """For v21 the section header IS the internal name — it must become the key."""
    snap = build_snapshot_essentials(_MODERN_V21)
    assert "bulbasaur" in snap["species"]
    assert "tackle" in snap["moves"]
    assert snap["moves"]["tackle"]["type"] == "Normal"


# --- ac4: pokeemerald path untouched ---------------------------------------- #


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
