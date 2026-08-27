"""Issue #7 Phase A — learnset-suggest proposal endpoint + Port Seam.

Exercises the learnset capability end to end through the API, with the LLM Port
**mocked** — so the suite runs with no ``litellm`` install, no API key, and never
makes a network call. Mirrors ``test_web_suggest_typing_stats.py`` in structure.

Capability:
- ``POST /api/species/{id}/suggest/learnset`` →
  ``{draft:{learnset:[{level,move,reasoning}]}, rationale:{learnset}, alternatives}``

Modes:
- ``full`` (default): propose a whole learnset from scratch.
- ``surgical``: change only the targeted move; rest byte-identical.

ACs covered:
- ac1: full mode returns contract, writes nothing.
- ac2: surgical mode, untouched-rows guard, missing instruction → 422.
- ac3: hallucinated move → 422; edited/created move present in pool; canonical name.
- ac4: context assembly carries ability effect text + evo level.
- ac5: level 101 → 422; two non-zero levels → 422; L0+L20 accepted; sort normalized.
- ac6: missing key → 503; provider.propose called exactly once; no file write.
- ac7: PUT /api/species/{id} learnset round-trip; skill inspection.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.web import dex as dexmod
from chrooked_pokedex.web import llm as llmmod
from chrooked_pokedex.web import suggest as suggestmod
from chrooked_pokedex.web.app import create_app

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SAMPLE = _REPO_ROOT / "tests" / "fixtures" / "sample_ruleset"

# ---------------------------------------------------------------------------
# In-memory snapshot: two moves, one ability, one species with evo context.
# The snapshot mirrors the minimum data needed to exercise every code path.
# ---------------------------------------------------------------------------

_SNAPSHOT = {
    "version": "1.11.2",
    "species": {
        "goodra": {
            "dex": 706,
            "chrooked_id": "goodra",
            "name": "Goodra",
            "types": ["Dragon"],
            "abilities": {
                "primary": "Sap Sipper",
                "secondary": None,
                "hidden": "Gooey",
            },
            "stats": {
                "hp": 90, "atk": 100, "def": 70,
                "spa": 110, "spd": 150, "spe": 60,
            },
            # Current learnset — two moves for surgical-mode tests.
            "learnset": [
                {"level": 1, "move": "Tackle"},
                {"level": 5, "move": "Dragon Pulse"},
            ],
            # Goodra is evolved (from Sliggoo).
            "evolution": {"from": "sliggoo", "method": {"kind": "EVO_LEVEL", "param": 50}},
            "evolves_into": [],
            "fully_evolved": True,
        },
        "sliggoo": {
            "dex": 705,
            "chrooked_id": "sliggoo",
            "name": "Sliggoo",
            "types": ["Dragon"],
            "abilities": {"primary": "Sap Sipper", "secondary": None, "hidden": "Gooey"},
            "stats": {
                "hp": 68, "atk": 75, "def": 53,
                "spa": 83, "spd": 113, "spe": 40,
            },
            "learnset": [{"level": 1, "move": "Tackle"}],
            "evolution": {"from": "goomy", "method": {"kind": "EVO_LEVEL", "param": 40}},
            # Sliggoo evolves into Goodra at level 50 — used to test evo context.
            "evolves_into": [
                {
                    "to": "goodra",
                    "to_name": "Goodra",
                    "method": "EVO_LEVEL",
                    "method_detail": {"kind": "EVO_LEVEL", "param": 50},
                }
            ],
            "fully_evolved": False,
        },
    },
    "abilities": {
        "sap-sipper": {
            "chrooked_id": "sap-sipper",
            "name": "Sap Sipper",
            "description": "Boosts Attack when hit by a Grass-type move.",
            "aka": {},
        },
        "gooey": {
            "chrooked_id": "gooey",
            "name": "Gooey",
            "description": "Contact moves lower the attacker's Speed stat.",
            "aka": {},
        },
    },
    "moves": {
        "tackle": {
            "chrooked_id": "tackle",
            "name": "Tackle",
            "type": "Normal",
            "category": "Physical",
            "power": 40,
            "accuracy": 100,
            "pp": 35,
            "description": "A Normal-type tackle.",
            "effect": "hit",
            "argument": None,
            "additional_effects": [],
            "flags": [],
            "priority": 0,
            "target": "selected",
            "aka": {},
        },
        "dragon-pulse": {
            "chrooked_id": "dragon-pulse",
            "name": "Dragon Pulse",
            "type": "Dragon",
            "category": "Special",
            "power": 85,
            "accuracy": 100,
            "pp": 10,
            "description": "A special Dragon-type move.",
            "effect": "hit",
            "argument": None,
            "additional_effects": [],
            "flags": [],
            "priority": 0,
            "target": "selected",
            "aka": {},
        },
    },
    "type_chart": [
        {"attacker": "Dragon", "defender": "Dragon", "multiplier": 2.0},
        {"attacker": "Normal", "defender": "Dragon", "multiplier": 0.5},
    ],
}

# The canonical move pool derived from _SNAPSHOT moves (name-sorted).
_POOL_NAMES = ["Dragon Pulse", "Tackle"]


class _FakeProvider:
    """A mock LlmProvider Port that records calls and returns a canned draft."""

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def propose(
        self,
        *,
        system: str,
        cached_context: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = llmmod.DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "system": system,
                "cached_context": cached_context,
                "user": user,
                "schema": schema,
                "max_tokens": max_tokens,
            }
        )
        return self.result


# ---------------------------------------------------------------------------
# Canned results
# ---------------------------------------------------------------------------

_GOOD_LEARNSET_RESULT = {
    "draft": {
        "learnset": [
            {"level": 1, "move": "Tackle", "reasoning": "basic Normal STAB start"},
            {"level": 5, "move": "Dragon Pulse", "reasoning": "Dragon STAB online early"},
            {"level": 30, "move": "Excalibur", "reasoning": "signature payoff"},
        ]
    },
    "rationale": {"learnset": "Standard physical-then-special progression for Goodra."},
    "alternatives": [
        {"value": "Tackle @ L5 — later start frees slot", "rationale": "Opens L1 for Growl."},
    ],
}

# A pool-valid draft that trips the size floor (only 2 rows; the snapshot pool
# of 3 sets the floor to 3). Normalized and editable, so it comes back as an
# editable salvage rather than a hard failure.
_TOO_FEW_LEARNSET_RESULT = {
    "draft": {
        "learnset": [
            {"level": 1, "move": "Tackle", "reasoning": "basic Normal STAB start"},
            {"level": 5, "move": "Dragon Pulse", "reasoning": "Dragon STAB early"},
        ]
    },
    "rationale": {"learnset": "Deliberately short to trip the size floor."},
    "alternatives": [],
}

# Surgical: move Dragon Pulse from L5 → L0 (on-evo). Only the L5 row changes;
# L1 Tackle stays untouched. Dragon Pulse at L0 replaces Dragon Pulse at L5.
_SURGICAL_RESULT = {
    "draft": {
        "learnset": [
            {"level": 0, "move": "Dragon Pulse", "reasoning": "moved to on-evo per instruction"},
            {"level": 1, "move": "Tackle", "reasoning": "unchanged"},
        ]
    },
    "rationale": {"learnset": "Dragon Pulse moved to L0 as instructed."},
    "alternatives": [],
}


@pytest.fixture
def ruleset_dir(tmp_path: Path) -> Path:
    dst = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, dst)
    return dst


@pytest.fixture
def ruleset_dir_no_goodra(tmp_path: Path) -> Path:
    """A ruleset directory with the goodra species override removed.

    Surgical-mode tests need the entry's current learnset to come from the
    snapshot (not the sample fixture's override), so they can assert precisely
    which rows the canned surgical proposal changed.
    """
    dst = tmp_path / "ruleset_ng"
    shutil.copytree(_SAMPLE, dst)
    goodra_override = dst / "species" / "goodra.yaml"
    if goodra_override.exists():
        goodra_override.unlink()
    return dst


def _make_client(ruleset_dir: Path, tmp_path: Path, provider: Any) -> TestClient:
    snap_path = tmp_path / "snap.json"
    snap_path.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    app = create_app(
        ruleset_dir=ruleset_dir, snapshot_path=snap_path, llm_provider=provider
    )
    return TestClient(app, raise_server_exceptions=False)


def _skeleton_result(
    chrooked_id: str, ruleset_dir: Path, anchors: list[str] | None = None
) -> dict[str, Any]:
    """A draft that fills the slot skeleton the endpoint will build.

    FULL mode now runs the deterministic slot skeleton (learnset_skeleton) as a
    HARD gate, so a fixed mock draft no longer validates. This computes the same
    skeleton the server will and fills each slot with its first unused candidate.
    """
    from chrooked_pokedex.model import Ruleset
    from chrooked_pokedex.web import learnset_skeleton as skmod

    ruleset = Ruleset.load(ruleset_dir)
    pool = dexmod.build_move_pool(_SNAPSHOT, ruleset)
    abilities = dexmod.build_abilities(_SNAPSHOT, ruleset)
    entry = dexmod.build_dex_entry(_SNAPSHOT, ruleset, chrooked_id)
    return _fill_skeleton(entry, abilities, pool, anchors=anchors)


def _fill_skeleton(
    entry: dict[str, Any],
    abilities: list[dict[str, Any]],
    pool: list[dict[str, Any]],
    anchors: list[str] | None = None,
) -> dict[str, Any]:
    """Fill each skeleton slot with its first unused candidate.

    ``anchors`` must mirror what the request sends, or this builds a different
    skeleton than the server does and the hard gate rejects the draft.
    """
    from chrooked_pokedex.web import learnset_skeleton as skmod

    skeleton = skmod.build_skeleton(entry, abilities, pool, anchors=anchors)
    rows, used = [], set()
    for slot in skeleton["slots"]:
        pick = next(
            (c for c in slot["candidates"] if c.casefold() not in used),
            slot["candidates"][0],
        )
        if slot["level"] > 0:
            # L0 + one non-zero level of the same move is legal — only
            # non-zero picks consume a move.
            used.add(pick.casefold())
        rows.append({"level": slot["level"], "move": pick, "reasoning": "fills slot"})
    return {
        "draft": {"learnset": rows},
        "rationale": {"learnset": "Skeleton-conforming draft."},
        "alternatives": [],
    }


def _species_files(ruleset_dir: Path) -> set[str]:
    species_dir = ruleset_dir / "species"
    if not species_dir.exists():
        return set()
    return {p.name for p in species_dir.iterdir()}


def _build_ruleset(tmp_path: Path) -> Any:
    from chrooked_pokedex.model import Ruleset
    return Ruleset.load(_SAMPLE)


# ===========================================================================
# Unit tests — build_move_pool (M1)
# ===========================================================================


def test_build_move_pool_includes_all_moves() -> None:
    """build_move_pool returns one row per named move, name-sorted."""
    from chrooked_pokedex.model import Ruleset

    ruleset = Ruleset.load(_SAMPLE)
    pool = dexmod.build_move_pool(_SNAPSHOT, ruleset)
    names = [row["move"] for row in pool]

    assert "Tackle" in names
    assert "Dragon Pulse" in names
    # Sorted by name.
    assert names == sorted(names)


def test_build_move_pool_compact_row_shape() -> None:
    """Each row has exactly the fields the rubric needs."""
    from chrooked_pokedex.model import Ruleset

    ruleset = Ruleset.load(_SAMPLE)
    pool = dexmod.build_move_pool(_SNAPSHOT, ruleset)
    for row in pool:
        assert "move" in row
        assert "type" in row
        assert "category" in row
        assert "power" in row
        assert "effect" in row


def test_build_move_pool_edited_move_shows_current_values(tmp_path: Path) -> None:
    """An edited move's current type/power appears — not the base values."""
    import yaml
    from chrooked_pokedex.model import Ruleset

    # Create a Ruleset that re-types Tackle to Dragon with power 60.
    # Note: the loader expects lowercase categories (physical/special/status).
    ruleset_dir = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, ruleset_dir)
    moves_dir = ruleset_dir / "moves"
    moves_dir.mkdir(exist_ok=True)
    (moves_dir / "tackle.yaml").write_text(
        yaml.dump({
            "chrooked_id": "tackle",
            "name": "Tackle",
            "type": "Dragon",
            "category": "physical",
            "power": 60,
        }),
        encoding="utf-8",
    )
    ruleset = Ruleset.load(ruleset_dir)
    pool = dexmod.build_move_pool(_SNAPSHOT, ruleset)
    tackle_row = next(r for r in pool if r["move"] == "Tackle")
    assert tackle_row["type"] == "Dragon"
    assert tackle_row["power"] == 60
    # A rebalanced canon move is NOT custom — it exists in the base.
    assert tackle_row["custom"] is False


