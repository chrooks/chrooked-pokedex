"""ac1 + ac2: byte-faithful read/write and round-trip-clean parsing of 16.2 PBS.

Fixtures under tests/fixtures/essentials162/ are byte-faithful excerpts of the real
Africanvs PBS: pokemon.txt has NO BOM, the rest carry a BOM, all use CRLF, and the
CSV descriptions are double-quoted Spanish containing commas.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chrooked_pokedex.appliers.essentials162 import (
    csv_io,
    pbs_io,
    section_edit,
    section_read,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "essentials162"
_ALL_FILES = ("pokemon.txt", "types.txt", "moves.txt", "abilities.txt")


def _raw(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


# --- pbs_io: BOM + CRLF awareness -------------------------------------------------

def test_read_reports_bom_per_file():
    # pokemon.txt has no BOM; the rest do (per-file, never assumed global).
    _, poke_bom = pbs_io.read(_FIXTURES / "pokemon.txt")
    _, types_bom = pbs_io.read(_FIXTURES / "types.txt")
    _, moves_bom = pbs_io.read(_FIXTURES / "moves.txt")
    _, ab_bom = pbs_io.read(_FIXTURES / "abilities.txt")
    assert poke_bom is False
    assert types_bom is True
    assert moves_bom is True
    assert ab_bom is True


def test_read_keeps_crlf_intact():
    text, _ = pbs_io.read(_FIXTURES / "pokemon.txt")
    assert "\r\n" in text  # newlines are preserved in-string, never normalized


@pytest.mark.parametrize("name", _ALL_FILES)
def test_noop_write_is_byte_identical(tmp_path, name):
    # ac2(a): read then write with NO edits yields byte-identical output — covers the
    # no-BOM pokemon.txt, BOM on the rest, CRLF, and quoted Spanish descriptions.
    text, had_bom = pbs_io.read(_FIXTURES / name)
    out = tmp_path / name
    pbs_io.write(out, text, had_bom)
    assert out.read_bytes() == _raw(name)


# --- ac1: round-trip-clean parse of known entities --------------------------------

def test_pokemon_parses_bulbasaur_by_internalname():
    text, _ = pbs_io.read(_FIXTURES / "pokemon.txt")
    index = section_read.internalname_to_index(text)
    assert "BULBASAUR" in index
    span = section_edit.find_section_by_internalname(text, "BULBASAUR")
    block = text[span[0]:span[1]]
    assert section_edit.get_field(block, "Type1") == "GRASS"


def test_moves_parses_megahorn_row():
    text, _ = pbs_io.read(_FIXTURES / "moves.txt")
    cols = csv_io.split_columns(csv_io_row(text, "MEGAHORN"))
    # idx,INTERNAL,Spanish,HEX,power,TYPE,cat,acc,pp,effect,target,priority,flags,"desc"
    assert cols[1] == "MEGAHORN"
    assert cols[3] == "000"  # 3-digit HEX funccode
    assert cols[12] == "abef"  # letter flags
    assert cols[13].startswith('"') and cols[13].endswith('"')  # quoted desc preserved


def test_quote_aware_splitter_keeps_comma_in_description():
    # The trailing description is double-quoted and may contain commas; a naive
    # split would break the row. The quote-aware splitter keeps it as one field.
    line = '3,BUGBUZZ,Zumbido,046,90,BUG,Special,100,10,10,00,0,befk,"Onda sónica. Baja, también, la Def. Esp."'
    cols = csv_io.split_columns(line)
    assert len(cols) == 14  # the two in-quote commas did NOT create extra columns
    assert cols[1] == "BUGBUZZ"
    assert cols[13] == '"Onda sónica. Baja, también, la Def. Esp."'
    assert "," in cols[13]  # commas survive inside the quoted field


def test_real_descriptions_are_single_quoted_fields():
    # Each committed move row's description is one double-quoted field (col 13).
    text, _ = pbs_io.read(_FIXTURES / "moves.txt")
    for internal in ("MEGAHORN", "ATTACKORDER", "BUGBUZZ", "XSCISSOR"):
        cols = csv_io.split_columns(csv_io_row(text, internal))
        assert len(cols) == 14
        assert cols[13].startswith('"') and cols[13].endswith('"')


def csv_io_row(text: str, internal: str) -> str:
    span = csv_io.find_row(text, internal)
    assert span is not None, f"row {internal} not found"
    return text[span[0]:span[1]]
