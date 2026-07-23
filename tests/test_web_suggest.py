"""Issue #6 Phase A — the ability-suggest proposal endpoint + Port Seam.

These exercise the reusable propose Seam end to end through the API, with the
LLM Port **mocked** — so the suite runs with no `litellm` install, no API key,
and never makes a network call. The contract under test:

- ``POST /api/species/{id}/suggest/ability`` returns
  ``{draft:{abilities:{...}}, rationale:{...}, alternatives:[...]}`` and writes
  NOTHING (the Ruleset on disk is untouched).
- The provider is called exactly ONCE per request (a single bounded call).
- A missing key (the default Adapter with no key) → a recoverable 503, not a 500.
- A hallucinated ability name (not in the pool) → a clean 422, nothing written.
- Context is assembled server-side: the prompt carries this species' real
  stats/types/abilities/learnset and the real ability pool.
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

_SNAPSHOT = {
    "version": "1.11.2",
    "species": {
        "goodra": {
            "dex": 706,
            "chrooked_id": "goodra",
            "name": "Goodra",
            "types": ["Dragon"],
            "abilities": {"primary": "Sap Sipper", "secondary": None, "hidden": "Gooey"},
            "stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 60},
            "learnset": [{"level": 1, "move": "Tackle"}, {"level": 5, "move": "Dragon Pulse"}],
        },
    },
    # A small but real ability pool the merge surfaces; the suggest endpoint
    # validates the draft against exactly these names.
    "abilities": {
        "sap-sipper": {"chrooked_id": "sap-sipper", "name": "Sap Sipper", "description": "Boosts Attack when hit by Grass.", "aka": {}},
        "gooey": {"chrooked_id": "gooey", "name": "Gooey", "description": "Lowers attacker Speed on contact.", "aka": {}},
        "hydration": {"chrooked_id": "hydration", "name": "Hydration", "description": "Heals status in rain.", "aka": {}},
        "rough-skin": {"chrooked_id": "rough-skin", "name": "Rough Skin", "description": "Damages attacker on contact.", "aka": {}},
    },
    "moves": {},
    "type_chart": [{"attacker": "Water", "defender": "Fire", "multiplier": 1.0}],
}


class _FakeProvider:
    """A mock LlmProvider Port: records each call, returns a canned draft.

    Records the assembled prompt so a test can assert context was built
    server-side, counts calls so a test can assert exactly one bounded call,
    and never touches the network or a vendor SDK.
    """

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


_GOOD_RESULT = {
    "draft": {"abilities": {"hidden": "Rough Skin"}},
    "rationale": {"hidden": "Punishes contact attackers; fits a bulky body."},
    "alternatives": [
        {"value": "Hydration", "rationale": "Status immunity in rain."},
        {"value": "Made Up Ability", "rationale": "Not real — should be dropped."},
    ],
}


@pytest.fixture
def ruleset_dir(tmp_path: Path) -> Path:
    dst = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, dst)
    return dst


def _make_client(ruleset_dir: Path, tmp_path: Path, provider: Any) -> TestClient:
    snap_path = tmp_path / "1.11.2.json"
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


# --------------------------------------------------------------------------- #
# ac1 — the contract + writes nothing
# --------------------------------------------------------------------------- #


def test_suggest_returns_contract(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_GOOD_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/goodra/suggest/ability")

    assert response.status_code == 200
    body = response.json()
    assert body["draft"] == {"abilities": {"hidden": "Rough Skin"}}
    assert body["rationale"]["hidden"]
    # The hallucinated alternative is dropped; the real one survives.
    assert [alt["value"] for alt in body["alternatives"]] == ["Hydration"]


def test_suggest_writes_nothing(ruleset_dir: Path, tmp_path: Path) -> None:
    before = _species_files(ruleset_dir)
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_GOOD_RESULT))

    client.post("/api/species/goodra/suggest/ability")

    assert _species_files(ruleset_dir) == before


def test_suggest_passes_direction_through(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_GOOD_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post(
        "/api/species/goodra/suggest/ability",
        json={"direction": "make it a contact-punisher"},
    )

    assert "make it a contact-punisher" in provider.calls[0]["user"]


# --------------------------------------------------------------------------- #
# ac2 — single bounded call, structured, honest errors
# --------------------------------------------------------------------------- #


def test_suggest_calls_provider_exactly_once(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_GOOD_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post("/api/species/goodra/suggest/ability")

    assert len(provider.calls) == 1
    # The call is bounded by a max_tokens cap.
    assert provider.calls[0]["max_tokens"] == llmmod.DEFAULT_MAX_TOKENS


def test_missing_key_is_recoverable_not_500(ruleset_dir: Path, tmp_path: Path, monkeypatch) -> None:
    # No mock injected → the real LiteLLM Adapter is built; with no key it must
    # raise a recoverable LlmError surfaced as a 503, never a raw 500 traceback.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client = _make_client(ruleset_dir, tmp_path, None)

    response = client.post("/api/species/goodra/suggest/ability")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "ANTHROPIC_API_KEY" in detail


def test_provider_api_error_is_honest_503(ruleset_dir: Path, tmp_path: Path) -> None:
    class _FailingProvider:
        def propose(self, **kwargs: Any) -> dict[str, Any]:
            raise llmmod.LlmError("The LLM provider call failed: APIError.")

    client = _make_client(ruleset_dir, tmp_path, _FailingProvider())

    response = client.post("/api/species/goodra/suggest/ability")

    assert response.status_code == 503
    assert "failed" in response.json()["detail"]


# --------------------------------------------------------------------------- #
# Hallucinated ability → clean error, nothing written (existing-only invariant)
# --------------------------------------------------------------------------- #


def test_hallucinated_ability_is_422(ruleset_dir: Path, tmp_path: Path) -> None:
    before = _species_files(ruleset_dir)
    bad = {
        "draft": {"abilities": {"primary": "Imaginary Power"}},
        "rationale": {"primary": "Invented."},
        "alternatives": [],
    }
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(bad))

    response = client.post("/api/species/goodra/suggest/ability")

    assert response.status_code == 422
    assert "existing" in response.json()["detail"].lower()
    assert _species_files(ruleset_dir) == before


def test_empty_draft_is_422(ruleset_dir: Path, tmp_path: Path) -> None:
    empty = {"draft": {"abilities": {}}, "rationale": {}, "alternatives": []}
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(empty))

    response = client.post("/api/species/goodra/suggest/ability")

    assert response.status_code == 422


def test_unknown_species_is_404(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_GOOD_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/nosuchmon/suggest/ability")

    assert response.status_code == 404
    # The Port is never called for an unknown species — context is gathered first.
    assert provider.calls == []


# --------------------------------------------------------------------------- #
# Context assembly — the right pool + the species' real data reach the prompt
# --------------------------------------------------------------------------- #


def test_context_carries_pool_and_species_data(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_GOOD_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post("/api/species/goodra/suggest/ability")

    call = provider.calls[0]
    # The cached prefix is the real ability pool (every snapshot ability name).
    for name in ("Sap Sipper", "Gooey", "Hydration", "Rough Skin"):
        assert name in call["cached_context"]
    # The fresh user delta carries this species' MERGED data (base ⊕ Ruleset):
    # the sample Ruleset overrides Goodra's types/abilities/learnset, and the
    # context reflects the override — proving assembly uses the merged dex entry,
    # not the raw base. (The sample Override sets types Water/Dragon, a Liquidation
    # learnset, and a Sap Sipper hidden slot.)
    entry = client.get("/api/dex/goodra").json()
    assert entry["name"] in call["user"]
    for override_type in entry["types"]:
        assert override_type in call["user"]
    first_move = entry["learnset"][0]["move"]
    assert first_move in call["user"]


# --------------------------------------------------------------------------- #
# Unit-level: the pool builder + validator (the reusable helper Surface)
# --------------------------------------------------------------------------- #


def test_build_ability_pool_trims_and_sorts() -> None:
    abilities = [
        {"name": "Zephyr", "description": "z"},
        {"name": "Adrenaline", "description": "a", "extra": "ignored"},
        {"name": "", "description": "dropped — no name"},
    ]
    pool = suggestmod.build_ability_pool(abilities)
    assert pool == [
        {"name": "Adrenaline", "description": "a"},
        {"name": "Zephyr", "description": "z"},
    ]


# --------------------------------------------------------------------------- #
# Hallucinated-move self-repair (a MOVE proposed for an ability slot must not
# nuke the whole proposal). One retry → partial → NO PROPOSAL only when empty.
# --------------------------------------------------------------------------- #


class _ScriptedProvider:
    """Returns a scripted result per call (the last repeats if calls exceed it)."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.calls: list[dict[str, Any]] = []

    def propose(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.results) - 1)
        return self.results[index]


