"""Resolution map for the polishedcrystal Applier: chrooked_id -> RGBDS symbol.

Symbols are derived by uppercasing (shadow-ball -> SHADOW_BALL) or taken from an
`aka: polishedcrystal:` hint, then verified against the target's constants files.
Unverifiable ids resolve to None so the caller reports `blocked` instead of
writing a symbol the assembler would reject.
"""

from pathlib import Path

import pytest

from chrooked_pokedex.appliers.polishedcrystal.resolution import build_resolution_map

FIXTURE = Path(__file__).parent / "fixtures" / "polishedcrystal"


@pytest.fixture()
def resmap():
    return build_resolution_map(FIXTURE)


@pytest.mark.unit
def test_move_resolves_by_uppercase(resmap):
    assert resmap.move("razor-leaf", {}) == "RAZOR_LEAF"


@pytest.mark.unit
def test_missing_move_resolves_to_none(resmap):
    assert resmap.move("not-a-real-move", {}) is None


@pytest.mark.unit
def test_aka_hint_wins_but_is_still_verified(resmap):
    assert resmap.move("ancient-power", {"polishedcrystal": "ANCIENTPOWER"}) == "ANCIENTPOWER"
    assert resmap.move("ancient-power", {"polishedcrystal": "NOT_IN_TARGET"}) is None


@pytest.mark.unit
def test_ability_resolves(resmap):
    assert resmap.ability("chlorophyll", {}) == "CHLOROPHYLL"
    assert resmap.ability("made-up-ability", {}) is None


@pytest.mark.unit
def test_species_label_guess_and_hint(resmap):
    # CamelCase guess for the evos_attacks label; aka hint for irregular names.
    assert resmap.species_label("bulbasaur", {}) == "Bulbasaur"
    assert (
        resmap.species_label("farfetchd-galarian", {"polishedcrystal": "FarfetchDGalarian"})
        == "FarfetchDGalarian"
    )
