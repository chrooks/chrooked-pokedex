"""Unit tests for per-Target additive edits (model/target_edits.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from chrooked_pokedex.model.target_edits import (
    LearnsetAddition,
    TargetEdits,
    load_target_edits,
)


def _write_edits(tmp_path: Path, slug: str, body: str) -> Path:
    target_dir = tmp_path / "targets" / slug
    target_dir.mkdir(parents=True)
    (target_dir / "edits.yaml").write_text(body, encoding="utf-8")
    return tmp_path


@pytest.mark.unit
def test_no_slug_returns_empty(tmp_path: Path) -> None:
    assert load_target_edits(tmp_path, None).learnset_add == {}


@pytest.mark.unit
def test_absent_file_returns_empty(tmp_path: Path) -> None:
    assert load_target_edits(tmp_path, "africanvs").learnset_add == {}


@pytest.mark.unit
def test_valid_file_builds_additions(tmp_path: Path) -> None:
    ruleset = _write_edits(
        tmp_path,
        "africanvs",
        "learnset_add:\n"
        "  - id: gothita\n"
        "    moves:\n"
        "      - { level: 1, move: Water Whip }\n",
    )
    edits = load_target_edits(ruleset, "africanvs")
    assert edits.learnset_additions("gothita") == (
        LearnsetAddition(level=1, move="Water Whip"),
    )
    assert edits.learnset_additions("gothorita") == ()


@pytest.mark.unit
def test_move_missing_level_raises(tmp_path: Path) -> None:
    ruleset = _write_edits(
        tmp_path,
        "africanvs",
        "learnset_add:\n  - id: gothita\n    moves:\n      - { move: Water Whip }\n",
    )
    with pytest.raises(ValueError, match="needs both 'level' and 'move'"):
        load_target_edits(ruleset, "africanvs")


@pytest.mark.unit
def test_missing_id_raises(tmp_path: Path) -> None:
    ruleset = _write_edits(
        tmp_path,
        "africanvs",
        "learnset_add:\n  - moves:\n      - { level: 1, move: Water Whip }\n",
    )
    with pytest.raises(ValueError, match="missing 'id'"):
        load_target_edits(ruleset, "africanvs")


@pytest.mark.unit
def test_empty_target_edits() -> None:
    assert TargetEdits().learnset_additions("gothita") == ()