def test_build_move_pool_created_move_present(tmp_path: Path) -> None:
    """A created move (Ruleset-only, no base counterpart) appears in the pool."""
    import yaml
    from chrooked_pokedex.model import Ruleset

    # Note: the loader expects lowercase categories (physical/special/status).
    ruleset_dir = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, ruleset_dir)
    moves_dir = ruleset_dir / "moves"
    moves_dir.mkdir(exist_ok=True)
    (moves_dir / "slime-blast.yaml").write_text(
        yaml.dump({
            "chrooked_id": "slime-blast",
            "name": "Slime Blast",
            "type": "Dragon",
            "category": "special",
            "power": 90,
        }),
        encoding="utf-8",
    )
    ruleset = Ruleset.load(ruleset_dir)
    pool = dexmod.build_move_pool(_SNAPSHOT, ruleset)
    names = [r["move"] for r in pool]
    assert "Slime Blast" in names
    # Created moves are flagged custom; base moves are not.
    by_name = {r["move"]: r for r in pool}
    assert by_name["Slime Blast"]["custom"] is True
    assert by_name["Dragon Pulse"]["custom"] is False


def test_build_move_pool_reports_power_honestly() -> None:
    """The pool carries the base's own power, and a genuine null stays null.

    This used to backfill from a hand-kept canon table, because the move parser
    read only a bare literal and left every gen-gated power null. The parser now
    resolves those ternaries, so the base is the single source — inventing a
    number here would hide the next parse gap instead of surfacing it.
    """
    from chrooked_pokedex.model import Ruleset

    def _move(chrooked_id: str, name: str, power: int | None) -> dict:
        return {
            "chrooked_id": chrooked_id, "name": name, "type": "Water",
            "category": "special", "power": power, "accuracy": 100, "pp": 15,
            "description": "", "effect": "hit", "argument": None,
            "additional_effects": [], "flags": [], "priority": 0,
            "target": "all", "aka": {},
        }

    snap = {
        **_SNAPSHOT,
        "moves": {
            **_SNAPSHOT["moves"],
            "surf": _move("surf", "Surf", 90),
            "mystery": _move("mystery", "Mystery", None),
        },
    }
    ruleset = Ruleset.load(_SAMPLE)
    pool = dexmod.build_move_pool(snap, ruleset)

    assert next(r for r in pool if r["move"] == "Surf")["power"] == 90
    assert next(r for r in pool if r["move"] == "Mystery")["power"] is None


def test_format_move_pool_tags_custom_moves_only() -> None:
    """[CUSTOM] appears on flagged rows and nowhere else."""
    pool = [
        {"move": "Tackle", "type": "Normal", "category": "Physical",
         "power": 40, "effect": "hit", "custom": False},
        {"move": "Tsunami", "type": "Water", "category": "Special",
         "power": 95, "effect": "hit", "custom": True},
    ]
    text = suggestmod._format_move_pool(pool)
    tackle_line, tsunami_line = text.splitlines()
    assert "[CUSTOM]" not in tackle_line
    assert tsunami_line.endswith("[CUSTOM]")


def test_learnset_rubric_directs_custom_move_consideration() -> None:
    """The rubric tells the model to actively weigh [CUSTOM] moves."""
    rubric = suggestmod._build_learnset_rubric()
    assert "[CUSTOM]" in rubric


def test_learnset_rubric_states_pacing_bands_from_contract() -> None:
    """The rubric's pacing clause is rendered from the shared band Contract."""
    rubric = suggestmod._build_learnset_rubric()
    for band in suggestmod._pacing_bands():
        if band.get("bp_max") is not None:
            assert f"≤{band['bp_max']}BP" in rubric


def test_pacing_violation_warns_but_does_not_reject() -> None:
    """An attacking move over its level band's BP cap warns; the draft passes."""
    # Dragon Pulse is 85bp in _make_pool; L8 sits in the ≤60BP band.
    out = suggestmod._validate_learnset_result(
        _draft([(1, "Tackle"), (8, "Dragon Pulse")]),
        _make_pool(),
        mode="full",
        current_learnset=[],
    )
    assert len(out["draft"]["learnset"]) == 2
    assert any(w.startswith("pacing:") and "Dragon Pulse" in w
               for w in out["warnings"])


def _ate_pool() -> list[dict[str, Any]]:
    """A pool with strong Normal attackers, so the -ate shortlist has content."""
    return [
        {"move": "Body Slam", "type": "Normal", "category": "physical",
         "power": 85, "effect": "hit", "custom": False},
        {"move": "Double-Edge", "type": "Normal", "category": "physical",
         "power": 120, "effect": "hit", "custom": False},
        {"move": "Hyper Voice", "type": "Normal", "category": "special",
         "power": 90, "effect": "hit", "custom": False},
        {"move": "Growl", "type": "Normal", "category": "status",
         "power": None, "effect": "hit", "custom": False},
        {"move": "Dragon Pulse", "type": "Dragon", "category": "special",
         "power": 85, "effect": "hit", "custom": False},
    ]


def _abilities_with(desc_by_name: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {"name": name, "description": desc, "aka": {}}
        for name, desc in desc_by_name.items()
    ]


_MIXED = {"atk": 100, "spa": 100}  # tie → category-blind shortlist


