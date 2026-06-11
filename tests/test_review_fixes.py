"""Regression tests for issues found in the review fan-out."""

from pathlib import Path

import pytest

from chrooked_pokedex.appliers.pokeemerald import c_edit
from chrooked_pokedex.appliers.pokeemerald.git_guard import (
    DirtyWorkingTree,
    require_clean_git_status,
)
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.seed.writer import _scalar


# --- loader fail-fast validation (nothing silently dropped) ---


def _write_ruleset(tmp_path: Path, species: str = "", move: str = "") -> Path:
    root = tmp_path / "ruleset"
    (root / "species").mkdir(parents=True)
    (root / "moves").mkdir(parents=True)
    (root / "meta.yaml").write_text("base_version: 1.11.2\nschema_version: 1\n")
    if species:
        (root / "species" / "x.yaml").write_text(species)
    if move:
        (root / "moves" / "m.yaml").write_text(move)
    return root


def test_unknown_stat_key_raises(tmp_path: Path) -> None:
    root = _write_ruleset(
        tmp_path,
        species="name: X\nchrooked_id: x\nstats: { spee: 90 }\n",  # 'spee' typo
    )
    with pytest.raises(ValueError) as excinfo:
        Ruleset.load(root)
    assert "spee" in str(excinfo.value)


def test_invalid_move_category_raises(tmp_path: Path) -> None:
    root = _write_ruleset(
        tmp_path,
        move="name: M\nchrooked_id: m\ntype: Steel\ncategory: phyiscal\n",  # typo
    )
    with pytest.raises(ValueError) as excinfo:
        Ruleset.load(root)
    assert "phyiscal" in str(excinfo.value)


# --- c_edit string-awareness: braces/commas inside C string literals ---


def test_find_species_entry_ignores_brace_in_string() -> None:
    text = """\
    [SPECIES_NIDORAN_F] =
    {
        .speciesName = _("Nidoran{F}"),
        .baseHP = 55,
    },
"""
    span = c_edit.find_species_entry(text, "SPECIES_NIDORAN_F")
    assert span is not None
    body = text[span[0] + 1 : span[1]]
    # The whole body was captured despite the '{' inside the string.
    assert ".baseHP = 55," in body


def test_field_value_end_ignores_comma_in_string() -> None:
    body = '\n        .description = _("A, B, and C"),\n        .baseHP = 10,\n'
    # The description's value must include the full quoted string, not stop at the
    # first comma inside it.
    assert c_edit.get_field(body, "description") == '_("A, B, and C")'
    assert c_edit.get_field(body, "baseHP") == "10"


# --- writer YAML quoting for special leading characters ---


def test_scalar_quotes_special_leading_chars() -> None:
    assert _scalar("[bracketed]").startswith('"')
    assert _scalar("*starred").startswith('"')
    assert _scalar("normal text") == "normal text"


# --- git guard ---


def test_git_guard_blocks_dirty_tree(tmp_path: Path) -> None:
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "file.txt").write_text("dirty")
    with pytest.raises(DirtyWorkingTree):
        require_clean_git_status(repo, force=False)


def test_git_guard_force_bypasses_dirty_tree(tmp_path: Path) -> None:
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "file.txt").write_text("dirty")
    require_clean_git_status(repo, force=True)  # no raise


def test_git_guard_allows_non_git_target(tmp_path: Path) -> None:
    # A non-git directory has no tracked state to protect; allowed by design.
    require_clean_git_status(tmp_path, force=False)  # no raise
