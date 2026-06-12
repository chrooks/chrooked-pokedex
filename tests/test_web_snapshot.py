"""Milestone 0 — the committed base snapshot.

`web/snapshot.py` turns base 1.11.2 into a deterministic JSON the Canon dex
merges onto. These tests pin the write/load round-trip and idempotency with a
synthetic snapshot dict, and exercise the real reader path only when the base
checkout is present (integration).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chrooked_pokedex.web import snapshot as snap

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE = _REPO_ROOT.parent / "ROMs" / "_scratch-expansion-1.11.2"

_TINY = {
    "version": "1.11.2",
    "species": {
        "goodra": {
            "dex": 706,
            "chrooked_id": "goodra",
            "name": "Goodra",
            "types": ["Dragon"],
            "abilities": {"primary": "Sap Sipper", "secondary": None, "hidden": "Hydration"},
            "stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 60},
            "learnset": [{"level": 1, "move": "Dragon Breath"}],
        },
    },
    "moves": {},
    "abilities": {},
    "type_chart": [],
}


def test_write_then_load_roundtrips(tmp_path: Path) -> None:
    out = tmp_path / "1.11.2.json"
    snap.write_snapshot(_TINY, out)
    assert snap.load_snapshot(out) == _TINY


def test_write_is_deterministic_and_idempotent(tmp_path: Path) -> None:
    out = tmp_path / "1.11.2.json"
    snap.write_snapshot(_TINY, out)
    first = out.read_bytes()
    snap.write_snapshot(_TINY, out)
    assert out.read_bytes() == first  # byte-identical on a second run


def test_write_creates_missing_parent_dir(tmp_path: Path) -> None:
    out = tmp_path / ".base" / "1.11.2.json"
    snap.write_snapshot(_TINY, out)
    assert out.exists()


def test_national_dex_map_is_positional_and_ignores_trailing_defines(tmp_path: Path) -> None:
    header = tmp_path / "include" / "constants" / "pokedex.h"
    header.parent.mkdir(parents=True)
    header.write_text(
        "enum {\n"
        "    NATIONAL_DEX_NONE,\n"
        "    NATIONAL_DEX_BULBASAUR,\n"
        "    NATIONAL_DEX_IVYSAUR,\n"
        "};\n"
        # A trailing #define that must NOT bump the counter.
        "#define NATIONAL_DEX_COUNT NATIONAL_DEX_IVYSAUR\n",
        encoding="utf-8",
    )
    numbers = snap._national_dex_map(tmp_path)
    assert numbers["NATIONAL_DEX_NONE"] == 0
    assert numbers["NATIONAL_DEX_BULBASAUR"] == 1
    assert numbers["NATIONAL_DEX_IVYSAUR"] == 2


def test_resolve_dex_handles_symbol_and_bare_integer() -> None:
    numbers = {"NATIONAL_DEX_GOODRA": 706}
    assert snap._resolve_dex("NATIONAL_DEX_GOODRA", numbers) == 706
    assert snap._resolve_dex("706", numbers) == 706  # some forks inline the number
    assert snap._resolve_dex(None, numbers) is None


@pytest.mark.integration
@pytest.mark.skipif(not _BASE.exists(), reason="base 1.11.2 checkout not present")
def test_build_snapshot_from_real_base() -> None:
    built = snap.build_snapshot(_BASE)
    assert built["version"] == "1.11.2"
    goodra = built["species"]["goodra"]
    assert goodra["dex"] == 706
    assert "Dragon" in goodra["types"]
    assert set(goodra["stats"]) == {"hp", "atk", "def", "spa", "spd", "spe"}
    assert goodra["learnset"]  # base Goodra learns moves
    # Pikachu rides along unchanged in the full national dex.
    assert "pikachu" in built["species"]