def test_ate_ability_forces_normal_move_requirement_with_shortlist() -> None:
    """An -ate ability yields a hard requirement naming the converted type and a
    pool-queried Normal-attacker shortlist, strongest first."""
    req = suggestmod._ability_move_requirements(
        {"primary": "Spectralize", "secondary": None, "hidden": None},
        _abilities_with({"Spectralize": "Normal moves become Ghost-type. +20% power."}),
        _ate_pool(),
        _MIXED,
    )
    assert "MUST" in req
    assert "Ghost-type" in req
    # Shortlist present, attackers only, strongest first, status excluded.
    assert "Double-Edge (120bp)" in req
    assert req.index("Double-Edge") < req.index("Body Slam")
    assert "Growl" not in req


def test_ate_shortlist_respects_offensive_bias() -> None:
    """A special attacker's -ate fuel is SPECIAL Normal moves, not physical.

    This is the Typhlosion-Hisui bug: SpA > Atk but the shortlist handed over
    physical Double-Edge/Head Charge. The bias-aware shortlist must exclude them
    and surface the special Normal attacker (Hyper Voice) instead."""
    special_attacker = {"atk": 84, "spa": 122}
    req = suggestmod._ability_move_requirements(
        {"primary": "Spectralize", "secondary": None, "hidden": None},
        _abilities_with({"Spectralize": "Normal moves become Ghost-type. +20% power."}),
        _ate_pool(),
        special_attacker,
    )
    assert "SPECIAL" in req
    assert "Hyper Voice" in req  # special Normal attacker, kept
    assert "Double-Edge" not in req  # physical, excluded for a special attacker
    assert "Body Slam" not in req


def test_ate_shortlist_excludes_signature_moves() -> None:
    """Signature/species-locked moves (Judgment, Techno Blast) stay out of fuel."""
    pool = _ate_pool() + [
        {"move": "Judgment", "type": "Normal", "category": "special",
         "power": 100, "effect": "hit", "custom": False},
        {"move": "Techno Blast", "type": "Normal", "category": "special",
         "power": 120, "effect": "hit", "custom": False},
    ]
    req = suggestmod._ability_move_requirements(
        {"primary": "Spectralize", "secondary": None, "hidden": None},
        _abilities_with({"Spectralize": "Normal moves become Ghost-type. +20% power."}),
        pool,
        {"atk": 84, "spa": 122},
    )
    assert "Judgment" not in req
    assert "Techno Blast" not in req
    assert "Hyper Voice" in req  # a generic special Normal attacker still offered


def test_ate_shortlist_excludes_gimmick_nukes() -> None:
    """The attacker shortlist drops moves above the gimmick-nuke power ceiling."""
    pool = _ate_pool() + [
        {"move": "Explosion", "type": "Normal", "category": "physical",
         "power": 250, "effect": "hit", "custom": False},
    ]
    req = suggestmod._ability_move_requirements(
        {"primary": "Spectralize", "secondary": None, "hidden": None},
        _abilities_with({"Spectralize": "Normal moves become Ghost-type. +20% power."}),
        pool,
        _MIXED,
    )
    assert "Explosion" not in req
    assert "Double-Edge" in req  # 120bp, under the ceiling, kept


def test_status_synergy_ability_leans_toward_status_moves() -> None:
    """An ability rewarding status moves surfaces a status-move shortlist (soft)."""
    pool = _ate_pool()  # carries one status move, Growl
    req = suggestmod._ability_move_requirements(
        {"primary": "Insidious", "secondary": None, "hidden": None},
        _abilities_with({"Insidious": "Raises Speed one stage when using a status move."}),
        pool,
        _MIXED,
    )
    assert "status" in req.lower()
    assert "Growl" in req
    assert "MUST" not in req  # soft lean, not a hard requirement


def test_no_synergy_ability_yields_no_requirement_line() -> None:
    """An ability with no tabled synergy adds no requirement (rubric still drives)."""
    req = suggestmod._ability_move_requirements(
        {"primary": "Sap Sipper", "secondary": None, "hidden": None},
        _abilities_with({"Sap Sipper": "Boosts Attack when hit by a Grass move."}),
        _ate_pool(),
        _MIXED,
    )
    assert req == ""


def test_offensive_bias_line_in_context_for_special_attacker() -> None:
    """A special attacker gets a loud OFFENSIVE BIAS line steering moves special."""
    entry = {
        "chrooked_id": "typhlosionhisui",
        "name": "Typhlosion Hisui",
        "types": ["Fire", "Ghost"],
        "stats": {"hp": 73, "atk": 84, "def": 78, "spa": 122, "spd": 88, "spe": 95},
        "abilities": {"primary": "Blaze", "secondary": "Pyre", "hidden": None},
        "learnset": [{"level": 1, "move": "Tackle"}],
        "evolution": {},
        "evolves_into": [],
    }
    ctx = suggestmod._build_learnset_user_context(
        entry, [], _ate_pool(), "full", None, None
    )
    assert "OFFENSIVE BIAS" in ctx
    assert "SPECIAL" in ctx


def test_ate_requirement_appears_in_assembled_context() -> None:
    """The requirement lands on its own loud line in the suggest user context."""
    entry = {
        "chrooked_id": "vaporate",
        "name": "Vaporate",
        "types": ["Water"],
        "stats": {"hp": 80, "atk": 110, "def": 70, "spa": 60, "spd": 70, "spe": 90},
        "abilities": {"primary": "Hydrate", "secondary": None, "hidden": None},
        "learnset": [{"level": 1, "move": "Tackle"}],
        "evolution": {},
        "evolves_into": [],
    }
    user_ctx = suggestmod._build_learnset_user_context(
        entry,
        _abilities_with({"Hydrate": "Normal moves become Water-type. +20% power."}),
        _ate_pool(),
        "full",
        None,
        None,
    )
    assert "ABILITY-DRIVEN MOVE REQUIREMENT" in user_ctx
    assert "Water-type" in user_ctx


def test_full_mode_shows_current_learnset_as_names_only() -> None:
    """FULL mode must not hand the model the current level placement — that anchor
    is what makes it copy the old early-level packing. It sees names + a PRIOR ART
    framing; surgical mode still sees the exact L<level> rows (it edits in place)."""
    entry = {
        "chrooked_id": "golem",
        "name": "Golem",
        "types": ["Rock", "Electric"],
        "stats": {"hp": 80, "atk": 120, "def": 130, "spa": 55, "spd": 65, "spe": 45},
        "abilities": {"primary": "Sturdy", "secondary": None, "hidden": None},
        "learnset": [
            {"level": 1, "move": "Charge"},
            {"level": 1, "move": "Defense Curl"},
            {"level": 3, "move": "Tackle"},
        ],
        "evolution": {},
        "evolves_into": [],
    }
    full = suggestmod._build_learnset_user_context(entry, [], _make_pool(), "full", None, None)
    assert "PRIOR ART" in full
    assert "Charge, Defense Curl, Tackle" in full  # names, no levels
    assert "L1 Charge" not in full  # the anchor is gone

    surgical = suggestmod._build_learnset_user_context(
        entry, [], _make_pool(), "surgical", "swap Tackle for Rock Throw", None
    )
    assert "L1 Charge" in surgical  # in-place edits still need the exact rows


def test_pacing_exempts_l0_and_in_band_rows() -> None:
    """L0 rows and in-band attacks draw no pacing warning."""
    # Dragon Pulse 85bp at L0 (exempt) and Tackle 40bp at L8 (under the 60 cap).
    out = suggestmod._validate_learnset_result(
        _draft([(0, "Dragon Pulse"), (8, "Tackle")]),
        _make_pool(),
        mode="full",
        current_learnset=[],
    )
    assert not any(w.startswith("pacing:") for w in out.get("warnings", []))


# ===========================================================================
# Unit tests — _validate_learnset_result (M2 validator)
# ===========================================================================

def _make_pool() -> list[dict[str, Any]]:
    return [
        {"move": "Dragon Pulse", "type": "Dragon", "category": "Special", "power": 85, "effect": "hit"},
        {"move": "Tackle", "type": "Normal", "category": "Physical", "power": 40, "effect": "hit"},
    ]


def _make_current_learnset() -> list[dict[str, Any]]:
    return [
        {"level": 1, "move": "Tackle"},
        {"level": 5, "move": "Dragon Pulse"},
    ]


