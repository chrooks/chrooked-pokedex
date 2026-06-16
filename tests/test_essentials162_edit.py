"""ac2(b): a single-field/single-column edit changes exactly one line, BOM/CRLF intact.

We diff the original fixture bytes against the edited bytes and assert exactly one
changed line (one unified-diff hunk of one line), with the BOM and CRLF preserved.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from chrooked_pokedex.appliers.essentials162 import (
    csv_io,
    pbs_io,
    section_edit,
    section_read,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "essentials162"


def _changed_line_count(before: str, after: str) -> int:
    """How many lines differ (added or removed) between two CRLF texts."""
    a = before.split("\r\n")
    b = after.split("\r\n")
    diff = difflib.ndiff(a, b)
    return sum(1 for line in diff if line[:1] in ("-", "+"))


# --- section edits (pokemon.txt) --------------------------------------------------

def test_set_section_field_changes_exactly_one_line():
    text, had_bom = pbs_io.read(_FIXTURES / "pokemon.txt")
    new, applied = section_edit.set_section_field(text, "BULBASAUR", "Type1", "FIRE")
    assert applied is True
    # exactly one line replaced (old Type1 line out, new Type1 line in == 2 diff lines)
    assert _changed_line_count(text, new) == 2
    assert had_bom is False  # pokemon.txt stays BOM-less
    assert "\r\n" in new and "\r\nType1=FIRE\r\n" in new  # CRLF intact, no-space `=`


def test_edit_leaves_other_section_byte_identical():
    text, _ = pbs_io.read(_FIXTURES / "pokemon.txt")
    new, _ = section_edit.set_section_field(text, "BULBASAUR", "Type1", "FIRE")
    ivy_before = section_edit.find_section_by_internalname(text, "IVYSAUR")
    ivy_after = section_edit.find_section_by_internalname(new, "IVYSAUR")
    assert text[ivy_before[0]:ivy_before[1]] == new[ivy_after[0]:ivy_after[1]]


def test_set_comma_index_changes_one_stat_only():
    text, _ = pbs_io.read(_FIXTURES / "pokemon.txt")
    new, applied = section_edit.set_comma_index(text, "BULBASAUR", "BaseStats", 3, "99")
    assert applied is True
    span = section_edit.find_section_by_internalname(new, "BULBASAUR")
    block = new[span[0]:span[1]]
    assert section_edit.get_field(block, "BaseStats") == "45,49,49,99,65,65"
    assert _changed_line_count(text, new) == 2  # one line out, one in


def test_set_section_field_missing_section_is_noop():
    text, _ = pbs_io.read(_FIXTURES / "pokemon.txt")
    new, applied = section_edit.set_section_field(text, "MISSINGNO", "Type1", "FIRE")
    assert applied is False
    assert new == text


def test_append_section_uses_next_index_and_crlf():
    text, _ = pbs_io.read(_FIXTURES / "pokemon.txt")
    next_index = section_read.max_index(text) + 1
    new = section_edit.append_section(
        text, next_index, "Name=Faketron\nInternalName=FAKETRON\nType1=NORMAL"
    )
    assert f"[{next_index}]\r\n" in new
    assert "\r\nInternalName=FAKETRON\r\n" in new
    assert section_read.max_index(new) == next_index


def test_append_section_has_no_blank_line_before_header():
    # Real 16.2 sections have EXACTLY one CRLF between the last line and the next
    # [N] header — never a blank line. Assert the exact bytes around the boundary.
    text, _ = pbs_io.read(_FIXTURES / "pokemon.txt")
    last_line = text.rstrip("\r\n").rsplit("\r\n", 1)[-1]
    next_index = section_read.max_index(text) + 1
    new = section_edit.append_section(
        text, next_index, "Name=Faketron\nInternalName=FAKETRON\nType1=NORMAL"
    )
    boundary = f"{last_line}\r\n[{next_index}]\r\n"
    assert boundary in new
    assert f"{last_line}\r\n\r\n[{next_index}]" not in new  # no doubled separator


# --- empty-value fields must not cross newlines -----------------------------------

def test_get_field_empty_value_does_not_read_next_line():
    # An empty-value field (`Type2=` with nothing after) must capture the empty value,
    # NOT consume the newline and read the following line's text.
    block = "[1]\r\nType2=\r\nType1=FIRE\r\n"
    assert section_edit.get_field(block, "Type2") == ""


def test_set_field_empty_value_does_not_clobber_next_line():
    # Setting an empty-value field must replace only its own value, leaving the
    # following line byte-identical.
    block = "[1]\r\nType2=\r\nType1=FIRE\r\n"
    new = section_edit.set_field(block, "Type2", "POISON")
    assert new == "[1]\r\nType2=POISON\r\nType1=FIRE\r\n"


# --- CSV edits (moves.txt / abilities.txt) ----------------------------------------

def test_set_column_changes_exactly_one_line_with_bom_and_crlf():
    text, had_bom = pbs_io.read(_FIXTURES / "moves.txt")
    new, applied = csv_io.set_column(text, "MEGAHORN", 4, "130")  # power 120 -> 130
    assert applied is True
    assert had_bom is True
    assert _changed_line_count(text, new) == 2  # one row line out, one in
    assert csv_io.get_column(new, "MEGAHORN", 4) == "130"


def test_set_column_leaves_quoted_description_untouched():
    text, _ = pbs_io.read(_FIXTURES / "moves.txt")
    desc_before = csv_io.get_column(text, "MEGAHORN", 13)
    new, _ = csv_io.set_column(text, "MEGAHORN", 4, "130")
    assert csv_io.get_column(new, "MEGAHORN", 13) == desc_before  # Spanish desc intact


def test_set_column_leaves_other_rows_byte_identical():
    text, _ = pbs_io.read(_FIXTURES / "moves.txt")
    new, _ = csv_io.set_column(text, "MEGAHORN", 4, "130")
    other_before = csv_io.find_row(text, "BUGBUZZ")
    other_after = csv_io.find_row(new, "BUGBUZZ")
    assert text[other_before[0]:other_before[1]] == new[other_after[0]:other_after[1]]


def test_set_column_missing_row_is_noop():
    text, _ = pbs_io.read(_FIXTURES / "moves.txt")
    new, applied = csv_io.set_column(text, "NOTAMOVE", 4, "130")
    assert applied is False
    assert new == text


def test_set_column_comma_value_preserves_column_count():
    # A value containing a comma must NOT shift later columns: it round-trips back to
    # the same value and keeps the row's column count intact (auto-quoted on write).
    text, _ = pbs_io.read(_FIXTURES / "moves.txt")
    before_cols = len(csv_io.split_columns(_row(text, "MEGAHORN")))
    new, applied = csv_io.set_column(text, "MEGAHORN", 13, "Embiste, con fuerza.")
    assert applied is True
    after_cols = len(csv_io.split_columns(_row(new, "MEGAHORN")))
    assert after_cols == before_cols  # comma did not create a phantom column
    assert csv_io.get_column(new, "MEGAHORN", 13) == '"Embiste, con fuerza."'


def test_set_column_round_trips_embedded_escaped_quote():
    # A description with a `""` escaped quote must survive a round-trip read of the
    # same column unchanged (no column shift, no quote mangling).
    text, _ = pbs_io.read(_FIXTURES / "moves.txt")
    value = '"Dice ""hola"", y ataca."'
    new, applied = csv_io.set_column(text, "MEGAHORN", 13, value)
    assert applied is True
    assert csv_io.get_column(new, "MEGAHORN", 13) == value
    # the row still splits into the same number of columns
    assert len(csv_io.split_columns(_row(new, "MEGAHORN"))) == 14


def _row(text: str, internal: str) -> str:
    span = csv_io.find_row(text, internal)
    assert span is not None
    return text[span[0]:span[1]]


def test_append_row_uses_next_index_and_crlf():
    text, _ = pbs_io.read(_FIXTURES / "abilities.txt")
    next_index = csv_io.max_index(text) + 1
    new = csv_io.append_row(text, f'{next_index},FAKEPOWER,Falso,"Una habilidad inventada."')
    assert new.endswith('"Una habilidad inventada."\r\n')
    assert csv_io.max_index(new) == next_index
