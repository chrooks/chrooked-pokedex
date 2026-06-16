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

from chrooked_pokedex.appliers.essentials162 import pbs_io

_ENV = "AFRICANVS_PBS"
_FILES = ("pokemon.txt", "types.txt", "moves.txt", "abilities.txt")

pytestmark = pytest.mark.integration


@pytest.fixture
def real_pbs() -> Path:
    raw = os.environ.get(_ENV)
    if not raw:
        pytest.skip(f"{_ENV} not set; skipping real-game-dir integration test")
    pbs = Path(raw)
    if not pbs.is_dir():
        pytest.skip(f"{_ENV}={raw!r} is not a directory")
    return pbs


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
