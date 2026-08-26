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
        (1, None),       # variable-power sentinel stays out
        (15, "≤50"),     # weak starter rungs count (Poison Sting)
        (50, "≤50"),     # upper bound inclusive
        (51, "51-75"),
        (75, "51-75"),   # upper bound inclusive
        (90, "76-90"),
        (109, "91-109"),
        (110, "110+"),
        (111, "110+"),
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
    filled, neutral = mc.filled_cells(pool)

    assert pool.moves["flamethrower"]["power"] == 90
    assert pool.learners["flamethrower"] >= mc.COMMON_THRESHOLD
    assert ("Fire", "special", "76-90") in filled
    assert ("Fire", "special", "76-90") in neutral  # Flamethrower is body-neutral


@pytest.mark.unit
def test_gen_gated_numbers_reach_the_pool() -> None:
    # The drain family's power and pp are gen-config ternaries in the base C
    # source. The parser resolves them, so the pool sees real numbers — this
    # test used to assert `pp is None`, encoding that parse gap as expected.
    pool = mc.build_pool()

    assert pool.moves["megadrain"]["pp"] == 15
    assert pool.moves["megadrain"]["power"] == 40
    assert mc.is_ladder_eligible(pool.moves["megadrain"])


@pytest.mark.unit
def test_unknown_pp_does_not_disqualify_a_rung() -> None:
    # Eligibility must not depend on pp being known: only a literal 1 (a
    # variable/no-BP sentinel) disqualifies. Kept as a guard now that no real
    # move reaches it.
    known = dict(mc.build_pool().moves["megadrain"])
    assert mc.is_ladder_eligible({**known, "pp": None})
    assert not mc.is_ladder_eligible({**known, "power": 1})


@pytest.mark.unit
def test_curated_exclusions_and_body_specific_tagging() -> None:
    pool = mc.build_pool()

    # Chris-ruled flavor/effect-specific moves never count as rungs.
    assert not mc.is_ladder_eligible(pool.moves["payback"])
    assert not mc.is_ladder_eligible(pool.moves["whirlpool"])
    # Body-plan words tag; ordinary moves don't.
    assert mc.is_body_specific(pool.moves["irontail"])
    assert not mc.is_body_specific(pool.moves["flamethrower"])


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


@pytest.mark.unit
def test_over110_requires_drawback_not_target_effect() -> None:
    # D21: a >110 rung carries its self-cost, not the type's target secondary.
    # Physical nuke with 1/3 recoil (effect: recoil) is compliant...
    phys_ok = {
        "type": "Dark", "category": "physical", "power": 120,
        "accuracy": 90, "pp": 5, "effect": "recoil", "additional_effects": [],
    }
    assert mc.audit_move("phys", phys_ok) == []

    # ...special nuke with the -2 SpA self-drop is compliant...
    spec_ok = {
        "type": "Bug", "category": "special", "power": 120,
        "accuracy": 90, "pp": 5, "effect": "hit",
        "additional_effects": [{"effect": "sp_atk_minus_2", "chance": 100}],
    }
    assert mc.audit_move("spec", spec_ok) == []

    # ...but a drawback-less >110 nuke is rejected (no free lunch).
    phys_bad = {**phys_ok, "effect": "hit"}
    assert any("drawback expected recoil" in d for d in mc.audit_move("bad", phys_bad))


@pytest.mark.unit
def test_over110_accepts_sinkhole_sink_pair_drawback() -> None:
    # Sinkhole's type-flavored >110 drawback: caster's Sp. Atk AND Speed each -1
    # (a behavior applies it; the data carries both markers). Must pass audit.
    sink = {
        "type": "Ground", "category": "special", "power": 130,
        "accuracy": 90, "pp": 5, "effect": "hit",
        "additional_effects": [
            {"effect": "sp_atk_minus_1", "chance": 100},
            {"effect": "spd_minus_1", "chance": 100},
        ],
    }
    assert mc.audit_move("sinkhole", sink) == []

    # Quagmire — Ground special 91-110, target -Speed at the 20% mid-band chance.
    quag = {
        "type": "Ground", "category": "special", "power": 100,
        "accuracy": 90, "pp": 10,
        "additional_effects": [{"effect": "spd_minus_1", "chance": 20}],
    }
    assert mc.audit_move("quagmire", quag) == []
