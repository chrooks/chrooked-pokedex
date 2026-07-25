"""Unit smoke tests for the move-coverage harness (scripts/move_coverage.py)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# scripts/ is not a package; load the harness module by path.
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "move_coverage.py"
_spec = importlib.util.spec_from_file_location("move_coverage", _SCRIPT)
assert _spec and _spec.loader
mc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mc)


@pytest.mark.unit
@pytest.mark.parametrize(
    "power, expected",
    [
        (29, None),      # below the ladder floor
        (30, "30-50"),
        (50, "30-50"),   # upper bound inclusive
        (51, "51-75"),
        (75, "51-75"),   # upper bound inclusive
        (90, "76-90"),
        (110, "91-110"),
        (111, ">110"),
    ],
)
def test_band_bucketing_is_upper_inclusive(power, expected) -> None:
    assert mc.band_of(power) == expected


@pytest.mark.unit
def test_flamethrower_resolves_and_fills_fire_special_76_90() -> None:
    # Base snapshot stores Flamethrower power: null; the canon table fills 90.
    # power 90 -> band 76-90 (the plan text's "91-110" is a typo; that band is
    # filled by Fire Blast at 110).
    pool = mc.build_pool()

    assert pool.moves["flamethrower"]["power"] == 90
    assert pool.learners["flamethrower"] >= mc.COMMON_THRESHOLD
    assert ("Fire", "special", "76-90") in mc.filled_cells(pool)


@pytest.mark.unit
def test_check_passes_for_cindersmash() -> None:
    # Fire physical 90: burn @10%, acc 100, pp 15 -> obeys the effect map + 76-90 band.
    pool = mc.build_pool()
    assert mc.audit_move("cindersmash", pool.moves["cindersmash"]) == []


@pytest.mark.unit
def test_check_flags_wrong_type_effect() -> None:
    # Fire wants burn (D1); this synthetic move carries paralysis instead.
    synthetic = {
        "chrooked_id": "synthetic",
        "name": "Synthetic Blaze",
        "type": "Fire",
        "category": "special",
        "power": 80,       # band 76-90 -> acc 100, pp 15
        "accuracy": 100,
        "pp": 15,
        "additional_effects": [{"effect": "paralysis", "chance": 10}],
    }

    deviations = mc.audit_move("synthetic", synthetic)

    assert any("effect expected burn got paralysis" in d for d in deviations)


@pytest.mark.unit
def test_check_flags_wrong_band_accuracy_and_pp() -> None:
    # A clean-effect move whose acc/pp break the 76-90 convention (100/15).
    synthetic = {
        "type": "Fire",
        "category": "special",
        "power": 80,
        "accuracy": 90,    # should be 100
        "pp": 5,           # should be 15
        "additional_effects": [{"effect": "burn", "chance": 10}],
    }

    deviations = mc.audit_move("syn", synthetic)

    assert any("accuracy expected 100 got 90" in d for d in deviations)
    assert any("pp expected 15 got 5" in d for d in deviations)