def _draft(abilities: dict[str, str]) -> dict[str, Any]:
    return {"draft": {"abilities": abilities}, "rationale": {}, "alternatives": []}


def test_invalid_then_valid_repairs_in_one_retry(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _ScriptedProvider([
        _draft({"hidden": "Nasty Plot"}),  # a MOVE — invalid
        _draft({"hidden": "Rough Skin"}),  # corrected on retry
    ])
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/goodra/suggest/ability")

    assert response.status_code == 200
    body = response.json()
    assert body["draft"]["abilities"] == {"hidden": "Rough Skin"}
    assert body.get("repaired") == 1
    assert "warnings" not in body  # fully corrected → no warnings
    assert len(provider.calls) == 2  # exactly one retry


def test_invalid_twice_returns_partial_with_warnings(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _ScriptedProvider([
        _draft({"primary": "Nasty Plot"}),                         # invalid move
        _draft({"primary": "Sap Sipper", "hidden": "Swords Dance"}),  # 1 valid, 1 move
    ])
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/goodra/suggest/ability")

    assert response.status_code == 200
    body = response.json()
    # The valid slot survives; the still-invalid slot is a per-slot warning.
    assert body["draft"]["abilities"] == {"primary": "Sap Sipper"}
    assert body["warnings"] and "Swords Dance" in body["warnings"][0]
    assert "hidden" in body["warnings"][0]
    assert body["repaired"] == 1


def test_repair_preserves_valid_slot_from_first_attempt(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _ScriptedProvider([
        _draft({"primary": "Sap Sipper", "hidden": "Nasty Plot"}),  # 1 valid, 1 move
        _draft({"hidden": "Rough Skin"}),                            # retry fixes hidden only
    ])
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/goodra/suggest/ability")

    assert response.status_code == 200
    # primary from the first attempt AND hidden from the retry both survive.
    assert response.json()["draft"]["abilities"] == {
        "primary": "Sap Sipper",
        "hidden": "Rough Skin",
    }
    assert "warnings" not in response.json()


def test_all_invalid_twice_is_no_proposal(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _ScriptedProvider([
        _draft({"primary": "Nasty Plot"}),
        _draft({"primary": "Swords Dance"}),
    ])
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/goodra/suggest/ability")

    assert response.status_code == 422
    assert "existing" in response.json()["detail"].lower()
    assert len(provider.calls) == 2  # tried the repair, then gave up
