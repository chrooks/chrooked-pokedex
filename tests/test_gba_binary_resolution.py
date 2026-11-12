"""gba-binary Resolution map: Monomyth display name / aka hint -> species index."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chrooked_pokedex.appliers.gba_binary.addresses import (
    ADDRESSES_FILE,
    AddressesError,
    load_addresses,
)
from chrooked_pokedex.appliers.gba_binary.resolution import build_resolution_map

pytestmark = pytest.mark.unit

FIXTURE = Path(__file__).parent / "fixtures" / "gba_binary"


@pytest.fixture
def resmap():
    return build_resolution_map(load_addresses(FIXTURE))


def test_name_matches_case_insensitively(resmap):
    assert resmap.species({}, "bulbasaur") == 1
    assert resmap.species({}, "BULBASAUR") == 1


def test_renamed_species_is_none(resmap):
    assert resmap.species({}, "Squirtle") is None


def test_blank_slot_never_matches(resmap):
    assert resmap.species({}, "??????????") is None


def test_aka_hint_wins(resmap):
    assert resmap.species({"monomyth": 2}, "Bulbasaur") == 2


def test_out_of_range_hint_is_none(resmap):
    assert resmap.species({"monomyth": 3}, "Bulbasaur") is None
    assert resmap.species({"monomyth": 0}, "Bulbasaur") is None


def test_type_name_resolves_to_id(resmap):
    assert resmap.type_id("Grass") == 12
    assert resmap.type_id("poison") == 3
    assert resmap.type_id("Sound") is None


def test_missing_file_fails_readably(tmp_path):
    with pytest.raises(AddressesError, match=ADDRESSES_FILE):
        load_addresses(tmp_path)


def test_missing_base_stats_fails_readably(tmp_path):
    data = json.loads((FIXTURE / ADDRESSES_FILE).read_text())
    del data["tables"]["base_stats"]
    (tmp_path / ADDRESSES_FILE).write_text(json.dumps(data))
    with pytest.raises(AddressesError, match="base_stats"):
        load_addresses(tmp_path)
