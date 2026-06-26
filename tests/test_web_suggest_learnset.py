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
        ]
    },
    "rationale": {"learnset": "Standard physical-then-special progression for Goodra."},
    "alternatives": [
        {"value": "Tackle @ L5 — later start frees slot", "rationale": "Opens L1 for Growl."},
    ],
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


def test_validate_learnset_rejects_hallucinated_move() -> None:
    result = {
        "draft": {
            "learnset": [
                {"level": 1, "move": "FakeMove", "reasoning": "invented"},
            ]
        },
        "rationale": {"learnset": "Bad."},
        "alternatives": [],
    }
    with pytest.raises(suggestmod.SuggestError, match="move pool"):
        suggestmod._validate_learnset_result(
            result, _make_pool(), mode="full", current_learnset=[]
        )


def test_validate_learnset_rejects_level_101() -> None:
    result = {
        "draft": {
            "learnset": [
                {"level": 101, "move": "Tackle", "reasoning": "too high"},
            ]
        },
        "rationale": {"learnset": "Bad."},
        "alternatives": [],
    }
    with pytest.raises(suggestmod.SuggestError, match="outside \\[0, 100\\]"):
        suggestmod._validate_learnset_result(
            result, _make_pool(), mode="full", current_learnset=[]
        )


def test_validate_learnset_rejects_negative_level() -> None:
    result = {
        "draft": {
            "learnset": [
                {"level": -1, "move": "Tackle", "reasoning": "negative"},
            ]
        },
        "rationale": {"learnset": "Bad."},
        "alternatives": [],
    }
    with pytest.raises(suggestmod.SuggestError, match="outside \\[0, 100\\]"):
        suggestmod._validate_learnset_result(
            result, _make_pool(), mode="full", current_learnset=[]
        )


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


def test_validate_learnset_rejects_two_nonzero_levels() -> None:
    """Same move at two non-zero levels → SuggestError."""
    result = {
        "draft": {
            "learnset": [
                {"level": 5, "move": "Tackle", "reasoning": "first"},
                {"level": 20, "move": "Tackle", "reasoning": "second"},
            ]
        },
        "rationale": {"learnset": "Bad."},
        "alternatives": [],
    }
    with pytest.raises(suggestmod.SuggestError, match="multiple non-zero levels"):
        suggestmod._validate_learnset_result(
            result, _make_pool(), mode="full", current_learnset=[]
        )


def test_validate_learnset_rejects_more_than_two_rows_per_move() -> None:
    """More than 2 rows for one move → SuggestError (>2 total rows violates D4).

    Note: exact (level, move) duplicates are silently deduped first. To get >2
    rows for one move they must be at different levels: L0 + L5 + L20 (3 rows).
    """
    result = {
        "draft": {
            "learnset": [
                # L0 + non-zero is valid (B carve-out), but L0 + L5 + L20 = 3 rows
                # which means we'd need two non-zero levels → caught by the two-
                # non-zero check first (which fires before the >2-rows check).
                # So test exactly >2 by doing L0 + two non-zero (already covered)
                # OR by having 3 different moves to confirm the path fires.
                # The simplest valid test: assert the ">2 rows" error message path.
                # We trigger it via the len(levels) > 2 guard after non-zero check.
                # Two non-zero levels are rejected first; so test 3 identical
                # exact-pair rows → they dedup to 1. Instead: test 3 distinct rows
                # (L0, L5, L20) for one move to hit >2 rows. But two non-zero
                # levels fires first. The `>2 rows` branch guards against an edge
                # case that can't arise through the current logic, so we test the
                # two-non-zero path which covers the same intent.
                #
                # This test now validates the `>2 rows` message is correct for
                # L0 + two non-zero, but that hits `multiple non-zero levels` first.
                # Adjust: we just confirm D4 errors cleanly for any >B-rule violation.
                {"level": 0, "move": "Dragon Pulse", "reasoning": "on-evo"},
                {"level": 5, "move": "Dragon Pulse", "reasoning": "first non-zero"},
                {"level": 20, "move": "Dragon Pulse", "reasoning": "second non-zero"},
            ]
        },
        "rationale": {"learnset": "Bad."},
        "alternatives": [],
    }
    # Two non-zero levels fires first (before >2 rows check).
    with pytest.raises(suggestmod.SuggestError, match="non-zero"):
        suggestmod._validate_learnset_result(
            result, _make_pool(), mode="full", current_learnset=[]
        )


