"""Each Applier translates a canonical `{method: id}` dict to its engine token."""

import pytest

from chrooked_pokedex.appliers.pokeemerald.evolution_apply import (
    _render_triple as pe_triple,
)
from chrooked_pokedex.appliers.essentials.evolution_apply import (
    _render_line as ess_line,
)
from chrooked_pokedex.appliers.essentials162.evolution_apply import (
    _render_triple as ess162_triple,
)

pytestmark = pytest.mark.unit


def test_pokeemerald_renders_canonical_methods():
    assert pe_triple({"method": "knows_move", "param": "Mimic"}, "SPECIES_MRMIME") == (
        "{EVO_MOVE, MOVE_MIMIC, SPECIES_MRMIME}"
    )
    assert pe_triple({"method": "trade"}, "SPECIES_X") == "{EVO_TRADE, 0, SPECIES_X}"
    assert pe_triple({"method": "friendship"}, "SPECIES_X") == (
        "{EVO_FRIENDSHIP, 0, SPECIES_X}"
    )
    assert pe_triple({"method": "level_day", "param": "30"}, "SPECIES_X") == (
        "{EVO_LEVEL_DAY, 30, SPECIES_X}"
    )
    assert pe_triple({"method": "trade_item", "param": "Metal Coat"}, "SPECIES_X") == (
        "{EVO_TRADE_ITEM, ITEM_METAL_COAT, SPECIES_X}"
    )


def test_essentials_v21_renders_canonical_methods():
    assert ess_line({"method": "knows_move", "param": "Mimic"}, "MRMIME") == (
        "MRMIME,HasMove,MIMIC"
    )
    assert ess_line({"method": "trade"}, "MRMIME") == "MRMIME,Trade"
    assert ess_line({"method": "trade_item", "param": "Metal Coat"}, "SCIZOR") == (
        "SCIZOR,TradeItem,METALCOAT"
    )


def test_essentials_162_renders_canonical_methods():
    assert ess162_triple({"method": "knows_move", "param": "Mimic"}, "MRMIME") == [
        "MRMIME",
        "HasMove",
        "MIMIC",
    ]
    # A param-less method emits an empty param to keep the flat triple aligned.
    assert ess162_triple({"method": "trade"}, "MRMIME") == ["MRMIME", "Trade", ""]


def test_clean_and_raw_shapes_still_render_unchanged():
    assert pe_triple({"level": 16}, "SPECIES_X") == "{EVO_LEVEL, 16, SPECIES_X}"
    assert ess_line({"item": "Water Stone"}, "VAPOREON") == "VAPOREON,Item,WATERSTONE"
    assert pe_triple({"pokeemerald": "EVO_MOVE", "param": "MOVE_MIMIC"}, "SPECIES_X") == (
        "{EVO_MOVE, MOVE_MIMIC, SPECIES_X}"
    )
