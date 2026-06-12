"""PBS read + edit primitives for the Essentials Applier.

Essentials PBS files are INI-like: a section starts at a `[INTERNAL_NAME]` line and
runs until the next one. Each line is `Key = value`. These primitives parse sections
and do whole-line field replacement inside one section without disturbing the rest of
the file — the Essentials analogue of the pokeemerald `c_edit` surgical editor.
"""

from chrooked_pokedex.appliers.essentials import pbs_edit, pbs_read

_PBS = """\
# A comment header.
[BULBASAUR]
Name = Bulbasaur
Types = GRASS,POISON
BaseStats = 45,49,49,45,65,65
Abilities = OVERGROW
HiddenAbilities = CHLOROPHYLL
Moves = 1,TACKLE,1,GROWL,3,VINEWHIP

[IVYSAUR]
Name = Ivysaur
Types = GRASS,POISON
BaseStats = 60,62,63,60,80,80
Abilities = OVERGROW
"""


def test_parse_sections_preserves_order_and_fields():
    sections = pbs_read.parse_sections(_PBS)
    headers = [h for h, _ in sections]
    assert headers == ["BULBASAUR", "IVYSAUR"]
    bulba = dict(sections[0][1])
    assert bulba["Name"] == "Bulbasaur"
    assert bulba["Types"] == "GRASS,POISON"
    assert bulba["BaseStats"] == "45,49,49,45,65,65"


def test_section_headers_helper():
    assert pbs_read.section_headers(_PBS) == {"BULBASAUR", "IVYSAUR"}


def test_name_to_header_map():
    # Resolution needs display-Name -> INTERNAL (learnsets cite moves by display name).
    mapping = pbs_read.name_to_header(_PBS)
    assert mapping["bulbasaur"] == "BULBASAUR"
    assert mapping["ivysaur"] == "IVYSAUR"


def test_find_section_span_and_missing():
    span = pbs_edit.find_section(_PBS, "BULBASAUR")
    assert span is not None
    block = _PBS[span[0]:span[1]]
    assert block.startswith("[BULBASAUR]")
    assert "[IVYSAUR]" not in block  # stops at the next section
    assert pbs_edit.find_section(_PBS, "MISSINGNO") is None


def test_get_field():
    span = pbs_edit.find_section(_PBS, "BULBASAUR")
    block = _PBS[span[0]:span[1]]
    assert pbs_edit.get_field(block, "Types") == "GRASS,POISON"
    assert pbs_edit.get_field(block, "Nonexistent") is None


def test_set_field_replaces_only_target_section():
    new = pbs_edit.set_section_field(_PBS, "BULBASAUR", "Types", "GRASS,FAIRY")
    # Bulbasaur changed...
    bulba_span = pbs_edit.find_section(new, "BULBASAUR")
    assert pbs_edit.get_field(new[bulba_span[0]:bulba_span[1]], "Types") == "GRASS,FAIRY"
    # ...Ivysaur untouched.
    ivy_span = pbs_edit.find_section(new, "IVYSAUR")
    assert pbs_edit.get_field(new[ivy_span[0]:ivy_span[1]], "Types") == "GRASS,POISON"


def test_set_field_inserts_when_absent():
    new = pbs_edit.set_section_field(_PBS, "IVYSAUR", "HiddenAbilities", "CHLOROPHYLL")
    span = pbs_edit.find_section(new, "IVYSAUR")
    assert pbs_edit.get_field(new[span[0]:span[1]], "HiddenAbilities") == "CHLOROPHYLL"


def test_set_comma_field_index():
    # BaseStats in Essentials order is HP,ATK,DEF,SPEED,SPATK,SPDEF.
    new, applied = pbs_edit.set_comma_index(_PBS, "BULBASAUR", "BaseStats", 3, "99")
    assert applied is True
    span = pbs_edit.find_section(new, "BULBASAUR")
    assert pbs_edit.get_field(new[span[0]:span[1]], "BaseStats") == "45,49,49,99,65,65"


def test_set_comma_index_reports_failure_when_field_absent():
    # Field missing -> no-op, and the caller is told (applied=False) so it can report.
    new, applied = pbs_edit.set_comma_index(_PBS, "IVYSAUR", "BaseStats", 9, "99")
    assert applied is False  # index out of range
    new2, applied2 = pbs_edit.set_comma_index(_PBS, "BULBASAUR", "Nonexistent", 0, "x")
    assert applied2 is False  # field absent
    assert new2 == _PBS