def test_validate_learnset_deduplicates_exact_pairs() -> None:
    """Exact (level, move) duplicates are silently deduplicated."""
    result = {
        "draft": {
            "learnset": [
                {"level": 1, "move": "Tackle", "reasoning": "a"},
                {"level": 1, "move": "Tackle", "reasoning": "a"},  # exact dup
            ]
        },
        "rationale": {"learnset": "OK."},
        "alternatives": [],
    }
    out = suggestmod._validate_learnset_result(
        result, _make_pool(), mode="full", current_learnset=[]
    )
    assert len(out["draft"]["learnset"]) == 1


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

    provider = _FakeProvider(_GOOD_LEARNSET_RESULT)
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

    provider = _FakeProvider(_GOOD_LEARNSET_RESULT)
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


def test_suggest_learnset_hallucinated_move_is_422(
    ruleset_dir: Path, tmp_path: Path
) -> None:
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
    assert "move pool" in response.json()["detail"].lower()
    assert _species_files(ruleset_dir) == before


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


def test_suggest_learnset_level_101_is_422(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    bad = {
        "draft": {
            "learnset": [
                {"level": 101, "move": "Tackle", "reasoning": "too high"},
            ]
        },
        "rationale": {"learnset": "Bad."},
        "alternatives": [],
    }
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(bad))

    response = client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert response.status_code == 422
    assert "0, 100" in response.json()["detail"]


def test_suggest_learnset_two_nonzero_levels_is_422(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    bad = {
        "draft": {
            "learnset": [
                {"level": 5, "move": "Tackle", "reasoning": "first"},
                {"level": 20, "move": "Tackle", "reasoning": "second"},
            ]
        },
        "rationale": {"learnset": "Bad."},
        "alternatives": [],
    }
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(bad))

    response = client.post("/api/species/goodra/suggest/learnset", json={"mode": "full"})

    assert response.status_code == 422
    assert "non-zero" in response.json()["detail"].lower()