def test_validate_learnset_accepts_valid_result() -> None:
    result = {
        "draft": {
            "learnset": [
                {"level": 1, "move": "Tackle", "reasoning": "basic"},
                {"level": 5, "move": "Dragon Pulse", "reasoning": "STAB"},
            ]
        },
        "rationale": {"learnset": "Standard."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result, _make_pool(), mode="full", current_learnset=[]
    )
    assert "learnset" in out["draft"]
    assert len(out["draft"]["learnset"]) == 2


def test_validate_learnset_drops_hallucinated_move_with_warning() -> None:
    """Risk-tolerant contract: a hallucinated move is DROPPED with a warning while
    valid rows survive, not rejected wholesale."""
    result = {
        "draft": {
            "learnset": [
                {"level": 1, "move": "Tackle", "reasoning": "basic"},
                {"level": 5, "move": "FakeMove", "reasoning": "invented"},
                {"level": 20, "move": "Dragon Pulse", "reasoning": "STAB"},
            ]
        },
        "rationale": {"learnset": "Mostly OK."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result, _make_pool(), mode="full", current_learnset=[]
    )
    moves = [r["move"] for r in out["draft"]["learnset"]]
    assert moves == ["Tackle", "Dragon Pulse"]
    assert any("FakeMove" in w for w in out["warnings"])


def test_validate_learnset_all_rows_dropped_raises() -> None:
    """If every row is junk, nothing survives → retryable SuggestError."""
    result = {
        "draft": {"learnset": [{"level": 5, "move": "FakeMove", "reasoning": "x"}]},
        "rationale": {"learnset": "Bad."},
        "alternatives": [],
    }
    with pytest.raises(suggestmod.SuggestError, match="No usable learnset rows"):
        suggestmod._validate_learnset_result(
            result, _make_pool(), mode="full", current_learnset=[]
        )


def test_validate_learnset_drops_out_of_range_level_with_warning() -> None:
    """A level outside [0, 100] drops that row with a warning; valid rows stay."""
    result = {
        "draft": {
            "learnset": [
                {"level": 1, "move": "Tackle", "reasoning": "ok"},
                {"level": 101, "move": "Dragon Pulse", "reasoning": "too high"},
                {"level": -1, "move": "Dragon Pulse", "reasoning": "negative"},
                {"level": 20, "move": "Dragon Pulse", "reasoning": "valid"},
            ]
        },
        "rationale": {"learnset": "Mixed."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result, _make_pool(), mode="full", current_learnset=[]
    )
    moves = [r["move"] for r in out["draft"]["learnset"]]
    assert moves == ["Tackle", "Dragon Pulse"]
    assert sum("outside" in w for w in out["warnings"]) == 2


def test_validate_learnset_accepts_level_zero() -> None:
    """Level 0 (on-evolution) is valid."""
    result = {
        "draft": {
            "learnset": [
                {"level": 0, "move": "Dragon Pulse", "reasoning": "on-evo reward"},
                {"level": 1, "move": "Tackle", "reasoning": "basic"},
            ]
        },
        "rationale": {"learnset": "OK."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result, _make_pool(), mode="full", current_learnset=[]
    )
    levels = [r["level"] for r in out["draft"]["learnset"]]
    assert 0 in levels


def test_validate_learnset_accepts_l0_plus_nonzero_same_move() -> None:
    """A move may appear at L0 AND once at a non-zero level (B carve-out)."""
    result = {
        "draft": {
            "learnset": [
                {"level": 0, "move": "Dragon Pulse", "reasoning": "on-evo"},
                {"level": 20, "move": "Dragon Pulse", "reasoning": "relearn"},
            ]
        },
        "rationale": {"learnset": "OK."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result, _make_pool(), mode="full", current_learnset=[]
    )
    moves = [r["move"] for r in out["draft"]["learnset"]]
    assert moves.count("Dragon Pulse") == 2


def test_validate_learnset_repairs_two_nonzero_levels_keeping_lowest() -> None:
    """Risk-tolerant contract: a move at two non-zero levels is REPAIRED by keeping
    the lowest and dropping the rest with a warning (Chris's Bonemerang case)."""
    result = {
        "draft": {
            "learnset": [
                {"level": 20, "move": "Tackle", "reasoning": "second"},
                {"level": 5, "move": "Tackle", "reasoning": "first"},
                {"level": 25, "move": "Dragon Pulse", "reasoning": "STAB"},
            ]
        },
        "rationale": {"learnset": "Fixable."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result, _make_pool(), mode="full", current_learnset=[]
    )
    rows = out["draft"]["learnset"]
    assert [(r["level"], r["move"]) for r in rows] == [
        (5, "Tackle"),
        (25, "Dragon Pulse"),
    ]
    assert any("Tackle" in w and "@20" in w for w in out["warnings"])


def test_validate_learnset_repairs_more_than_two_rows_per_move() -> None:
    """L0 + two non-zero → keep L0 + the lowest non-zero, drop the extra, warn."""
    result = {
        "draft": {
            "learnset": [
                {"level": 0, "move": "Dragon Pulse", "reasoning": "on-evo"},
                {"level": 5, "move": "Dragon Pulse", "reasoning": "first non-zero"},
                {"level": 20, "move": "Dragon Pulse", "reasoning": "second non-zero"},
            ]
        },
        "rationale": {"learnset": "Fixable."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result, _make_pool(), mode="full", current_learnset=[]
    )
    kept = sorted((r["level"], r["move"]) for r in out["draft"]["learnset"])
    assert kept == [(0, "Dragon Pulse"), (5, "Dragon Pulse")]
    assert any("@20" in w for w in out["warnings"])


def test_validate_learnset_deduplicates_exact_pairs() -> None:
    """Exact (level, move) duplicates are silently deduplicated."""
    result = {
        "draft": {
            "learnset": [
                {"level": 1, "move": "Tackle", "reasoning": "a"},
                {"level": 1, "move": "Tackle", "reasoning": "a"},  # exact dup
                {"level": 20, "move": "Dragon Pulse", "reasoning": "b"},
            ]
        },
        "rationale": {"learnset": "OK."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result, _make_pool(), mode="full", current_learnset=[]
    )
    assert len(out["draft"]["learnset"]) == 2


def test_validate_learnset_sorts_by_level_then_name() -> None:
    """Unsorted input comes back sorted by (level, move name)."""
    result = {
        "draft": {
            "learnset": [
                {"level": 5, "move": "Dragon Pulse", "reasoning": "b"},
                {"level": 1, "move": "Tackle", "reasoning": "a"},
            ]
        },
        "rationale": {"learnset": "OK."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result, _make_pool(), mode="full", current_learnset=[]
    )
    rows = out["draft"]["learnset"]
    assert (rows[0]["level"], rows[0]["move"]) == (1, "Tackle")
    assert (rows[1]["level"], rows[1]["move"]) == (5, "Dragon Pulse")


def test_validate_learnset_normalizes_case_to_canonical() -> None:
    """Case-variant move name normalizes to the pool's canonical display name."""
    result = {
        "draft": {
            "learnset": [
                {"level": 1, "move": "TACKLE", "reasoning": "all caps"},
                {"level": 20, "move": "Dragon Pulse", "reasoning": "STAB"},
            ]
        },
        "rationale": {"learnset": "OK."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result, _make_pool(), mode="full", current_learnset=[]
    )
    assert out["draft"]["learnset"][0]["move"] == "Tackle"


# ===========================================================================
# Unit tests — shape bounds (size range, level ceiling, early-level caps)
# ===========================================================================


def _wide_pool(n: int) -> list[dict[str, Any]]:
    """A pool of n distinct moves, so drafts can reach the real size floor."""
    return [
        {"move": f"Move {i:02d}", "type": "Normal", "category": "Physical",
         "power": 40, "effect": "hit"}
        for i in range(n)
    ]


def _draft(rows: list[tuple[int, str]]) -> dict[str, Any]:
    return {
        "draft": {
            "learnset": [
                {"level": lvl, "move": mv, "reasoning": "x"} for lvl, mv in rows
            ]
        },
        "rationale": {"learnset": "Shape test."},
        "alternatives": [],
    }


def test_full_mode_rejects_too_few_rows_for_large_pool() -> None:
    """With a pool past the floor, a draft under LEARNSET_SIZE_MIN raises."""
    pool = _wide_pool(30)
    rows = [(10 + 5 * i, f"Move {i:02d}") for i in range(5)]
    with pytest.raises(suggestmod.SuggestError, match="rows after validation"):
        suggestmod._validate_learnset_result(
            _draft(rows), pool, mode="full", current_learnset=[]
        )


def test_full_mode_rejects_too_many_rows() -> None:
    """A draft over LEARNSET_SIZE_MAX raises."""
    count = suggestmod.LEARNSET_SIZE_MAX + 1
    pool = _wide_pool(count)
    rows = [(11 + 2 * i, f"Move {i:02d}") for i in range(count)]
    with pytest.raises(suggestmod.SuggestError, match="rows after validation"):
        suggestmod._validate_learnset_result(
            _draft(rows), pool, mode="full", current_learnset=[]
        )


def test_full_mode_size_floor_scales_to_small_pool() -> None:
    """A pool smaller than LEARNSET_SIZE_MIN lowers the floor to the pool size."""
    out = suggestmod._validate_learnset_result(
        _draft([(1, "Tackle"), (20, "Dragon Pulse")]),
        _make_pool(),
        mode="full",
        current_learnset=[],
    )
    assert len(out["draft"]["learnset"]) == 2


def test_full_mode_drops_rows_above_level_ceiling() -> None:
    """A row above LEARNSET_MAX_LEVEL is dropped with a warning in full mode."""
    ceiling = suggestmod.LEARNSET_MAX_LEVEL
    out = suggestmod._validate_learnset_result(
        _draft([(1, "Tackle"), (20, "Dragon Pulse"), (ceiling + 1, "Dragon Pulse")]),
        _make_pool(),
        mode="full",
        current_learnset=[],
    )
    levels = [r["level"] for r in out["draft"]["learnset"]]
    assert levels == [1, 20]
    assert any(str(ceiling + 1) in w for w in out["warnings"])


def test_full_mode_rejects_early_level_packing() -> None:
    """More rows at L5-or-below than the cap raises with a spread-out nudge."""
    pool = _wide_pool(30)
    over_cap = suggestmod.LEARNSET_MAX_MOVES_THROUGH_L5 + 1
    early = [(1, f"Move {i:02d}") for i in range(over_cap)]
    late = [
        (20 + 3 * i, f"Move {i + over_cap:02d}")
        for i in range(suggestmod.LEARNSET_SIZE_MIN - over_cap + 2)
    ]
    with pytest.raises(suggestmod.SuggestError, match="level 5 or below"):
        suggestmod._validate_learnset_result(
            _draft(early + late), pool, mode="full", current_learnset=[]
        )


def test_early_level_packing_flags_with_editable_salvage() -> None:
    """The reported symptom: an early-packed draft is flagged but the normalized,
    editable learnset rides along as salvage so the UI can show it for editing."""
    pool = _wide_pool(30)
    over_cap = suggestmod.LEARNSET_MAX_MOVES_THROUGH_L5 + 1
    early = [(1, f"Move {i:02d}") for i in range(over_cap)]
    late = [
        (20 + 3 * i, f"Move {i + over_cap:02d}")
        for i in range(suggestmod.LEARNSET_SIZE_MIN - over_cap + 2)
    ]
    try:
        suggestmod._validate_learnset_result(
            _draft(early + late), pool, mode="full", current_learnset=[]
        )
        raise AssertionError("expected a SuggestError")
    except suggestmod.SuggestError as error:
        assert error.salvage is not None
        assert "level 5 or below" in error.salvage["error"]
        # Every proposed row survives in the salvage (pool-checked + sorted),
        # so nothing is lost — the author edits the flagged draft in place.
        assert len(error.salvage["draft"]["learnset"]) == len(early + late)


def test_surgical_mode_tolerates_rows_above_level_ceiling() -> None:
    """Surgical mode keeps untouched rows above the ceiling (base learnsets do)."""
    current = [
        {"level": 1, "move": "Tackle"},
        {"level": 80, "move": "Dragon Pulse"},
    ]
    out = suggestmod._validate_learnset_result(
        _draft([(5, "Tackle"), (80, "Dragon Pulse")]),
        _make_pool(),
        mode="surgical",
        current_learnset=current,
        instruction="move Tackle to level 5",
    )
    levels = [r["level"] for r in out["draft"]["learnset"]]
    assert 80 in levels


# ===========================================================================
# Unit tests — surgical untouched-rows guard
# ===========================================================================


def test_surgical_accepts_single_swap() -> None:
    """Surgical mode: exactly one row changed is accepted.

    Current learnset: [(1, Tackle), (5, Dragon Pulse)].
    Proposed: [(0, Dragon Pulse), (1, Tackle)] — Dragon Pulse moved from L5 to L0.
    The guard allows 1 add + 1 remove (one surgical swap). Tackle@L1 is untouched.
    Dragon Pulse at L0 doesn't conflict with the B rule (no non-zero level for it).
    """
    result = {
        "draft": {
            "learnset": [
                {"level": 0, "move": "Dragon Pulse", "reasoning": "on-evo reward"},
                {"level": 1, "move": "Tackle", "reasoning": "unchanged"},
            ]
        },
        "rationale": {"learnset": "Dragon Pulse moved to L0."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result,
        _make_pool(),
        mode="surgical",
        current_learnset=_make_current_learnset(),
        instruction="move Dragon Pulse to L0 as on-evo reward",
    )
    assert len(out["draft"]["learnset"]) == 2


def test_surgical_accepts_no_changes() -> None:
    """Surgical mode: proposing the identical learnset is allowed (zero changes)."""
    result = {
        "draft": {
            "learnset": [
                {"level": 1, "move": "Tackle", "reasoning": "unchanged"},
                {"level": 5, "move": "Dragon Pulse", "reasoning": "unchanged"},
            ]
        },
        "rationale": {"learnset": "Nothing changed."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result,
        _make_pool(),
        mode="surgical",
        current_learnset=_make_current_learnset(),
        instruction="no changes needed",
    )
    assert len(out["draft"]["learnset"]) == 2


def test_surgical_rejects_multiple_perturbed_rows() -> None:
    """Surgical mode: changing 2+ rows → SuggestError.

    The untouched-rows guard allows at most one row added and one row removed
    (a single surgical swap). Changing more than one pair is rejected as the
    model perturbed rows beyond the instruction's scope.
    """
    result = {
        "draft": {
            "learnset": [
                # Both rows changed: L1→L10 Tackle AND L5→L0 Dragon Pulse
                # That is 2 added + 2 removed → guard fires.
                {"level": 10, "move": "Tackle", "reasoning": "oops"},
                {"level": 0, "move": "Dragon Pulse", "reasoning": "oops2"},
            ]
        },
        "rationale": {"learnset": "Bad."},
        "alternatives": [],
    }
    with pytest.raises(suggestmod.SuggestError, match="Surgical mode"):
        suggestmod._validate_learnset_result(
            result,
            _make_pool(),
            mode="surgical",
            current_learnset=_make_current_learnset(),
            instruction="change Dragon Pulse at L5 to something",
        )


def test_surgical_missing_instruction_raises_before_port_call() -> None:
    """Surgical mode with no instruction → SuggestError, no Port call."""
    pool = _make_pool()
    entry = {
        "chrooked_id": "goodra",
        "name": "Goodra",
        "types": ["Dragon"],
        "stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 60},
        "abilities": {},
        "learnset": _make_current_learnset(),
        "evolution": None,
        "evolves_into": [],
    }
    provider = _FakeProvider(_GOOD_LEARNSET_RESULT)
    with pytest.raises(suggestmod.SuggestError, match="instruction"):
        suggestmod.suggest_learnset(
            provider=provider,
            entry=entry,
            move_pool=pool,
            abilities=[],
            mode="surgical",
            instruction=None,
        )
    assert provider.calls == [], "Port must not be called before SuggestError"


def test_surgical_empty_learnset_raises() -> None:
    """Surgical mode on a species with no current learnset → SuggestError."""
    pool = _make_pool()
    entry = {
        "chrooked_id": "goodra",
        "name": "Goodra",
        "types": ["Dragon"],
        "stats": {},
        "abilities": {},
        "learnset": [],  # no current learnset
        "evolution": None,
        "evolves_into": [],
    }
    provider = _FakeProvider(_GOOD_LEARNSET_RESULT)
    with pytest.raises(suggestmod.SuggestError, match="no prior learnset|none|existing"):
        suggestmod.suggest_learnset(
            provider=provider,
            entry=entry,
            move_pool=pool,
            abilities=[],
            mode="surgical",
            instruction="swap Tackle for Dragon Pulse at L1",
        )


# ===========================================================================
# Unit tests — context assembly (ac4)
# ===========================================================================


def test_context_assembly_includes_ability_effect_text() -> None:
    """The assembled user context carries ability effect descriptions (not names-only)."""
    from chrooked_pokedex.model import Ruleset

    ruleset = Ruleset.load(_SAMPLE)
    abilities = dexmod.build_abilities(_SNAPSHOT, ruleset)

    pool = _make_pool()
    entry = {
        "chrooked_id": "goodra",
        "name": "Goodra",
        "types": ["Dragon"],
        "stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 60},
        "abilities": {"primary": "Sap Sipper", "secondary": None, "hidden": "Gooey"},
        "learnset": _make_current_learnset(),
        "evolution": {"from": "sliggoo", "method": {}},
        "evolves_into": [],
    }

    provider = _FakeProvider(_fill_skeleton(entry, abilities, pool))
    suggestmod.suggest_learnset(
        provider=provider,
        entry=entry,
        move_pool=pool,
        abilities=abilities,
        mode="full",
    )

    assert len(provider.calls) == 1
    user_ctx = provider.calls[0]["user"]
    # The ability description text should appear, not just the name.
    assert "Boosts Attack" in user_ctx or "Grass" in user_ctx


def test_context_assembly_includes_evo_level_for_pre_evo() -> None:
    """Evo level from evolves_into[].method_detail.param appears in context."""
    pool = _make_pool()
    entry = {
        "chrooked_id": "sliggoo",
        "name": "Sliggoo",
        "types": ["Dragon"],
        "stats": {"hp": 68, "atk": 75, "def": 53, "spa": 83, "spd": 113, "spe": 40},
        "abilities": {"primary": "Sap Sipper", "secondary": None, "hidden": "Gooey"},
        "learnset": [{"level": 1, "move": "Tackle"}],
        "evolution": {"from": "goomy", "method": {}},
        "evolves_into": [
            {
                "to": "goodra",
                "to_name": "Goodra",
                "method": "EVO_LEVEL",
                "method_detail": {"kind": "EVO_LEVEL", "param": 50},
            }
        ],
    }

    provider = _FakeProvider(_fill_skeleton(entry, [], pool))
    suggestmod.suggest_learnset(
        provider=provider,
        entry=entry,
        move_pool=pool,
        abilities=[],
        mode="full",
    )

    user_ctx = provider.calls[0]["user"]
    assert "50" in user_ctx  # evo level present


# ===========================================================================
# ac1 — full mode: contract + writes nothing
# ===========================================================================


def test_suggest_learnset_full_returns_contract(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    provider = _FakeProvider(_GOOD_LEARNSET_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post(
        "/api/species/goodra/suggest/learnset",
        json={"mode": "full"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "draft" in body
    assert "learnset" in body["draft"]
    rows = body["draft"]["learnset"]
    assert isinstance(rows, list)
    assert len(rows) > 0
    for row in rows:
        assert "level" in row
        assert "move" in row
        assert "reasoning" in row
    assert "rationale" in body
    assert "learnset" in body["rationale"]
    assert "alternatives" in body


def test_suggest_learnset_full_writes_nothing(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    before = _species_files(ruleset_dir)
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_GOOD_LEARNSET_RESULT))

    client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert _species_files(ruleset_dir) == before


# --------------------------------------------------------------------------- #
# Self-repair layer — a missing/empty draft list (the truncation-adjacent
# failure) retries ONCE; a persistent miss errors honestly naming what came back.
# --------------------------------------------------------------------------- #

# An empty draft — what a truncation-adjacent response parses to (arguments "{}").
_MISSING_LEARNSET_RESULT: dict[str, Any] = {}


def test_learnset_missing_list_repairs_in_one_retry(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    provider = _SequenceProvider(
        [_MISSING_LEARNSET_RESULT, _skeleton_result("goodra", ruleset_dir)]
    )
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert response.status_code == 200
    assert len(response.json()["draft"]["learnset"]) > 0
    assert len(provider.calls) == 2  # exactly one retry


def test_learnset_missing_twice_errors_honestly_naming_what_came_back(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    # Learnset retries eagerly (3 extra attempts); a persistently missing list
    # exhausts all four calls, then errors honestly.
    provider = _SequenceProvider([_MISSING_LEARNSET_RESULT] * 4)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    # Not a bare dead end: names the original miss AND what the retries returned.
    assert "learnset list" in detail
    assert "after 3 automatic retries" in detail
    assert len(provider.calls) == 4  # first try + 3 eager repairs, then gave up


def test_suggest_learnset_flagged_draft_returns_200_with_editable_salvage(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """A draft the model never completes comes back as a 200 anyway: after the
    eager retries exhaust, the server's skeleton auto-repair finishes the
    draft deterministically (each unfilled slot seated with an unused
    candidate) — the UI gets a full proposal, not a salvage banner."""
    provider = _SequenceProvider([_TOO_FEW_LEARNSET_RESULT] * 4)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert response.status_code == 200
    body = response.json()
    assert "error" not in body  # repaired, not flagged
    assert any("auto-repair" in w for w in body["warnings"])
    assert len(body["draft"]["learnset"]) > 2  # the two model rows got completed
    assert len(provider.calls) == 4  # first try + 3 eager repairs, then repaired


def test_suggest_learnset_flagged_draft_writes_nothing(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """A flagged salvage is still a proposal — it writes nothing to the Ruleset."""
    before = _species_files(ruleset_dir)
    provider = _SequenceProvider([_TOO_FEW_LEARNSET_RESULT] * 4)
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert _species_files(ruleset_dir) == before


def test_learnset_token_limit_raised_for_full_draft() -> None:
    # The real cure for the intermittent truncation: a comfortable output budget
    # for a ~20-25 row learnset with per-row reasoning.
    assert suggestmod.LEARNSET_MAX_TOKENS >= 8192


def test_suggest_learnset_full_no_body_accepted(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """Sending no JSON body at all defaults to full mode."""
    provider = _FakeProvider(_GOOD_LEARNSET_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/goodra/suggest/learnset")

    assert response.status_code == 200


def test_suggest_learnset_unknown_species_is_404(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    provider = _FakeProvider(_GOOD_LEARNSET_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/nosuchmon/suggest/learnset")

    assert response.status_code == 404
    assert provider.calls == []


# ===========================================================================
# ac2 — surgical mode: happy path + untouched-rows guard + missing instruction
# ===========================================================================


def test_suggest_learnset_surgical_happy_path(
    ruleset_dir_no_goodra: Path, tmp_path: Path
) -> None:
    """Surgical mode: single swap accepted, rest byte-identical.

    Uses a ruleset without the goodra species override so the current learnset
    comes from the snapshot: [(1,Tackle),(5,Dragon Pulse)]. _SURGICAL_RESULT
    proposes [(0,Dragon Pulse),(1,Tackle)] — moving Dragon Pulse from L5 to L0.
    That's exactly 1 add + 1 remove, within the surgical guard.
    """
    provider = _FakeProvider(_SURGICAL_RESULT)
    client = _make_client(ruleset_dir_no_goodra, tmp_path, provider)

    response = client.post(
        "/api/species/goodra/suggest/learnset",
        json={
            "mode": "surgical",
            "instruction": "move Dragon Pulse to L0 (on-evo reward)",
        },
    )

    assert response.status_code == 200
    body = response.json()
    rows = body["draft"]["learnset"]
    assert len(rows) == 2


def test_suggest_learnset_surgical_perturbed_rows_is_422(
    ruleset_dir_no_goodra: Path, tmp_path: Path
) -> None:
    """Surgical mode: model changes 2+ rows (beyond a single swap) → 422.

    Current learnset (from snapshot): [(1, Tackle), (5, Dragon Pulse)].
    Bad proposal: [(10, Tackle), (0, Dragon Pulse), (20, Dragon Pulse)].
    That's multiple changes: L1→L10 Tackle AND L5→L0+L20 Dragon Pulse.
    The guard fires because 2+ rows were added or removed.
    """
    bad_surgical = {
        "draft": {
            "learnset": [
                # Both original rows are gone; replaced with completely different set
                {"level": 10, "move": "Tackle", "reasoning": "oops moved L1→L10"},
                {"level": 20, "move": "Dragon Pulse", "reasoning": "oops moved L5→L20"},
            ]
        },
        "rationale": {"learnset": "Bad."},
        "alternatives": [],
    }
    client = _make_client(ruleset_dir_no_goodra, tmp_path, _FakeProvider(bad_surgical))

    response = client.post(
        "/api/species/goodra/suggest/learnset",
        json={
            "mode": "surgical",
            "instruction": "move Dragon Pulse to a different level",
        },
    )

    assert response.status_code == 422
    assert "urgical" in response.json()["detail"]


def test_suggest_learnset_surgical_missing_instruction_is_422(
    ruleset_dir_no_goodra: Path, tmp_path: Path
) -> None:
    """Surgical mode with no instruction → 422 before any Port call."""
    provider = _FakeProvider(_GOOD_LEARNSET_RESULT)
    client = _make_client(ruleset_dir_no_goodra, tmp_path, provider)

    response = client.post(
        "/api/species/goodra/suggest/learnset",
        json={"mode": "surgical"},  # no instruction
    )

    assert response.status_code == 422
    assert "instruction" in response.json()["detail"].lower()
    assert provider.calls == []


def test_suggest_learnset_surgical_writes_nothing(
    ruleset_dir_no_goodra: Path, tmp_path: Path
) -> None:
    before = _species_files(ruleset_dir_no_goodra)
    client = _make_client(
        ruleset_dir_no_goodra,
        tmp_path,
        _FakeProvider(_SURGICAL_RESULT),
    )

    client.post(
        "/api/species/goodra/suggest/learnset",
        json={
            "mode": "surgical",
            "instruction": "move Dragon Pulse to L0 (on-evo reward)",
        },
    )

    assert _species_files(ruleset_dir_no_goodra) == before


# ===========================================================================
# ac3 — hallucinated move → 422; edited/created move present; canonical name
# ===========================================================================


def test_suggest_learnset_all_hallucinated_is_422(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """A draft whose ONLY row is a hallucinated move drops to empty and, after the
    eager retries, is an honest 422 — nothing written."""
    bad = {
        "draft": {
            "learnset": [
                {"level": 1, "move": "FakeMoveXYZ", "reasoning": "invented"},
            ]
        },
        "rationale": {"learnset": "Bad."},
        "alternatives": [],
    }
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(bad))
    before = _species_files(ruleset_dir)

    response = client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert response.status_code == 422
    assert "no usable learnset rows" in response.json()["detail"].lower()
    assert _species_files(ruleset_dir) == before


def test_suggest_learnset_hallucinated_move_dropped_among_valid(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """A hallucinated move alongside valid rows is dropped with a warning; the
    proposal still returns 200 with the valid rows (risk-tolerant contract)."""
    mixed = {
        "draft": {
            "learnset": [
                {"level": 1, "move": "Tackle", "reasoning": "basic"},
                {"level": 5, "move": "FakeMoveXYZ", "reasoning": "invented"},
                {"level": 20, "move": "Dragon Pulse", "reasoning": "STAB"},
                {"level": 30, "move": "Excalibur", "reasoning": "signature"},
            ]
        },
        "rationale": {"learnset": "Mostly OK."},
        "alternatives": [],
    }
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(mixed))

    response = client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert response.status_code == 200
    body = response.json()
    moves = [r["move"] for r in body["draft"]["learnset"]]
    assert "FakeMoveXYZ" not in moves
    assert any("FakeMoveXYZ" in w for w in body["warnings"])


def test_suggest_learnset_edited_move_in_pool(tmp_path: Path) -> None:
    """An edited move (different type/power) appears in the pool with current values."""
    import yaml
    from chrooked_pokedex.model import Ruleset

    # Note: the loader expects lowercase categories (physical/special/status).
    ruleset_dir = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, ruleset_dir)
    moves_dir = ruleset_dir / "moves"
    moves_dir.mkdir(exist_ok=True)
    (moves_dir / "tackle.yaml").write_text(
        yaml.dump({
            "chrooked_id": "tackle",
            "name": "Tackle",
            "type": "Dragon",
            "category": "special",
            "power": 80,
        }),
        encoding="utf-8",
    )
    ruleset = Ruleset.load(ruleset_dir)
    pool = dexmod.build_move_pool(_SNAPSHOT, ruleset)
    tackle_row = next(r for r in pool if r["move"] == "Tackle")
    assert tackle_row["type"] == "Dragon"
    assert tackle_row["power"] == 80


# ===========================================================================
# ac5 — level validator + repeat-move B rule + sort normalization
# ===========================================================================


def test_suggest_learnset_out_of_range_level_dropped_among_valid(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """An out-of-range level is dropped with a warning; valid rows return 200."""
    mixed = {
        "draft": {
            "learnset": [
                {"level": 1, "move": "Tackle", "reasoning": "ok"},
                {"level": 101, "move": "Dragon Pulse", "reasoning": "too high"},
                {"level": 20, "move": "Dragon Pulse", "reasoning": "valid"},
                {"level": 30, "move": "Excalibur", "reasoning": "signature"},
            ]
        },
        "rationale": {"learnset": "Mixed."},
        "alternatives": [],
    }
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(mixed))

    response = client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert response.status_code == 200
    body = response.json()
    # The out-of-range row is gone (with a warning); the server's skeleton
    # auto-repair then completes the draft, so more rows may ride along.
    assert not any(r["level"] == 101 for r in body["draft"]["learnset"])
    assert any("101" in w for w in body["warnings"])
    assert "error" not in body


def test_suggest_learnset_two_nonzero_levels_repaired_to_200(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """A move at two non-zero levels is repaired (keep lowest) and returns 200 with
    a warning, not a 422 — Chris's risk-tolerant ruling."""
    dupe = {
        "draft": {
            "learnset": [
                {"level": 5, "move": "Tackle", "reasoning": "first"},
                {"level": 20, "move": "Tackle", "reasoning": "second"},
                {"level": 25, "move": "Dragon Pulse", "reasoning": "STAB"},
                {"level": 30, "move": "Excalibur", "reasoning": "signature"},
            ]
        },
        "rationale": {"learnset": "Fixable."},
        "alternatives": [],
    }
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(dupe))

    response = client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert response.status_code == 200
    body = response.json()
    rows = [(r["level"], r["move"]) for r in body["draft"]["learnset"]]
    # The duplicate was dropped (keep-lowest, with a warning); the skeleton
    # auto-repair then completes the draft, so Tackle appears at most once
    # at a non-zero level.
    nonzero_tackle = [lvl for lvl, mv in rows if mv == "Tackle" and lvl > 0]
    assert len(nonzero_tackle) <= 1
    assert any("@20" in w for w in body["warnings"])


def test_suggest_learnset_l0_plus_nonzero_accepted(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """L0 (on-evo) + one non-zero level for the same move is the B carve-out."""
    ok = {
        "draft": {
            "learnset": [
                {"level": 0, "move": "Dragon Pulse", "reasoning": "on-evo"},
                {"level": 20, "move": "Dragon Pulse", "reasoning": "relearn"},
                {"level": 1, "move": "Tackle", "reasoning": "basic"},
            ]
        },
        "rationale": {"learnset": "B carve-out."},
        "alternatives": [],
    }
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(ok))

    response = client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert response.status_code == 200
    rows = response.json()["draft"]["learnset"]
    assert sum(1 for r in rows if r["move"] == "Dragon Pulse") == 2


def test_suggest_learnset_unsorted_input_sorted_on_output(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """Unsorted draft comes back sorted by (level, name)."""
    unsorted = {
        "draft": {
            "learnset": [
                {"level": 30, "move": "Excalibur", "reasoning": "signature"},
                {"level": 5, "move": "Dragon Pulse", "reasoning": "STAB"},
                {"level": 1, "move": "Tackle", "reasoning": "basic"},
            ]
        },
        "rationale": {"learnset": "OK."},
        "alternatives": [],
    }
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(unsorted))

    response = client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert response.status_code == 200
    rows = response.json()["draft"]["learnset"]
    keys = [(r["level"], r["move"]) for r in rows]
    assert keys == sorted(keys)


# ===========================================================================
# ac6 — Port invariants: one call, no write, missing key → 503
# ===========================================================================


def test_suggest_learnset_calls_provider_exactly_once(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    provider = _FakeProvider(_skeleton_result("goodra", ruleset_dir))
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert len(provider.calls) == 1
    assert provider.calls[0]["max_tokens"] == suggestmod.LEARNSET_MAX_TOKENS


def test_suggest_learnset_missing_key_is_recoverable_503(
    ruleset_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default Adapter with no key → 503, not 500."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client = _make_client(ruleset_dir, tmp_path, None)  # real Adapter

    response = client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_suggest_learnset_passes_direction_to_provider(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    provider = _FakeProvider(_GOOD_LEARNSET_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post(
        "/api/species/goodra/suggest/learnset",
        json={"mode": "full", "direction": "special-attacker focus"},
    )

    assert "special-attacker focus" in provider.calls[0]["user"]


def test_suggest_learnset_move_pool_in_cached_context(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """The move pool lands in cached_context so it's prompt-cached."""
    provider = _FakeProvider(_GOOD_LEARNSET_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    cached = provider.calls[0]["cached_context"]
    assert "Tackle" in cached
    assert "Dragon Pulse" in cached


# ===========================================================================
# ac7 — CRUD round-trip: PUT writes learnset; skill file exists and is sound
# ===========================================================================


def test_crud_roundtrip_learnset_override(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """PUT /api/species/{id} with a suggested-shape learnset → 200, stored whole."""
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_GOOD_LEARNSET_RESULT))

    payload = {
        "name": "Goodra",
        "chrooked_id": "goodra",
        "learnset": [
            {"level": 1, "move": "Tackle"},
            {"level": 5, "move": "Dragon Pulse"},
        ],
    }
    response = client.put("/api/species/goodra", json=payload)

    assert response.status_code == 200


def test_crud_roundtrip_learnset_without_reasoning(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """PUT accepts {level, move} rows (reasoning stripped before PUT)."""
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_GOOD_LEARNSET_RESULT))

    # Simulate what the skill does: strip reasoning before PUT.
    payload = {
        "name": "Goodra",
        "chrooked_id": "goodra",
        "learnset": [
            {"level": 0, "move": "Dragon Pulse"},
            {"level": 1, "move": "Tackle"},
        ],
    }
    response = client.put("/api/species/goodra", json=payload)

    assert response.status_code == 200


def test_skill_file_exists_and_is_confirmation_gated() -> None:
    """The learnset-suggest skill exists, has disable-model-invocation, and is confirmation-gated."""
    skill_path = (
        _REPO_ROOT / ".claude" / "skills" / "learnset-suggest" / "SKILL.md"
    )
    assert skill_path.exists(), "SKILL.md must exist"
    content = skill_path.read_text(encoding="utf-8")
    assert "disable-model-invocation: true" in content
    # Confirmation gate language.
    assert "explicit" in content.lower() or "without" in content.lower()
    # References both endpoints.
    assert "/suggest/learnset" in content
    assert "PUT" in content


def test_skill_file_references_both_modes() -> None:
    """The skill file documents both full and surgical modes."""
    skill_path = (
        _REPO_ROOT / ".claude" / "skills" / "learnset-suggest" / "SKILL.md"
    )
    content = skill_path.read_text(encoding="utf-8")
    assert "full" in content
    assert "surgical" in content


# ===========================================================================
# Regression tests — bounce 1 defect: token-budget + truncation error (ac1)
# ===========================================================================


def test_suggest_learnset_uses_learnset_max_tokens(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """suggest_learnset passes LEARNSET_MAX_TOKENS (4096), not DEFAULT_MAX_TOKENS (1024).

    Regression guard for the bounce-1 defect: learnset responses (~15-25 rows
    with per-move reasoning) need a larger token budget than the tiny
    ability/typing/stats outputs. The mocked provider records the kwarg; assert
    it equals the capability-specific constant, not the shared 1024 default.
    """
    provider = _FakeProvider(_skeleton_result("goodra", ruleset_dir))
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert len(provider.calls) == 1
    recorded = provider.calls[0]["max_tokens"]
    assert recorded == suggestmod.LEARNSET_MAX_TOKENS, (
        f"Expected LEARNSET_MAX_TOKENS ({suggestmod.LEARNSET_MAX_TOKENS}), "
        f"got {recorded}. The learnset capability must not reuse DEFAULT_MAX_TOKENS."
    )
    assert recorded != llmmod.DEFAULT_MAX_TOKENS, (
        "max_tokens must not equal DEFAULT_MAX_TOKENS — the larger budget is required."
    )


def test_llm_provider_raises_llm_error_on_finish_reason_length(
    ruleset_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """finish_reason='length' from litellm → LlmError (surfaces as 503, not 422).

    Regression guard for the bounce-1 defect: without the finish_reason guard,
    a truncated response reaches _parse_tool_arguments and raises a misleading
    LlmError("did not include a structured proposal") that looked like a bad
    draft → 422. With the guard, truncation surfaces as an honest 503.

    This test exercises the real LiteLlmProvider.propose with a mocked
    litellm.completion that returns a truncated-looking response.
    """
    import types

    # Build a minimal mock response whose finish_reason is "length".
    # Structure mirrors what litellm.completion returns.
    mock_tool_call = types.SimpleNamespace(
        function=types.SimpleNamespace(arguments='{"draft": {"learnset": [')
    )
    mock_message = types.SimpleNamespace(
        tool_calls=[mock_tool_call],
    )
    mock_choice = types.SimpleNamespace(
        finish_reason="length",
        message=mock_message,
    )
    mock_response = types.SimpleNamespace(choices=[mock_choice])

    import sys

    # Stub litellm so the real LiteLlmProvider can import it without the package.
    litellm_stub = types.ModuleType("litellm")
    litellm_stub.completion = lambda **kwargs: mock_response  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", litellm_stub)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    provider = llmmod.LiteLlmProvider()
    with pytest.raises(llmmod.LlmError, match="truncated"):
        provider.propose(
            system="rubric",
            cached_context="pool",
            user="context",
            schema={"type": "object", "properties": {}},
            max_tokens=llmmod.DEFAULT_MAX_TOKENS,
        )


def test_suggest_learnset_truncated_response_is_503(
    ruleset_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real-adapter truncated response (finish_reason='length') → 503, not 422.

    Exercises the full route→adapter→finish_reason path so a future truncation
    surfaces as an honest "service unavailable" rather than a misleading
    "missing a draft learnset list" 422.
    """
    import sys
    import types

    mock_tool_call = types.SimpleNamespace(
        function=types.SimpleNamespace(arguments='{"draft": {"learnset": [')
    )
    mock_message = types.SimpleNamespace(tool_calls=[mock_tool_call])
    mock_choice = types.SimpleNamespace(finish_reason="length", message=mock_message)
    mock_response = types.SimpleNamespace(choices=[mock_choice])

    litellm_stub = types.ModuleType("litellm")
    litellm_stub.completion = lambda **kwargs: mock_response  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", litellm_stub)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    # provider=None → the route constructs a real LiteLlmProvider
    client = _make_client(ruleset_dir, tmp_path, None)

    response = client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert response.status_code == 503
    assert "truncated" in response.json()["detail"].lower()


class _SequenceProvider:
    """A mock Port that returns a different canned result per call, in order."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.calls: list[dict[str, Any]] = []

    def propose(self, **kwargs: Any) -> dict[str, Any]:
        result = self.results[len(self.calls)]
        self.calls.append(kwargs)
        return result


# =========================================================================== #
# Anchors — moves the user names outright (#89)
#
# The anchor field replaces naming moves inside the `direction` prose, which the
# slot skeleton silently overrode: 14 anchors named, 10 placed (2026-08-27,
# Ariados). An anchor now gets its own skeleton slot, and the warn-only diff is
# the backstop for the paths a skeleton cannot cover.
# =========================================================================== #


def test_suggest_learnset_anchors_reach_the_prompt(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    provider = _FakeProvider(_skeleton_result("goodra", ruleset_dir, anchors=["Dragon Pulse"]))
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post(
        "/api/species/goodra/suggest/learnset",
        json={"mode": "full", "anchors": ["Dragon Pulse"]},
    )

    user = provider.calls[0]["user"]
    assert "MOVES THE USER NAMED" in user
    assert "Dragon Pulse" in user
    assert "ANCHOR — the user named Dragon Pulse" in user


def test_suggest_learnset_placed_anchor_emits_no_warning(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    provider = _FakeProvider(_skeleton_result("goodra", ruleset_dir, anchors=["Dragon Pulse"]))
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post(
        "/api/species/goodra/suggest/learnset",
        json={"mode": "full", "anchors": ["Dragon Pulse"]},
    )

    assert response.status_code == 200
    body = response.json()
    moves = {row["move"] for row in body["draft"]["learnset"]}
    assert "Dragon Pulse" in moves
    assert not any(w.startswith("anchor:") for w in body.get("warnings") or [])


def test_suggest_learnset_unknown_anchor_is_422_before_the_port_call(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """A typo'd anchor must fail loud, and must not cost a round-trip."""
    provider = _FakeProvider(_GOOD_LEARNSET_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post(
        "/api/species/goodra/suggest/learnset",
        json={"mode": "full", "anchors": ["Flurb"]},
    )

    assert response.status_code == 422
    assert "Flurb" in response.json()["detail"]
    assert provider.calls == []


def test_resolve_anchors_rejects_more_than_the_cap() -> None:
    """Too many anchors erase the generated ladder, so the boundary refuses."""
    names = [f"Move {i}" for i in range(suggestmod.LEARNSET_ANCHOR_MAX + 1)]
    pool = [
        {"move": n, "type": "Normal", "category": "Physical", "power": 50, "effect": "hit"}
        for n in names
    ]
    with pytest.raises(suggestmod.SuggestError) as excinfo:
        suggestmod._resolve_anchors(names, pool, "full")
    assert str(suggestmod.LEARNSET_ANCHOR_MAX) in str(excinfo.value)


def test_resolve_anchors_canonicalizes_and_dedupes() -> None:
    pool = [
        {"move": "Dragon Pulse", "type": "Dragon", "category": "Special", "power": 85, "effect": "hit"},
    ]
    assert suggestmod._resolve_anchors(
        ["dragon pulse", " DRAGON PULSE "], pool, "full"
    ) == ["Dragon Pulse"]


def test_suggest_learnset_anchors_in_surgical_mode_is_422(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    provider = _FakeProvider(_SURGICAL_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post(
        "/api/species/goodra/suggest/learnset",
        json={"mode": "surgical", "instruction": "swap L1", "anchors": ["Dragon Pulse"]},
    )

    assert response.status_code == 422
    assert "surgical" in response.json()["detail"].lower()
    assert provider.calls == []


def test_suggest_learnset_empty_anchor_list_is_a_no_op(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """`anchors: []` must behave exactly like omitting the key."""
    provider = _FakeProvider(_skeleton_result("goodra", ruleset_dir))
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post(
        "/api/species/goodra/suggest/learnset",
        json={"mode": "full", "anchors": []},
    )

    assert response.status_code == 200
    assert "MOVES THE USER NAMED" not in provider.calls[0]["user"]


def test_validate_learnset_warns_when_the_draft_drops_an_anchor() -> None:
    """The warn-only backstop.

    Exercised directly rather than through the endpoint: with a skeleton in play
    the anchor is a hard slot, so a skeleton-valid draft that omits it cannot
    exist. This covers the skeleton-free path and the autofill shortfall.
    """
    # The size floor is min(LEARNSET_SIZE_MIN, len(pool)), so a pool smaller than
    # the floor forces the draft to use every move — and the anchor could never
    # be missing. Go wide enough that the floor caps at LEARNSET_SIZE_MIN.
    filler = [
        {"move": f"Filler {i}", "type": "Normal", "category": "Physical",
         "power": 50, "effect": "hit"}
        for i in range(suggestmod.LEARNSET_SIZE_MIN + 2)
    ]
    pool = filler + [
        {"move": "Dragon Pulse", "type": "Dragon", "category": "Special",
         "power": 85, "effect": "hit"},
    ]
    result = {
        "draft": {
            "learnset": [
                # spaced 4 apart: clears the early-packing caps and the L75 ceiling
                {"level": i * 4 + 1, "move": row["move"], "reasoning": "filler"}
                for i, row in enumerate(filler)
            ]
        },
        "rationale": {"learnset": "Standard."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result,
        pool,
        mode="full",
        current_learnset=[],
        anchors=["Dragon Pulse"],
    )
    assert any(
        w.startswith("anchor: Dragon Pulse") for w in out["warnings"]
    ), out.get("warnings")


def test_validate_learnset_anchor_diff_is_case_insensitive() -> None:
    """A placed anchor must not warn just because the request differed in case."""
    result = {
        "draft": {
            "learnset": [
                {"level": 1, "move": "Tackle", "reasoning": "basic"},
                {"level": 5, "move": "Dragon Pulse", "reasoning": "STAB"},
            ]
        },
        "rationale": {"learnset": "Standard."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result,
        _make_pool(),
        mode="full",
        current_learnset=[],
        anchors=["dragon pulse"],
    )
    assert not any(w.startswith("anchor:") for w in out.get("warnings") or [])
