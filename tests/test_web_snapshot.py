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


def test_eval_define_reads_plain_integer() -> None:
    assert snap._eval_define("150", {}) == 150
    assert snap._eval_define("234  // expyield", {}) == 234


def test_eval_define_resolves_config_gated_ternary() -> None:
    config = {"P_UPDATED_STATS": 8, "GEN_8": 7, "GEN_6": 5}
    # 8 >= 7 -> the modern (first) value
    assert (
        snap._eval_define("(P_UPDATED_STATS >= GEN_8 ? 140 : 150)", config) == 140
    )
    # a config below the gate takes the legacy value
    assert (
        snap._eval_define("(P_UPDATED_STATS >= GEN_8 ? 140 : 150)", {"P_UPDATED_STATS": 5, "GEN_8": 7})
        == 150
    )


def test_eval_define_returns_none_for_unsupported_shape() -> None:
    assert snap._eval_define("SOME_OTHER_MACRO", {}) is None
    assert snap._eval_define("(a + b)", {}) is None


def test_eval_expr_resolves_symbols_ternaries_and_offsets() -> None:
    symbols = {"P_UPDATED_STATS": 8, "GEN_7": 6, "ALAKAZAM_SP_DEF": 95, "CORSOLA_HP": 65}
    assert snap._eval_expr("130", symbols) == 130
    assert snap._eval_expr("ALAKAZAM_SP_DEF", symbols) == 95
    assert snap._eval_expr("P_UPDATED_STATS >= GEN_7 ? 95 : 85", symbols) == 95
    # macro with an integer offset, both directions
    assert snap._eval_expr("ALAKAZAM_SP_DEF + 10", symbols) == 105
    assert snap._eval_expr("CORSOLA_HP - 5", symbols) == 60
    assert snap._eval_expr("UNKNOWN_MACRO", symbols) is None


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


@pytest.mark.integration
@pytest.mark.skipif(not _BASE.exists(), reason="base 1.11.2 checkout not present")
def test_symbolic_form_stats_are_resolved_not_dropped() -> None:
    # Forms whose stats are named macros (AEGISLASH_MAIN_STAT etc.) must resolve
    # to their real values, not vanish. P_UPDATED_STATS = GEN_LATEST, so the
    # modern values apply (Aegislash main stat 140, Alakazam SpDef 95).
    species = snap.build_snapshot(_BASE)["species"]
    blade = species["aegislashblade"]["stats"]
    shield = species["aegislashshield"]["stats"]
    assert blade["atk"] == 140 and blade["spa"] == 140
    assert shield["def"] == 140 and shield["spd"] == 140
    # every form carries the full six stats now
    assert set(blade) == {"hp", "atk", "def", "spa", "spd", "spe"}
    assert species["alakazam"]["stats"]["spd"] == 95
