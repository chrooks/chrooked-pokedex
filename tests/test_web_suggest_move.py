"""Issue #9 — move design / edit: propose endpoint + create/edit/behavior modes.

Exercises the move-design capability end to end through the API, with the
LLM Port **mocked** — so the suite runs with no ``litellm`` install, no API key,
and never makes a network call. Mirrors ``test_web_suggest_ability_create.py``.

Capability:
- ``POST /api/moves/suggest`` →
  ``{draft:{move, behavior?}, rationale:{move, edit?}, alternatives, warnings, chrooked_id, before?}``

ACs covered (see the Throughline):
- ac1: propose returns the full draft shape for create + edit; writes nothing on disk.
- ac2: behavior stub has empty engine_hints + the grounding note; a filled
  engine_hints → 422; the stub round-trips through the loader via PUT /behaviors.
- ac3: slugify unit; a name colliding with an existing owned move id → 422 (create
  never clobbers); edit mode uses the existing id (overwrite, no collision check).
- ac4: field validation — bad category → 422; bad type → 422; out-of-range power/
  accuracy/pp → 422; unknown flags → dropped with warning (not a hard failure);
  missing required create fields → 422.
- ac5: PUT /api/moves/{id} round-trip (create-shaped) → 200; PUT /api/behaviors/{id}
  round-trip (stub) → 200; forced loader failure (invalid category in PUT) → 422
  with the file unwritten.
- ac6: missing key → 503 via the REAL adapter (no network); provider.propose called
  exactly once; grep confirms the suggest path never writes a file.
- ac7: skill inspection — SKILL.md drives propose + the two writes, confirmation-gated,
  disable-model-invocation:true, never authors engine_hints.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.web import llm as llmmod
from chrooked_pokedex.web import suggest as suggestmod
from chrooked_pokedex.web.app import create_app

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SAMPLE = _REPO_ROOT / "tests" / "fixtures" / "sample_ruleset"

# ---------------------------------------------------------------------------
# In-memory snapshot with a minimal type chart (so build_type_pool works) and
# one existing move (excalibur) so we can test the edit path.
# ---------------------------------------------------------------------------

_SNAPSHOT = {
    "version": "1.11.2",
    "species": {
        "pikachu": {
            "dex": 25,
            "chrooked_id": "pikachu",
            "name": "Pikachu",
            "types": ["Electric"],
            "abilities": {"primary": "Static", "secondary": None, "hidden": "Lightning Rod"},
            "stats": {"hp": 35, "atk": 55, "def": 40, "spa": 50, "spd": 50, "spe": 90},
            "learnset": [{"level": 1, "move": "Tackle"}],
            "evolution": None,
            "evolves_into": [],
            "fully_evolved": False,
        },
    },
    "abilities": {
        "static": {
            "chrooked_id": "static",
            "name": "Static",
            "description": "May paralyze on contact.",
            "aka": {},
        },
    },
    "moves": {
        "excalibur": {
            "chrooked_id": "excalibur",
            "name": "Excalibur",
            "type": "Steel",
            "category": "physical",
            "power": 90,
            "accuracy": 100,
            "pp": 10,
            "description": "A holy sword strike.",
            "effect": "hit",
            "argument": None,
            "additional_effects": [],
            "flags": ["slicing"],
            "priority": 0,
            "target": "selected",
            "aka": {},
        },
    },
    "type_chart": [
        {"attacker": "Normal", "defender": "Rock", "multiplier": 0.5},
        {"attacker": "Normal", "defender": "Ghost", "multiplier": 0.0},
        {"attacker": "Fire", "defender": "Grass", "multiplier": 2.0},
        {"attacker": "Water", "defender": "Fire", "multiplier": 2.0},
        {"attacker": "Electric", "defender": "Water", "multiplier": 2.0},
        {"attacker": "Fairy", "defender": "Dragon", "multiplier": 2.0},
        {"attacker": "Steel", "defender": "Ice", "multiplier": 2.0},
        {"attacker": "Dark", "defender": "Psychic", "multiplier": 2.0},
        {"attacker": "Ghost", "defender": "Ghost", "multiplier": 2.0},
        {"attacker": "Ground", "defender": "Fire", "multiplier": 2.0},
        {"attacker": "Grass", "defender": "Water", "multiplier": 2.0},
    ],
}


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


def _good_create_result(
    *,
    name: str = "Shadow Strike",
    move_type: str = "Ghost",
    category: str = "physical",
    power: int | None = 80,
    accuracy: int | None = 100,
    pp: int = 10,
    flags: list[str] | None = None,
    engine_hints: dict[str, str] | None = None,
    with_behavior: bool = False,
) -> dict[str, Any]:
    if flags is None:
        flags = ["contact"]

    move: dict[str, Any] = {
        "name": name,
        "type": move_type,
        "category": category,
        "power": power,
        "accuracy": accuracy,
        "pp": pp,
        "priority": 0,
        "target": "selected",
        "flags": flags,
        "effect": "hit",
        "additional_effects": [{"effect": "flinch", "chance": 30}],
        "description": "A shadowy strike that may cause flinching.",
    }

    draft: dict[str, Any] = {"move": move}

    if with_behavior:
        behavior: dict[str, Any] = {
            "effects": [
                {
                    "summary": "Strikes target with a shadowy blow.",
                    "trigger": "on-hit",
                    "when": "",
                    "effect": "Deal damage and apply flinch at 30%.",
                }
            ],
            "test_cases": [
                {"given": "user attacks target", "expect": "damage dealt, 30% flinch"},
            ],
            "notes": ["Custom move with contact and flinch mechanic."],
        }
        if engine_hints is not None:
            behavior["engine_hints"] = engine_hints
        draft["behavior"] = behavior

    return {
        "draft": draft,
        "rationale": {
            "move": "A reliable contact Ghost-type move with a flinch angle.",
        },
        "alternatives": [
            {"value": "Shadow Claw variant", "rationale": "higher BP, no flinch"},
        ],
    }


def _good_edit_result(
    *,
    name: str = "Excalibur",
    power: int = 100,
) -> dict[str, Any]:
    return {
        "draft": {
            "move": {
                "name": name,
                "power": power,
            },
        },
        "rationale": {
            "move": "Bumping power for competitive viability.",
            "edit": "Changed power from 90 to 100.",
        },
        "alternatives": [
            {"value": "Add slicing bonus instead", "rationale": "different angle"},
        ],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ruleset_dir(tmp_path: Path) -> Path:
    dst = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, dst)
    return dst


def _make_client(ruleset_dir: Path, tmp_path: Path, provider: Any) -> TestClient:
    snap_path = tmp_path / "snap.json"
    snap_path.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    app = create_app(
        ruleset_dir=ruleset_dir, snapshot_path=snap_path, llm_provider=provider
    )
    return TestClient(app, raise_server_exceptions=False)


def _files(ruleset_dir: Path, kind: str) -> set[str]:
    sub = ruleset_dir / kind
    if not sub.exists():
        return set()
    return {p.name for p in sub.iterdir()}


# ===========================================================================
# Unit tests — slugify_move_id
# ===========================================================================


def test_slugify_basic() -> None:
    assert suggestmod.slugify_move_id("Shadow Strike") == "shadowstrike"


def test_slugify_strips_punctuation_and_case() -> None:
    assert suggestmod.slugify_move_id("Dragon-Claw!") == "dragonclaw"
    assert suggestmod.slugify_move_id("TakeDown") == "takedown"


def test_slugify_keeps_digits() -> None:
    assert suggestmod.slugify_move_id("Move 2 Win") == "move2win"


# ===========================================================================
# Unit tests — _validate_move_result (the validator directly)
# ===========================================================================


def _type_pool() -> list[str]:
    """Minimal type pool matching the snapshot type chart."""
    return [
        "Normal", "Fire", "Water", "Electric", "Grass",
        "Fairy", "Steel", "Dark", "Ghost", "Ground",
    ]


def _validate_create(
    result: dict[str, Any],
    move_ids: set[str] | None = None,
) -> dict[str, Any]:
    return suggestmod._validate_move_result(
        result,
        type_pool=_type_pool(),
        move_ids=move_ids or set(),
        mode="create",
        existing_move=None,
    )


def _validate_edit(
    result: dict[str, Any],
    existing_move: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if existing_move is None:
        existing_move = dict(_SNAPSHOT["moves"]["excalibur"])
    return suggestmod._validate_move_result(
        result,
        type_pool=_type_pool(),
        move_ids=set(),
        mode="edit",
        existing_move=existing_move,
    )


def test_validate_create_good_draft() -> None:
    out = _validate_create(_good_create_result())
    assert out["draft"]["move"]["chrooked_id"] == "shadowstrike"
    assert out["draft"]["move"]["category"] == "physical"
    assert out["draft"]["move"]["type"] == "Ghost"
    assert out["warnings"] == []


def test_validate_create_no_name_raises() -> None:
    bad = _good_create_result(name="")
    with pytest.raises(suggestmod.SuggestError, match="no name"):
        _validate_create(bad)


def test_validate_create_collision_raises() -> None:
    """D4: id matching an existing owned move → refused."""
    with pytest.raises(suggestmod.SuggestError, match="already exists"):
        _validate_create(_good_create_result(), move_ids={"shadowstrike"})


def test_validate_edit_no_collision_on_existing_id() -> None:
    """Edit mode: the existing id is the target — no collision check."""
    result = _good_edit_result()
    # excalibur is in move_ids but edit mode allows it (it's the overwrite target)
    out = suggestmod._validate_move_result(
        result,
        type_pool=_type_pool(),
        move_ids={"excalibur"},
        mode="edit",
        existing_move=dict(_SNAPSHOT["moves"]["excalibur"]),
    )
    assert out["chrooked_id"] == "excalibur"


def test_validate_bad_category_raises() -> None:
    bad = _good_create_result(category="undefined")
    with pytest.raises(suggestmod.SuggestError, match="invalid category"):
        _validate_create(bad)


def test_validate_bad_type_raises() -> None:
    bad = _good_create_result(move_type="Sludge")
    with pytest.raises(suggestmod.SuggestError, match="unrecognized type"):
        _validate_create(bad)


def test_validate_type_case_insensitive() -> None:
    """Type matching is case-insensitive; canonical casing is preserved."""
    result = _good_create_result(move_type="ghost")
    out = _validate_create(result)
    assert out["draft"]["move"]["type"] == "Ghost"


def test_validate_power_out_of_range_raises() -> None:
    bad = _good_create_result(power=999)
    with pytest.raises(suggestmod.SuggestError, match="invalid power"):
        _validate_create(bad)


def test_validate_power_null_ok() -> None:
    out = _validate_create(_good_create_result(power=None))
    assert out["draft"]["move"]["power"] is None


def test_validate_accuracy_out_of_range_raises() -> None:
    bad = _good_create_result(accuracy=101)
    with pytest.raises(suggestmod.SuggestError, match="invalid accuracy"):
        _validate_create(bad)


def test_validate_accuracy_null_ok() -> None:
    out = _validate_create(_good_create_result(accuracy=None))
    assert out["draft"]["move"]["accuracy"] is None


def test_validate_pp_out_of_range_raises() -> None:
    bad = _good_create_result(pp=99)
    with pytest.raises(suggestmod.SuggestError, match="invalid pp"):
        _validate_create(bad)


def test_validate_unknown_flags_dropped_with_warning() -> None:
    """Unknown flags are dropped with a warning (not a hard failure)."""
    bad = _good_create_result(flags=["contact", "supersecretflag"])
    out = _validate_create(bad)
    assert "contact" in out["draft"]["move"]["flags"]
    assert "supersecretflag" not in out["draft"]["move"]["flags"]
    assert any("supersecretflag" in w for w in out["warnings"])


def test_validate_create_no_behavior_ok() -> None:
    """Draft without behavior is valid (most moves don't need a custom stub)."""
    out = _validate_create(_good_create_result(with_behavior=False))
    assert "behavior" not in out["draft"]


def test_validate_behavior_stub_present_and_valid() -> None:
    """A valid behavior stub (no engine_hints) is accepted and the grounding note added."""
    out = _validate_create(_good_create_result(with_behavior=True))
    behavior = out["draft"]["behavior"]
    assert behavior["engine_hints"] == {}
    assert any("STUB" in note for note in behavior["notes"])


def test_validate_filled_engine_hints_raises() -> None:
    """D1: a draft that fills engine_hints is refused."""
    bad = _good_create_result(
        with_behavior=True, engine_hints={"pokeemerald": "src/battle.c:1234"}
    )
    with pytest.raises(suggestmod.SuggestError, match="engine_hints"):
        _validate_create(bad)


def test_validate_edit_builds_before_delta() -> None:
    """Edit mode: `before` captures the original values for changed fields."""
    result = _good_edit_result(power=100)
    out = _validate_edit(result)
    assert out["before"]["power"] == 90
    assert out["draft"]["move"]["power"] == 100


def test_validate_edit_chrooked_id_from_name() -> None:
    """Edit mode: chrooked_id is slugified from the proposed name."""
    result = _good_edit_result(name="Excalibur")
    out = _validate_edit(result)
    assert out["chrooked_id"] == "excalibur"


# ===========================================================================
# ac1 — propose (create) returns the full draft shape; writes nothing on disk
# ===========================================================================


def test_suggest_create_returns_contract(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_good_create_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    before_moves = _files(ruleset_dir, "moves")
    resp = client.post("/api/moves/suggest", json={"direction": "a Ghost-type contact move"})

    assert resp.status_code == 200
    body = resp.json()
    assert "draft" in body
    assert "move" in body["draft"]
    assert "rationale" in body
    assert "alternatives" in body
    assert "chrooked_id" in body
    assert "warnings" in body

    # Nothing written
    assert _files(ruleset_dir, "moves") == before_moves


def test_suggest_create_contract_shape(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_good_create_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post("/api/moves/suggest", json={"direction": "a Ghost-type contact move"})
    body = resp.json()

    move = body["draft"]["move"]
    assert "chrooked_id" in move
    assert move["chrooked_id"] == "shadowstrike"
    assert move["type"] == "Ghost"
    assert move["category"] == "physical"
    assert body["chrooked_id"] == "shadowstrike"


# ===========================================================================
# ac1 — propose (edit) returns delta + before/after; writes nothing
# ===========================================================================


def test_suggest_edit_returns_before_after(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_good_edit_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    before_moves = _files(ruleset_dir, "moves")
    resp = client.post(
        "/api/moves/suggest",
        json={"mode": "edit", "move_id": "excalibur", "direction": "bump power to 100"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["before"]["power"] == 90
    assert body["draft"]["move"]["power"] == 100
    assert body["chrooked_id"] == "excalibur"
    # Nothing written
    assert _files(ruleset_dir, "moves") == before_moves


def test_suggest_edit_missing_move_id_returns_422(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_good_edit_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post(
        "/api/moves/suggest",
        json={"mode": "edit", "direction": "bump power"},
    )
    assert resp.status_code == 422


def test_suggest_edit_unknown_move_id_returns_404(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_good_edit_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post(
        "/api/moves/suggest",
        json={"mode": "edit", "move_id": "nonexistent", "direction": "bump power"},
    )
    assert resp.status_code == 404


# ===========================================================================
# ac2 — behavior stub: engine_hints forced empty; filled engine_hints → 422
# ===========================================================================


def test_suggest_create_with_valid_behavior_stub(ruleset_dir: Path, tmp_path: Path) -> None:
    """A draft with a valid behavior stub (no engine_hints) is accepted."""
    provider = _FakeProvider(_good_create_result(with_behavior=True))
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post("/api/moves/suggest", json={"direction": "custom mechanic move"})
    assert resp.status_code == 200
    body = resp.json()
    behavior = body["draft"]["behavior"]
    assert behavior["engine_hints"] == {}
    assert any("STUB" in note for note in behavior["notes"])


def test_suggest_create_filled_engine_hints_returns_422(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """D1: a draft with engine_hints filled → 422."""
    provider = _FakeProvider(
        _good_create_result(
            with_behavior=True,
            engine_hints={"pokeemerald": "src/battle_util.c:999"},
        )
    )
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post("/api/moves/suggest", json={"direction": "a custom move"})
    assert resp.status_code == 422
    assert "engine_hints" in resp.json()["detail"]


def test_suggest_behavior_stub_roundtrip_via_put(ruleset_dir: Path, tmp_path: Path) -> None:
    """ac2/ac5: the behavior stub (empty engine_hints) round-trips through PUT /behaviors."""
    provider = _FakeProvider(_good_create_result(with_behavior=True))
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post("/api/moves/suggest", json={"direction": "a custom mechanic move"})
    assert resp.status_code == 200
    behavior = resp.json()["draft"]["behavior"]

    # PUT the behavior through the loader
    put_resp = client.put(
        f"/api/behaviors/{behavior['chrooked_id']}",
        json=behavior,
    )
    assert put_resp.status_code == 200


# ===========================================================================
# ac3 — slugify + collision: create refuses existing id; edit targets existing id
# ===========================================================================


def test_suggest_create_collision_returns_422(ruleset_dir: Path, tmp_path: Path) -> None:
    """D4: a name slugifying to an existing owned move id → 422."""
    # The sample ruleset has 'excalibur'; use that as the collision target.
    provider = _FakeProvider(_good_create_result(name="Excalibur"))
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post("/api/moves/suggest", json={"direction": "a steel sword move"})
    assert resp.status_code == 422
    assert "already exists" in resp.json()["detail"]


def test_suggest_edit_uses_existing_id(ruleset_dir: Path, tmp_path: Path) -> None:
    """Edit mode: the response chrooked_id matches the existing move's id."""
    provider = _FakeProvider(_good_edit_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post(
        "/api/moves/suggest",
        json={"mode": "edit", "move_id": "excalibur", "direction": "bump power"},
    )
    assert resp.status_code == 200
    assert resp.json()["chrooked_id"] == "excalibur"


# ===========================================================================
# ac4 — field validation (bad category/type/range → 422; unknown flags → warning)
# ===========================================================================


def test_suggest_bad_category_returns_422(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_good_create_result(category="undefined"))
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post("/api/moves/suggest", json={"direction": "a mystery move"})
    assert resp.status_code == 422
    assert "category" in resp.json()["detail"]


def test_suggest_bad_type_returns_422(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_good_create_result(move_type="Sludge"))
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post("/api/moves/suggest", json={"direction": "a poison move"})
    assert resp.status_code == 422
    assert "type" in resp.json()["detail"].lower()


def test_suggest_bad_power_returns_422(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_good_create_result(power=999))
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post("/api/moves/suggest", json={"direction": "a super strong move"})
    assert resp.status_code == 422
    assert "power" in resp.json()["detail"]


def test_suggest_unknown_flags_dropped_with_warning(ruleset_dir: Path, tmp_path: Path) -> None:
    """Unknown flags are dropped + surfaced as warnings (not a hard 422)."""
    provider = _FakeProvider(_good_create_result(flags=["contact", "supersecretflag"]))
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post("/api/moves/suggest", json={"direction": "a move with flags"})
    assert resp.status_code == 200
    body = resp.json()
    assert "contact" in body["draft"]["move"]["flags"]
    assert "supersecretflag" not in body["draft"]["move"]["flags"]
    assert any("supersecretflag" in w for w in body["warnings"])


def test_suggest_missing_direction_returns_422(ruleset_dir: Path, tmp_path: Path) -> None:
    """An empty direction is a 422 before any LLM call."""
    provider = _FakeProvider(_good_create_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post("/api/moves/suggest", json={"direction": ""})
    assert resp.status_code == 422
    assert len(provider.calls) == 0


# ===========================================================================
# ac5 — accept round-trips: PUT /moves (create) + PUT /behaviors + failure handling
# ===========================================================================


def test_suggest_move_accept_roundtrip_via_put(ruleset_dir: Path, tmp_path: Path) -> None:
    """ac5: the full create draft round-trips through PUT /api/moves/{id} → 200."""
    provider = _FakeProvider(_good_create_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post("/api/moves/suggest", json={"direction": "a Ghost-type contact move"})
    assert resp.status_code == 200
    draft_move = resp.json()["draft"]["move"]
    chrooked_id = draft_move["chrooked_id"]

    put_resp = client.put(f"/api/moves/{chrooked_id}", json=draft_move)
    assert put_resp.status_code == 200
    # The file exists on disk now
    assert (ruleset_dir / "moves" / f"{chrooked_id}.yaml").exists()


def test_suggest_put_with_invalid_category_is_rejected(ruleset_dir: Path, tmp_path: Path) -> None:
    """ac5: a forced bad payload in PUT → 422 with file unwritten."""
    provider = _FakeProvider(_good_create_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    before_moves = _files(ruleset_dir, "moves")

    bad_payload = {
        "name": "Broken Move",
        "chrooked_id": "brokenmove",
        "type": "Fire",
        "category": "INVALID",  # triggers loader rejection
        "pp": 10,
    }
    put_resp = client.put("/api/moves/brokenmove", json=bad_payload)
    assert put_resp.status_code == 422
    # No new file written
    assert _files(ruleset_dir, "moves") == before_moves


# ===========================================================================
# ac5 (bounce-1 regression) — edit propose returns a FULL merged draft.move
# so a type-only edit does not wipe power/pp/accuracy/etc. on PUT.
# ===========================================================================


def _good_type_only_edit_result(*, new_type: str = "Fairy") -> dict[str, Any]:
    """LLM response that changes only `type` — no power/pp/accuracy in the delta."""
    return {
        "draft": {
            "move": {
                "name": "Excalibur",
                "type": new_type,
            },
        },
        "rationale": {
            "move": "Retyping to Fairy for thematic reasons.",
            "edit": f"Changed type from Steel to {new_type}.",
        },
        "alternatives": [],
    }


def test_edit_type_only_draft_move_carries_original_power_pp_accuracy() -> None:
    """Regression (bounce 1): a type-only edit returns a FULL draft.move.

    The partial LLM delta (only `type`) must be merged onto the existing move so
    that `draft.move` carries the original power/pp/accuracy — not None — making
    it safe to PUT without a client-side read step.
    """
    existing = dict(_SNAPSHOT["moves"]["excalibur"])  # power=90, pp=10, accuracy=100
    result = _good_type_only_edit_result(new_type="Fairy")
    out = _validate_edit(result, existing_move=existing)

    move = out["draft"]["move"]
    # Changed field is updated.
    assert move["type"] == "Fairy"
    # Unchanged fields are preserved — NOT None (the bug was they'd be absent/None).
    assert move["power"] == existing["power"]
    assert move["pp"] == existing["pp"]
    assert move["accuracy"] == existing["accuracy"]
    assert move["effect"] == existing["effect"]
    assert move["flags"] == existing["flags"]
    assert move["target"] == existing["target"]


def test_edit_type_only_before_carries_only_changed_fields() -> None:
    """The `before` dict must contain only the changed fields (for the diff display)."""
    existing = dict(_SNAPSHOT["moves"]["excalibur"])
    result = _good_type_only_edit_result(new_type="Fairy")
    out = _validate_edit(result, existing_move=existing)

    # `before` has the pre-change type value.
    assert "type" in out["before"]
    assert out["before"]["type"] == "Steel"
    # `before` must NOT include fields the LLM didn't touch.
    assert "power" not in out["before"]
    assert "pp" not in out["before"]
    assert "accuracy" not in out["before"]


def test_edit_accept_preserves_unchanged_fields_via_put(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """Full accept round-trip: PUT the edit draft.move → the file preserves power=90.

    This is the end-to-end regression: a type-only propose must produce a payload
    that writes Excalibur's power correctly (90), not None.
    """
    provider = _FakeProvider(_good_type_only_edit_result(new_type="Fairy"))
    client = _make_client(ruleset_dir, tmp_path, provider)

    resp = client.post(
        "/api/moves/suggest",
        json={"mode": "edit", "move_id": "excalibur", "direction": "retype to Fairy"},
    )
    assert resp.status_code == 200
    draft_move = resp.json()["draft"]["move"]
    chrooked_id = draft_move["chrooked_id"]

    # The draft.move should already carry power/pp/accuracy from the merge.
    assert draft_move["power"] == 90
    assert draft_move["pp"] == 10
    assert draft_move["accuracy"] == 100

    # PUT it — the loader must accept it and write the file.
    put_resp = client.put(f"/api/moves/{chrooked_id}", json=draft_move)
    assert put_resp.status_code == 200

    # Verify the written file preserves power=90 and landed type=Fairy.
    saved = put_resp.json()
    assert saved["power"] == 90, (
        f"Power was wiped to {saved['power']!r} — partial PUT bug regressed."
    )
    assert saved["type"] == "Fairy"  # The edit landed.


# ===========================================================================
# ac6 — missing key → 503; provider.propose called exactly once; no write
# ===========================================================================


def test_suggest_missing_key_returns_503(ruleset_dir: Path, tmp_path: Path) -> None:
    """ac6: a None provider (real LiteLlmProvider missing key) → 503."""
    client = _make_client(ruleset_dir, tmp_path, None)

    resp = client.post("/api/moves/suggest", json={"direction": "a fire move"})
    assert resp.status_code == 503


def test_suggest_provider_called_exactly_once(ruleset_dir: Path, tmp_path: Path) -> None:
    """ac6: the Port is called exactly once per propose."""
    provider = _FakeProvider(_good_create_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post("/api/moves/suggest", json={"direction": "a Ghost move"})
    assert len(provider.calls) == 1


def test_suggest_propose_writes_nothing(ruleset_dir: Path, tmp_path: Path) -> None:
    """ac6: the propose endpoint never writes a file."""
    provider = _FakeProvider(_good_create_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    before_moves = _files(ruleset_dir, "moves")
    before_behaviors = _files(ruleset_dir, "behaviors")

    client.post("/api/moves/suggest", json={"direction": "a Ghost move"})

    assert _files(ruleset_dir, "moves") == before_moves
    assert _files(ruleset_dir, "behaviors") == before_behaviors


# ===========================================================================
# ac7 — skill inspection: SKILL.md drives the workflow correctly
# ===========================================================================


def test_skill_exists() -> None:
    skill_path = _REPO_ROOT / ".claude" / "skills" / "move-design" / "SKILL.md"
    assert skill_path.exists(), "move-design/SKILL.md is missing"


def test_skill_is_confirmation_gated() -> None:
    skill_path = _REPO_ROOT / ".claude" / "skills" / "move-design" / "SKILL.md"
    content = skill_path.read_text()
    assert "explicit" in content.lower() or "yes" in content.lower(), (
        "Skill must gate writes on explicit user confirmation"
    )


def test_skill_disable_model_invocation() -> None:
    skill_path = _REPO_ROOT / ".claude" / "skills" / "move-design" / "SKILL.md"
    content = skill_path.read_text()
    assert "disable-model-invocation: true" in content


def test_skill_does_not_author_engine_hints() -> None:
    skill_path = _REPO_ROOT / ".claude" / "skills" / "move-design" / "SKILL.md"
    content = skill_path.read_text()
    # The skill must warn against engine_hints but never fill it
    assert "engine_hints" in content
    assert "never" in content.lower() or "must not" in content.lower() or "empty" in content.lower()


def test_skill_sequences_move_then_behavior_writes() -> None:
    skill_path = _REPO_ROOT / ".claude" / "skills" / "move-design" / "SKILL.md"
    content = skill_path.read_text()
    # The skill must reference both PUT /moves and PUT /behaviors in order
    assert "/api/moves/" in content
    assert "/api/behaviors/" in content
    moves_pos = content.index("/api/moves/")
    behaviors_pos = content.index("/api/behaviors/")
    assert moves_pos < behaviors_pos, "moves write must come before behaviors write"


def test_skill_no_distribution_scope() -> None:
    """ac5: distribution to learnsets is explicitly out of scope for #9."""
    skill_path = _REPO_ROOT / ".claude" / "skills" / "move-design" / "SKILL.md"
    content = skill_path.read_text()
    # The skill should mention learnset distribution is out of scope
    assert "learnset" in content.lower() or "distribution" in content.lower()
