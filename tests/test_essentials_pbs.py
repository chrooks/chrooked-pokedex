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


# --- multi-line whole-key writer (Essentials `Evolution =` lives one-per-line) ---

_EVO_PBS = """\
[EEVEE]
Name = Eevee
BaseStats = 55,55,50,55,45,65
Evolution = VAPOREON,Item,WATERSTONE
Evolution = JOLTEON,Item,THUNDERSTONE
Evolution = FLAREON,Item,FIRESTONE

[VAPOREON]
Name = Vaporeon
BaseStats = 130,65,60,65,110,95
"""


def test_get_section_values_returns_every_repeated_key():
    span = pbs_edit.find_section(_EVO_PBS, "EEVEE")
    block = _EVO_PBS[span[0]:span[1]]
    values = pbs_edit.get_section_values(block, "Evolution")
    assert values == [
        "VAPOREON,Item,WATERSTONE",
        "JOLTEON,Item,THUNDERSTONE",
        "FLAREON,Item,FIRESTONE",
    ]


def test_set_section_lines_replaces_all_key_lines():
    new_text, applied = pbs_edit.set_section_lines(
        _EVO_PBS, "EEVEE", "Evolution",
        ["ESPEON,HappinessDay", "UMBREON,HappinessNight"],
    )
    assert applied is True
    span = pbs_edit.find_section(new_text, "EEVEE")
    block = new_text[span[0]:span[1]]
    assert pbs_edit.get_section_values(block, "Evolution") == [
        "ESPEON,HappinessDay", "UMBREON,HappinessNight",
    ]
    # The neighbouring section is untouched.
    assert "[VAPOREON]" in new_text
    assert pbs_edit.get_field(block, "Name") == "Eevee"  # other keys survive


def test_set_section_lines_is_idempotent_for_identical_set():
    same = [
        "VAPOREON,Item,WATERSTONE",
        "JOLTEON,Item,THUNDERSTONE",
        "FLAREON,Item,FIRESTONE",
    ]
    new_text, applied = pbs_edit.set_section_lines(_EVO_PBS, "EEVEE", "Evolution", same)
    assert applied is False
    assert new_text == _EVO_PBS  # no churn when the desired set already matches


def test_set_section_lines_inserts_when_key_absent():
    text = "[VAPOREON]\nName = Vaporeon\nBaseStats = 130,65,60,65,110,95\n"
    new_text, applied = pbs_edit.set_section_lines(text, "VAPOREON", "Evolution", ["FOO,Level,5"])
    assert applied is True
    span = pbs_edit.find_section(new_text, "VAPOREON")
    assert pbs_edit.get_section_values(new_text[span[0]:span[1]], "Evolution") == ["FOO,Level,5"]


def test_set_section_lines_missing_section_is_noop():
    new_text, applied = pbs_edit.set_section_lines(_EVO_PBS, "NOPE", "Evolution", ["X,Level,5"])
    assert applied is False
    assert new_text == _EVO_PBS


def test_remove_section_field_drops_the_line():
    text = "[FIRE]\nName = Fire\nWeaknesses = WATER\nResistances = GRASS\n"
    new_text, removed = pbs_edit.remove_section_field(text, "FIRE", "Weaknesses")
    assert removed is True
    span = pbs_edit.find_section(new_text, "FIRE")
    block = new_text[span[0]:span[1]]
    assert pbs_edit.get_field(block, "Weaknesses") is None
    assert pbs_edit.get_field(block, "Resistances") == "GRASS"  # neighbour key intact


def test_remove_section_field_absent_key_is_noop():
    text = "[FIRE]\nName = Fire\n"
    new_text, removed = pbs_edit.remove_section_field(text, "FIRE", "Weaknesses")
    assert removed is False
    assert new_text == text


def test_set_section_lines_empty_values_raises_not_wipes():
    # Emptying every line of a key is data destruction by another name; the writer
    # must refuse it (remove_section_field is the deliberate path), never wipe silently.
    import pytest
    with pytest.raises(ValueError):
        pbs_edit.set_section_lines(_EVO_PBS, "EEVEE", "Evolution", [])
