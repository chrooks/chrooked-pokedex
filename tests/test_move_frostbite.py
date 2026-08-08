"""Cryofreeze, and the freeze-to-frostbite rename of the neutral effect name.

Freeze was replaced outright: the neutral vocabulary now says `frostbite`
everywhere, while each engine keeps its own unchanged symbol (Essentials
`FreezeTarget`, Rejuv funccode 0x00C). These tests pin both halves — the move
exists with the agreed numbers, and no neutral `freeze` survives anywhere.
"""

from pathlib import Path

import pytest

from chrooked_pokedex.appliers.essentials import vocab
from chrooked_pokedex.model import Ruleset

RULESET_DIR = Path(__file__).resolve().parents[1] / "ruleset"
SRC_DIR = Path(__file__).resolve().parents[1] / "src"


@pytest.mark.unit
def test_cryofreeze_exists_with_agreed_numbers() -> None:
    move = Ruleset.load(RULESET_DIR).moves["cryofreeze"]
    assert move.name == "Cryofreeze"
    assert move.type == "Ice"
    assert move.category == "status"
    assert move.power == 0
    assert move.accuracy == 85
    assert move.pp == 15

    effect = move.additional_effects[0]
    assert effect.effect == "frostbite"
    assert effect.chance == 100


@pytest.mark.unit
def test_no_move_still_uses_the_freeze_effect_name() -> None:
    for move in Ruleset.load(RULESET_DIR).moves.values():
        names = {e.effect for e in move.additional_effects} | {move.effect}
        assert "freeze" not in names, f"{move.chrooked_id} still uses 'freeze'"


@pytest.mark.unit
def test_engine_symbol_is_unchanged_by_the_reskin() -> None:
    """The rename is neutral-side only — Essentials keeps FreezeTarget."""
    assert vocab.additional_function_code("frostbite") == "FreezeTarget"
    assert vocab.additional_function_code("freeze") is None


@pytest.mark.unit
def test_no_neutral_freeze_key_survives_in_any_applier() -> None:
    offenders = [
        path
        for path in SRC_DIR.rglob("*.py")
        if '"freeze"' in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"neutral 'freeze' key still present in {offenders}"
