"""Content fingerprint primitive shared by the dex cache (#59) and the
apply-preview cache (#63). The key property: the hash changes iff a file's bytes
change, and is stable across repeated reads of unchanged content."""

from __future__ import annotations

from pathlib import Path

import pytest

from chrooked_pokedex.fingerprint import hash_files, hash_ruleset_dir


@pytest.mark.unit
def test_hash_ruleset_dir_stable_across_reads(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("x: 1\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.yaml").write_text("y: 2\n")

    first = hash_ruleset_dir(tmp_path)
    assert hash_ruleset_dir(tmp_path) == first  # deterministic, no clock dependence


@pytest.mark.unit
def test_hash_ruleset_dir_changes_when_content_changes(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("x: 1\n")
    before = hash_ruleset_dir(tmp_path)

    (tmp_path / "a.yaml").write_text("x: 2\n")  # one byte differs
    assert hash_ruleset_dir(tmp_path) != before


@pytest.mark.unit
def test_hash_ruleset_dir_changes_when_file_added(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("x: 1\n")
    before = hash_ruleset_dir(tmp_path)

    (tmp_path / "c.yaml").write_text("z: 3\n")
    assert hash_ruleset_dir(tmp_path) != before


@pytest.mark.unit
def test_hash_files_order_independent(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("aaa")
    b.write_text("bbb")
    # Same set, different argument order → same hash (sorted internally).
    assert hash_files([a, b], tmp_path) == hash_files([b, a], tmp_path)


@pytest.mark.unit
def test_hash_files_empty_set_is_stable(tmp_path: Path) -> None:
    assert hash_files([], tmp_path) == hash_files([], tmp_path)
