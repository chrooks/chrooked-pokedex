"""Unit tests for per-Target holds (model/holds.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from chrooked_pokedex.model.holds import HoldSet, load_holds


def _write_holds(tmp_path: Path, slug: str, body: str) -> Path:
    target_dir = tmp_path / "targets" / slug
    target_dir.mkdir(parents=True)
    (target_dir / "holds.yaml").write_text(body, encoding="utf-8")
    return tmp_path


@pytest.mark.unit
def test_no_slug_returns_empty(tmp_path: Path) -> None:
    assert load_holds(tmp_path, None).held == {}


@pytest.mark.unit
def test_absent_file_returns_empty(tmp_path: Path) -> None:
    assert load_holds(tmp_path, "africanvs").held == {}


@pytest.mark.unit
def test_valid_file_builds_map(tmp_path: Path) -> None:
    ruleset = _write_holds(
        tmp_path,
        "africanvs",
        "holds:\n"
        "  - id: gothita\n"
        "    categories: [species, abilities, learnset]\n",
    )
    holds = load_holds(ruleset, "africanvs")
    assert holds.is_held("gothita", "learnset")
    assert holds.is_held("gothita", "abilities")
    assert not holds.is_held("gothita", "evolution")
    assert not holds.is_held("gothorita", "learnset")


@pytest.mark.unit
def test_unknown_category_raises(tmp_path: Path) -> None:
    ruleset = _write_holds(
        tmp_path,
        "africanvs",
        "holds:\n  - id: gothita\n    categories: [bogus]\n",
    )
    with pytest.raises(ValueError, match="unknown hold category"):
        load_holds(ruleset, "africanvs")


@pytest.mark.unit
def test_missing_id_raises(tmp_path: Path) -> None:
    ruleset = _write_holds(
        tmp_path, "africanvs", "holds:\n  - categories: [species]\n"
    )
    with pytest.raises(ValueError, match="missing 'id'"):
        load_holds(ruleset, "africanvs")


@pytest.mark.unit
def test_empty_holdset_holds_nothing() -> None:
    assert not HoldSet().is_held("gothita", "species")


@pytest.mark.unit
def test_hold_filtered_ruleset_clears_held_fields() -> None:
    """Display filter: held species/learnset categories are cleared so the backdrop
    falls through to the Target's own data; unheld species are untouched."""
    import dataclasses
    from chrooked_pokedex.model.holds import hold_filtered_ruleset
    from chrooked_pokedex.model.ruleset import Ruleset
    from chrooked_pokedex.model.schema import (
        AbilitiesOverride, AbilityDef, LearnsetMove, SpeciesOverride,
    )

    gothorita = SpeciesOverride(
        name="Gothorita", chrooked_id="gothorita",
        types=("Psychic",),
        abilities=AbilitiesOverride(primary="Starfall", secondary="Competitive"),
        stats={"hp": 70},
        learnset=(LearnsetMove(level=1, move="Pound"),),
    )
    pikachu = SpeciesOverride(name="Pikachu", chrooked_id="pikachu", types=("Electric",))
    ruleset = Ruleset(
        species={"gothorita": gothorita, "pikachu": pikachu},
        abilities={"starfall": AbilityDef(name="Starfall", chrooked_id="starfall")},
    )
    holds = HoldSet(held={"gothorita": frozenset({"species", "learnset"})})

    filtered = hold_filtered_ruleset(ruleset, holds)
    g = filtered.species["gothorita"]
    assert g.types is None and g.abilities is None and g.stats is None  # species held
    assert g.learnset is None  # learnset held
    # Unheld species untouched; ability definitions not held here.
    assert filtered.species["pikachu"].types == ("Electric",)
    assert "starfall" in filtered.abilities
    # Empty holds → identical object.
    assert hold_filtered_ruleset(ruleset, HoldSet()) is ruleset
