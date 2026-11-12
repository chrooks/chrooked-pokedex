"""gba-binary species apply through route_apply on a fake ROM in tmp_path."""

from __future__ import annotations

import hashlib
import json
import zlib
from pathlib import Path

import pytest

from chrooked_pokedex.appliers.dispatch import route_apply
from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.model.schema import LearnsetMove, SpeciesOverride
from chrooked_pokedex.report import ApplyReport

pytestmark = pytest.mark.unit

FIXTURE = Path(__file__).parent / "fixtures" / "gba_binary" / "monomyth.addresses.json"
BLOCKS = "chrooked.blocks.json"
TABLE = 0x08000010
STRIDE = 24
# Index 1 "Bulbasaur": Normal/Normal so a Grass/Poison Override changes type bytes.
RECORDS = [
    bytes(STRIDE),
    bytes([45, 49, 49, 45, 65, 65, 0, 0]) + bytes(range(1, 17)),
    bytes([44, 48, 65, 43, 50, 64, 11, 11]) + bytes(range(17, 33)),
]


def make_target(tmp_path: Path, sha1: str | None = None) -> Path:
    rom = bytes(16) + b"".join(RECORDS) + bytes(40)
    (tmp_path / "monomyth.gba").write_bytes(rom)
    data = json.loads(FIXTURE.read_text())
    data["rom_sha1"] = sha1 or hashlib.sha1(rom).hexdigest()
    (tmp_path / FIXTURE.name).write_text(json.dumps(data))
    return tmp_path


def sp(cid: str, name: str, **kw) -> SpeciesOverride:
    return SpeciesOverride(name=name, chrooked_id=cid, **kw)


def ruleset(*species: SpeciesOverride) -> Ruleset:
    return Ruleset(species={s.chrooked_id: s for s in species})


BULBA = sp("bulbasaur", "Bulbasaur", types=("Grass", "Poison"), stats={"hp": 60})


def apply(target: Path, rs: Ruleset) -> tuple[ApplyReport, dict | None]:
    report = ApplyReport()
    route_apply(target, "gba-binary", rs, report)
    path = target / BLOCKS
    return report, (json.loads(path.read_text()) if path.exists() else None)


def test_one_block_patched_only_at_overridden_offsets(tmp_path):
    report, out = apply(make_target(tmp_path), ruleset(BULBA))
    assert out["format"] == 1
    [block] = out["blocks"]
    assert block["address"] == f"0x{TABLE + STRIDE:08X}"
    assert block["length"] == STRIDE
    assert block["original_crc32"] == f"0x{zlib.crc32(RECORDS[1]):08X}"
    patched = bytes.fromhex(block["bytes"])
    diff = [i for i in range(STRIDE) if patched[i] != RECORDS[1][i]]
    assert diff == [0, 6, 7]
    assert (patched[0], patched[6], patched[7]) == (60, 12, 3)
    [entry] = report.entries
    assert (entry.status, entry.chrooked_id, entry.symbol) == ("applied", "bulbasaur", "#1 Bulbasaur")


def test_renamed_species_resolves_through_aka(tmp_path):
    squirtle = sp("squirtle", "Squirtle", aka={"monomyth": 2}, stats={"spe": 99})
    report, out = apply(make_target(tmp_path), ruleset(squirtle))
    [block] = out["blocks"]
    assert block["address"] == f"0x{TABLE + 2 * STRIDE:08X}"
    assert bytes.fromhex(block["bytes"])[3] == 99  # spe offset from the Addresses file
    assert report.entries[0].symbol == "#2 Mishimizu"


def test_unmatched_species_is_blocked_with_no_block(tmp_path):
    goodra = sp("goodra", "Goodra", types=("Water", "Dragon"))
    report, out = apply(make_target(tmp_path), ruleset(BULBA, goodra))
    assert len(out["blocks"]) == 1
    blocked = [e for e in report.entries if e.status == "blocked"]
    assert [e.chrooked_id for e in blocked] == ["goodra"]
    assert "Goodra" in blocked[0].reason


def test_learnset_only_species_gets_no_row(tmp_path):
    ls = sp("goodra", "Goodra", learnset=(LearnsetMove(level=1, move="Tackle"),))
    report, out = apply(make_target(tmp_path), ruleset(BULBA, ls))
    assert [e.chrooked_id for e in report.entries] == ["bulbasaur"]


def test_stat_above_255_is_blocked(tmp_path):
    big = sp("bulbasaur", "Bulbasaur", stats={"hp": 256})
    report, out = apply(make_target(tmp_path), ruleset(big))
    assert out["blocks"] == []
    assert report.entries[0].status == "blocked"


def test_unknown_type_is_partial_and_stats_still_written(tmp_path):
    odd = sp("bulbasaur", "Bulbasaur", types=("Sound",), stats={"hp": 60})
    report, out = apply(make_target(tmp_path), ruleset(odd))
    patched = bytes.fromhex(out["blocks"][0]["bytes"])
    assert patched[0] == 60 and patched[6:8] == RECORDS[1][6:8]
    assert report.entries[0].status == "partial"
    assert report.entries[0].partial_fields == ("types",)


def test_one_type_species_sets_both_type_bytes(tmp_path):
    mono = sp("bulbasaur", "Bulbasaur", types=("Grass",))
    _, out = apply(make_target(tmp_path), ruleset(mono))
    assert bytes.fromhex(out["blocks"][0]["bytes"])[6:8] == bytes([12, 12])


def test_already_matching_record_gets_no_block(tmp_path):
    same = sp("bulbasaur", "Bulbasaur", stats={"hp": 45})
    report, out = apply(make_target(tmp_path), ruleset(same))
    assert out["blocks"] == []
    assert report.entries[0].status == "applied"
    assert "already matches" in report.entries[0].reason


def test_unchanged_ruleset_leaves_blocks_file_byte_identical(tmp_path):
    target = make_target(tmp_path)
    apply(target, ruleset(BULBA))
    first = (target / BLOCKS).read_bytes()
    apply(target, ruleset(BULBA))
    assert (target / BLOCKS).read_bytes() == first


def test_wrong_rom_sha1_aborts_before_writing(tmp_path):
    target = make_target(tmp_path, sha1="f" * 40)
    report, out = apply(target, ruleset(BULBA))
    assert out is None
    [entry] = report.entries
    assert entry.status == "blocked" and entry.chrooked_id == "(all)"
    assert "sha1" in entry.reason


def test_other_category_leaves_blocks_file_alone(tmp_path):
    target = make_target(tmp_path)
    apply(target, ruleset(BULBA))
    first = (target / BLOCKS).read_bytes()
    route_apply(target, "gba-binary", ruleset(), ApplyReport(), category="moves")
    assert (target / BLOCKS).read_bytes() == first
