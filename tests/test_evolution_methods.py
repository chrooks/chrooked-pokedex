"""Unit tests for the canonical evolution-method table."""

import pytest

from chrooked_pokedex.model import evolution_methods as em

pytestmark = pytest.mark.unit


def test_every_method_round_trips_token_to_id_both_engines():
    for method in em.CANONICAL.values():
        assert em.id_for_token(method.pokeemerald) == method.id
        assert em.id_for_token(method.essentials) == method.id


def test_to_engine_translates_canonical_method():
    assert em.to_engine({"method": "knows_move", "param": "Mimic"}, "pokeemerald") == (
        "EVO_MOVE",
        "move",
        "Mimic",
    )
    assert em.to_engine({"method": "knows_move", "param": "Mimic"}, "essentials") == (
        "HasMove",
        "move",
        "Mimic",
    )


def test_to_engine_param_less_method_has_empty_param():
    assert em.to_engine({"method": "trade"}, "pokeemerald") == ("EVO_TRADE", "none", "")
    assert em.to_engine({"method": "friendship"}, "essentials") == (
        "Happiness",
        "none",
        "",
    )


def test_to_engine_returns_none_for_clean_and_raw_shapes():
    # The Applier's own branches own these; the canonical layer must stay out.
    assert em.to_engine({"level": 16}, "pokeemerald") is None
    assert em.to_engine({"item": "Water Stone"}, "essentials") is None
    assert em.to_engine({"pokeemerald": "EVO_MOVE", "param": "MOVE_MIMIC"}, "pokeemerald") is None
    assert em.to_engine({"method": "not_a_real_method"}, "pokeemerald") is None


def test_id_for_unknown_token_is_none():
    assert em.id_for_token("EVO_SOMETHING_MADE_UP") is None


def test_public_list_shape_and_order():
    rows = em.public_list()
    assert [r["id"] for r in rows][:2] == ["level", "level_day"]
    knows_move = next(r for r in rows if r["id"] == "knows_move")
    assert knows_move == {
        "id": "knows_move",
        "label": "Knows move",
        "value_kind": "move",
        "tokens": ["EVO_MOVE", "HasMove"],
    }
