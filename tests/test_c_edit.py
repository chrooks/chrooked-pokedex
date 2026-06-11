from chrooked_pokedex.appliers.pokeemerald import c_edit

_ENTRY = """\
    [SPECIES_GOODRA] =
    {
        .baseHP = 90,
        .types = MON_TYPES(TYPE_DRAGON),
        .abilities = {ABILITY_SAP_SIPPER, ABILITY_HYDRATION, ABILITY_GOOEY},
    },
    [SPECIES_OTHER] =
    {
        .baseHP = 10,
    },
"""


def test_find_species_entry_brace_form() -> None:
    span = c_edit.find_species_entry(_ENTRY, "SPECIES_GOODRA")
    assert span is not None
    open_brace, close_brace = span
    assert _ENTRY[open_brace] == "{"
    assert _ENTRY[close_brace] == "}"


def test_find_species_entry_macro_form_returns_none() -> None:
    text = "    [SPECIES_UNOWN] = UNOWN_MISC_INFO(TYPE_PSYCHIC),\n"
    assert c_edit.find_species_entry(text, "SPECIES_UNOWN") is None


def test_set_field_replaces_in_place() -> None:
    span = c_edit.find_species_entry(_ENTRY, "SPECIES_GOODRA")
    body = _ENTRY[span[0] + 1 : span[1]]
    new_body = c_edit.set_field(body, "types", "MON_TYPES(TYPE_DRAGON, TYPE_WATER)")
    assert "MON_TYPES(TYPE_DRAGON, TYPE_WATER)" in new_body
    assert "MON_TYPES(TYPE_DRAGON)," not in new_body
    # untouched fields survive
    assert ".baseHP = 90," in new_body


def test_set_field_replaces_array_value_wholesale() -> None:
    span = c_edit.find_species_entry(_ENTRY, "SPECIES_GOODRA")
    body = _ENTRY[span[0] + 1 : span[1]]
    new_body = c_edit.set_field(
        body, "abilities", "{ABILITY_POISON_HEAL, ABILITY_HYDRATION, ABILITY_GOOEY}"
    )
    assert "ABILITY_POISON_HEAL" in new_body
    assert "ABILITY_SAP_SIPPER" not in new_body


def test_set_field_inserts_when_absent() -> None:
    span = c_edit.find_species_entry(_ENTRY, "SPECIES_OTHER")
    body = _ENTRY[span[0] + 1 : span[1]]
    new_body = c_edit.set_field(body, "types", "MON_TYPES(TYPE_NORMAL)")
    assert ".types = MON_TYPES(TYPE_NORMAL)," in new_body
    assert ".baseHP = 10," in new_body


def test_replace_entry_body_round_trips() -> None:
    span = c_edit.find_species_entry(_ENTRY, "SPECIES_GOODRA")
    body = _ENTRY[span[0] + 1 : span[1]]
    new_body = c_edit.set_field(body, "baseHP", "95")
    result = c_edit.replace_entry_body(_ENTRY, span, new_body)
    assert ".baseHP = 95," in result
    # the other species entry is undisturbed
    assert ".baseHP = 10," in result
    assert result.count("[SPECIES_OTHER]") == 1
