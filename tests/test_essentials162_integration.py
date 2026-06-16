"""ac2(c) integration: a no-op read/write against the REAL game dir is byte-identical.

Skipped unless AFRICANVS_PBS points at a real 16.2 PBS folder. We copy each file, read
it with pbs_io, write it straight back with no edits, and assert the bytes are
unchanged — proving the byte-faithfulness holds on the full real files (hundreds of
sections), not just the small committed excerpts.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from chrooked_pokedex.appliers.essentials162 import csv_io, pbs_io, section_edit

_ENV = "AFRICANVS_PBS"
_FILES = ("pokemon.txt", "types.txt", "moves.txt", "abilities.txt")
_FIXTURES = Path(__file__).parent / "fixtures" / "essentials162"


# --- real-excerpt edit round-trip (committed fixtures, not env-gated) --------------
# These use the committed byte-faithful excerpts: a REAL edit must change exactly the
# intended line, leave BOM/CRLF intact, and leave neighbor lines byte-identical.


def test_real_excerpt_move_power_edit_changes_one_line_only():
    raw = (_FIXTURES / "moves.txt").read_bytes()
    text, had_bom = pbs_io.read(_FIXTURES / "moves.txt")
    new, applied = csv_io.set_column(text, "MEGAHORN", 4, "130")  # power 120 -> 130
    assert applied is True
    out_bytes = (b"\xef\xbb\xbf" if had_bom else b"") + new.encode("utf-8")
    assert had_bom is True  # moves.txt carries a BOM
    # Exactly one line differs: the intended MEGAHORN power change.
    before = raw.lstrip(b"\xef\xbb\xbf").split(b"\r\n")
    after = out_bytes.lstrip(b"\xef\xbb\xbf").split(b"\r\n")
    diffs = [i for i in range(len(before)) if before[i] != after[i]]
    assert len(diffs) == 1
    assert before[diffs[0]].split(b",")[1] == b"MEGAHORN"
    assert b",130," in after[diffs[0]]
    # Neighbor rows are byte-identical.
    assert before[: diffs[0]] == after[: diffs[0]]
    assert before[diffs[0] + 1 :] == after[diffs[0] + 1 :]
    # BOM + CRLF intact end to end.
    assert out_bytes.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in out_bytes


def test_real_excerpt_species_type1_edit_changes_one_line_only():
    raw = (_FIXTURES / "pokemon.txt").read_bytes()
    text, had_bom = pbs_io.read(_FIXTURES / "pokemon.txt")
    new, applied = section_edit.set_section_field(text, "BULBASAUR", "Type1", "FIRE")
    assert applied is True
    assert had_bom is False  # pokemon.txt is BOM-less
    out_bytes = new.encode("utf-8")
    before = raw.split(b"\r\n")
    after = out_bytes.split(b"\r\n")
    diffs = [i for i in range(len(before)) if before[i] != after[i]]
    assert len(diffs) == 1
    assert before[diffs[0]] == b"Type1=GRASS"
    assert after[diffs[0]] == b"Type1=FIRE"
    assert before[: diffs[0]] == after[: diffs[0]]
    assert before[diffs[0] + 1 :] == after[diffs[0] + 1 :]
    assert not out_bytes.startswith(b"\xef\xbb\xbf")  # no BOM gained
    assert b"\r\n" in out_bytes


# --- env-gated real-game-dir no-op identity (skipped without AFRICANVS_PBS) --------


@pytest.fixture
def real_pbs() -> Path:
    raw = os.environ.get(_ENV)
    if not raw:
        pytest.skip(f"{_ENV} not set; skipping real-game-dir integration test")
    pbs = Path(raw)
    if not pbs.is_dir():
        pytest.skip(f"{_ENV}={raw!r} is not a directory")
    return pbs


@pytest.mark.integration
@pytest.mark.parametrize("name", _FILES)
def test_real_file_noop_write_is_byte_identical(real_pbs, tmp_path, name):
    source = real_pbs / name
    if not source.exists():
        pytest.skip(f"{name} absent from {real_pbs}")
    work = tmp_path / name
    shutil.copy(source, work)
    text, had_bom = pbs_io.read(work)
    pbs_io.write(work, text, had_bom)
    assert work.read_bytes() == source.read_bytes()
