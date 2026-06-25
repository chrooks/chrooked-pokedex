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