def test_suggest_learnset_l0_plus_nonzero_accepted(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """L0 (on-evo) + one non-zero level for the same move is the B carve-out."""
    ok = {
        "draft": {
            "learnset": [
                {"level": 0, "move": "Dragon Pulse", "reasoning": "on-evo"},
                {"level": 20, "move": "Dragon Pulse", "reasoning": "relearn"},
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
    assert rows[0]["level"] == 1
    assert rows[1]["level"] == 5


# ===========================================================================
# ac6 — Port invariants: one call, no write, missing key → 503
# ===========================================================================


def test_suggest_learnset_calls_provider_exactly_once(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    provider = _FakeProvider(_GOOD_LEARNSET_RESULT)
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
    provider = _FakeProvider(_GOOD_LEARNSET_RESULT)
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


# ===========================================================================
# Line mode — suggest a learnset for the whole evolution line (one call per
# member, coherence threaded base→tip, per-member errors isolated).
# ===========================================================================


class _SequenceProvider:
    """A mock Port that returns a different canned result per call, in order."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.calls: list[dict[str, Any]] = []

    def propose(self, **kwargs: Any) -> dict[str, Any]:
        result = self.results[len(self.calls)]
        self.calls.append(kwargs)
        return result


class _RaisingProvider:
    """A mock Port that always raises LlmError (missing key / upstream outage)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def propose(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        raise llmmod.LlmError("OPENAI_API_KEY not configured")


def test_resolve_linear_chain_walks_base_to_tip() -> None:
    """The chain through any member is base→tip, derived from the FORWARD graph.

    Forward edges (``evolves_into[].to``) are reliable chrooked_ids; the backward
    parent map is inverted from them. Goomy is absent here (no forward edge points
    at Sliggoo), so the chain is just Sliggoo → Goodra."""
    entries = [
        {"chrooked_id": cid, **v} for cid, v in _SNAPSHOT["species"].items()
    ]
    children = suggestmod.build_evolution_children(entries)

    assert suggestmod.resolve_linear_chain(children, "goodra") == ["sliggoo", "goodra"]
    assert suggestmod.resolve_linear_chain(children, "sliggoo") == ["sliggoo", "goodra"]


def test_resolve_linear_chain_ignores_display_name_from_edges() -> None:
    """A chain resolves even when ``evolution.from`` holds a display name (an
    override-sourced edge), because topology comes from forward edges only. This
    is the Nido-line regression: Nidoking's override `from` is "Nidorino" (a name,
    not the `nidorino` chrooked_id), which must NOT break the walk."""
    entries = [
        {"chrooked_id": "nidoranm", "evolves_into": [{"to": "nidorino"}],
         "evolution": None},
        {"chrooked_id": "nidorino", "evolves_into": [{"to": "nidoking"}],
         "evolution": {"from": "Nidoran"}},  # display name, not chrooked_id
        {"chrooked_id": "nidoking", "evolves_into": [],
         "evolution": {"from": "Nidorino"}},  # display name, not chrooked_id
    ]
    children = suggestmod.build_evolution_children(entries)
    assert suggestmod.resolve_linear_chain(children, "nidoking") == [
        "nidoranm",
        "nidorino",
        "nidoking",
    ]


def test_line_endpoint_returns_stages_with_coherence(
    ruleset_dir_no_goodra: Path, tmp_path: Path
) -> None:
    """One stage per member, anchor flagged, chain label set; the second member's
    prompt carries the first member's accepted draft as coherence context; nothing
    is written to disk."""
    provider = _SequenceProvider([_GOOD_LEARNSET_RESULT, _GOOD_LEARNSET_RESULT])
    client = _make_client(ruleset_dir_no_goodra, tmp_path, provider)
    before = _species_files(ruleset_dir_no_goodra)

    response = client.post("/api/species/goodra/suggest/learnset/line", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["chain_label"] == "Sliggoo → Goodra"
    stages = body["stages"]
    assert [s["chrooked_id"] for s in stages] == ["sliggoo", "goodra"]
    assert [s["anchor"] for s in stages] == [False, True]
    # Each stage carries a draft and the member's current learnset for the diff.
    assert stages[0]["draft"]["learnset"][0]["move"] == "Tackle"
    assert stages[1]["current"] == [{"level": 1, "move": "Tackle"}, {"level": 5, "move": "Dragon Pulse"}]
    # One Port call per member; the tip's prompt threads the base member's draft.
    assert len(provider.calls) == 2
    assert "Family coherence" in provider.calls[1]["user"]
    assert "Sliggoo" in provider.calls[1]["user"]
    # Read-only: no species file written.
    assert _species_files(ruleset_dir_no_goodra) == before


def test_line_endpoint_isolates_per_member_error(
    ruleset_dir_no_goodra: Path, tmp_path: Path
) -> None:
    """A member whose proposal fails validation becomes a stage error; the other
    members still return their drafts (stages are independent)."""
    bad = {
        "draft": {"learnset": [{"level": 1, "move": "Flamethrower"}]},  # not in pool
        "rationale": {"learnset": "x"},
        "alternatives": [],
    }
    provider = _SequenceProvider([_GOOD_LEARNSET_RESULT, bad])
    client = _make_client(ruleset_dir_no_goodra, tmp_path, provider)

    response = client.post("/api/species/goodra/suggest/learnset/line", json={})

    assert response.status_code == 200
    stages = response.json()["stages"]
    assert stages[0]["error"] is None and stages[0]["draft"] is not None
    assert stages[1]["draft"] is None
    assert "Flamethrower" in stages[1]["error"]


def test_line_endpoint_missing_key_is_503(
    ruleset_dir_no_goodra: Path, tmp_path: Path
) -> None:
    """A missing key / upstream failure fails every member identically → 503."""
    client = _make_client(ruleset_dir_no_goodra, tmp_path, _RaisingProvider())
    response = client.post("/api/species/goodra/suggest/learnset/line", json={})
    assert response.status_code == 503


def test_line_endpoint_unknown_species_is_404(
    ruleset_dir_no_goodra: Path, tmp_path: Path
) -> None:
    """An unknown anchor species → 404 before any Port call."""
    provider = _SequenceProvider([])
    client = _make_client(ruleset_dir_no_goodra, tmp_path, provider)
    response = client.post("/api/species/nope/suggest/learnset/line", json={})
    assert response.status_code == 404
    assert provider.calls == []
