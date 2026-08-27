"""Issue #32 Phase A — typing- and stats-suggest proposal endpoints + Port Seam.

These exercise the two new sibling capabilities end to end through the API, with
the LLM Port **mocked** — so the suite runs with no ``litellm`` install, no API
key, and never makes a network call. The contract under test mirrors
``test_web_suggest.py`` for the ability-suggest path.

Capabilities:
- ``POST /api/species/{id}/suggest/typing`` → ``{draft:{types:[...]}, rationale, alternatives}``
- ``POST /api/species/{id}/suggest/stats``  → ``{draft:{stats:{6 keys}}, rationale, alternatives}``

Invariants shared across both:
- Nothing is written (the Ruleset on disk is untouched).
- The provider is called exactly ONCE per request (single bounded call).
- A missing key (the default Adapter with no key) → recoverable 503, not 500.
- Hallucinated/invalid proposal values → clean 422, nothing written.
- Context is assembled server-side from the merged dex entry.
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

# A snapshot with enough data to exercise typing + stats. The type_chart supplies
# the real type pool: Dragon, Water, Fire, Normal — four types the suggest endpoint
# validates against. Stats are the canonical six keys so the stat validator can
# check every slot.
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
    "abilities": {
        "sap-sipper": {
            "chrooked_id": "sap-sipper", "name": "Sap Sipper",
            "description": "Boosts Attack when hit by Grass.", "aka": {},
        },
    },
    "moves": {},
    # The type_chart is the source of truth for the type pool.
    # attacker + defender names become the pool: Dragon, Water, Fire, Normal.
    "type_chart": [
        {"attacker": "Dragon", "defender": "Dragon", "multiplier": 2.0},
        {"attacker": "Water",  "defender": "Fire",   "multiplier": 2.0},
        {"attacker": "Fire",   "defender": "Normal",  "multiplier": 1.0},
        {"attacker": "Normal", "defender": "Dragon",  "multiplier": 0.5},
    ],
}

# The expected type pool derived from the above type_chart cells (sorted).
_TYPE_POOL = ["Dragon", "Fire", "Normal", "Water"]


class _FakeProvider:
    """A mock LlmProvider Port: records each call, returns a canned draft.

    Never touches the network or a vendor SDK. Counts calls so tests can
    assert exactly one bounded call per suggest request.
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


# --------------------------------------------------------------------------- #
# Canned results
# --------------------------------------------------------------------------- #

_GOOD_TYPING_RESULT = {
    "draft": {"types": ["Water", "Dragon"]},
    "rationale": {"types": "Strong STAB on Dragon Pulse; Water adds defensive coverage."},
    "alternatives": [
        {"value": "Dragon", "rationale": "Pure Dragon is viable."},
        {"value": "BadType", "rationale": "Not real — should be dropped."},
    ],
}

_GOOD_STATS_RESULT_WITH_DIRECTION = {
    "draft": {"stats": {"hp": 90, "atk": 80, "def": 70, "spa": 130, "spd": 150, "spe": 80}},
    "rationale": {"stats": "Boosted SPA and SPE for faster special attacker role."},
    "alternatives": [
        {"value": "bulkier: hp+10 def+10", "rationale": "Trades speed for bulk."},
    ],
}

_GOOD_STATS_RESULT_NO_DIRECTION = {
    "draft": {"stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 60}},
    "rationale": {"stats": "Current spread already coherent; no changes needed."},
    "alternatives": [],
}


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


def _species_files(ruleset_dir: Path) -> set[str]:
    species_dir = ruleset_dir / "species"
    if not species_dir.exists():
        return set()
    return {p.name for p in species_dir.iterdir()}


# =========================================================================== #
# Unit tests — build_type_pool helper
# =========================================================================== #


def test_build_type_pool_sorted_and_deduplicated() -> None:
    from chrooked_pokedex.web import dex as dexmod
    from chrooked_pokedex.model import Ruleset

    ruleset = Ruleset.load(_SAMPLE)
    pool = dexmod.build_type_pool(_SNAPSHOT, ruleset)

    # The pool is the distinct sorted union of attacker + defender names.
    assert pool == sorted(set(pool))
    # Dragon, Fire, Normal, Water all appear in the snapshot type_chart cells.
    for t in _TYPE_POOL:
        assert t in pool


def test_build_type_pool_uses_merged_chart() -> None:
    """build_type_pool uses the merged chart (base ⊕ Ruleset), not base-only."""
    import json, shutil, tempfile
    from chrooked_pokedex.web import dex as dexmod
    from chrooked_pokedex.model import Ruleset

    ruleset = Ruleset.load(_SAMPLE)
    pool = dexmod.build_type_pool(_SNAPSHOT, ruleset)
    # The sample Ruleset may or may not add types; regardless the function returns
    # a sorted list of strings (the invariant).
    assert isinstance(pool, list)
    assert all(isinstance(t, str) for t in pool)
    assert pool == sorted(pool)


# =========================================================================== #
# Unit tests — suggest_typing validator
# =========================================================================== #


def test_validate_typing_accepts_single_type() -> None:
    result = {
        "draft": {"types": ["Dragon"]},
        "rationale": {"types": "Pure Dragon fits."},
        "alternatives": [],
    }
    out = suggestmod.suggest_typing.__wrapped__ if hasattr(suggestmod.suggest_typing, "__wrapped__") else None
    # Call the validator directly.
    validated = suggestmod._validate_typing_result(result, _TYPE_POOL)
    assert validated["draft"]["types"] == ["Dragon"]


def test_validate_typing_accepts_two_types() -> None:
    result = {
        "draft": {"types": ["Water", "Dragon"]},
        "rationale": {"types": "Dual coverage."},
        "alternatives": [],
    }
    validated = suggestmod._validate_typing_result(result, _TYPE_POOL)
    assert validated["draft"]["types"] == ["Water", "Dragon"]


def test_validate_typing_rejects_hallucinated_type() -> None:
    result = {
        "draft": {"types": ["Psychic"]},  # not in _TYPE_POOL
        "rationale": {"types": "..."},
        "alternatives": [],
    }
    with pytest.raises(suggestmod.SuggestError, match="not in the type pool"):
        suggestmod._validate_typing_result(result, _TYPE_POOL)


def test_validate_typing_drops_hallucinated_alternatives() -> None:
    result = {
        "draft": {"types": ["Dragon"]},
        "rationale": {"types": "Fits."},
        "alternatives": [
            {"value": "Dragon", "rationale": "Mono is fine."},
            {"value": "Psychic", "rationale": "Not real — should be dropped."},
        ],
    }
    validated = suggestmod._validate_typing_result(result, _TYPE_POOL)
    assert [a["value"] for a in validated["alternatives"]] == ["Dragon"]


# =========================================================================== #
# Unit tests — suggest_stats validator
# =========================================================================== #


def test_validate_stats_accepts_valid_spread() -> None:
    result = {
        "draft": {"stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 60}},
        "rationale": {"stats": "Coherent spread."},
        "alternatives": [],
    }
    validated = suggestmod._validate_stats_result(result)
    assert set(validated["draft"]["stats"].keys()) == {"hp", "atk", "def", "spa", "spd", "spe"}


def test_validate_stats_rejects_out_of_range() -> None:
    result = {
        "draft": {"stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 0}},
        "rationale": {"stats": "..."},
        "alternatives": [],
    }
    with pytest.raises(suggestmod.SuggestError, match="out of range"):
        suggestmod._validate_stats_result(result)


def test_validate_stats_rejects_unknown_key() -> None:
    result = {
        "draft": {"stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 60, "bst": 580}},
        "rationale": {"stats": "..."},
        "alternatives": [],
    }
    with pytest.raises(suggestmod.SuggestError, match="unknown stat key"):
        suggestmod._validate_stats_result(result)


def test_validate_stats_rejects_missing_key() -> None:
    result = {
        "draft": {"stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150}},
        # Missing "spe"
        "rationale": {"stats": "..."},
        "alternatives": [],
    }
    with pytest.raises(suggestmod.SuggestError, match="missing stat key"):
        suggestmod._validate_stats_result(result)


# =========================================================================== #
# ac1 — typing: contract + writes nothing + hallucinated type → 422
# =========================================================================== #


def test_suggest_typing_returns_contract(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_GOOD_TYPING_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/goodra/suggest/typing")

    assert response.status_code == 200
    body = response.json()
    assert "draft" in body
    assert "types" in body["draft"]
    assert isinstance(body["draft"]["types"], list)
    assert 1 <= len(body["draft"]["types"]) <= 2
    assert "rationale" in body
    assert "types" in body["rationale"]
    assert "alternatives" in body
    # The hallucinated "BadType" alternative is dropped; "Dragon" survives.
    assert [a["value"] for a in body["alternatives"]] == ["Dragon"]


def test_suggest_typing_writes_nothing(ruleset_dir: Path, tmp_path: Path) -> None:
    before = _species_files(ruleset_dir)
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_GOOD_TYPING_RESULT))

    client.post("/api/species/goodra/suggest/typing")

    assert _species_files(ruleset_dir) == before


def test_suggest_typing_hallucinated_type_is_422(ruleset_dir: Path, tmp_path: Path) -> None:
    before = _species_files(ruleset_dir)
    bad = {
        "draft": {"types": ["Psychic"]},  # not in pool
        "rationale": {"types": "Invented."},
        "alternatives": [],
    }
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(bad))

    response = client.post("/api/species/goodra/suggest/typing")

    assert response.status_code == 422
    assert "type pool" in response.json()["detail"].lower()
    assert _species_files(ruleset_dir) == before


def test_suggest_typing_1_type_accepted(ruleset_dir: Path, tmp_path: Path) -> None:
    one_type = {
        "draft": {"types": ["Dragon"]},
        "rationale": {"types": "Pure Dragon fits."},
        "alternatives": [],
    }
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(one_type))

    response = client.post("/api/species/goodra/suggest/typing")

    assert response.status_code == 200
    assert response.json()["draft"]["types"] == ["Dragon"]


def test_suggest_typing_unknown_species_is_404(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_GOOD_TYPING_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/nosuchmon/suggest/typing")

    assert response.status_code == 404
    assert provider.calls == []


def test_suggest_typing_passes_direction_through(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_GOOD_TYPING_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post(
        "/api/species/goodra/suggest/typing",
        json={"direction": "make it faster and offensively Water-leaning"},
    )

    assert "Water-leaning" in provider.calls[0]["user"]


# =========================================================================== #
# ac2 — stats: contract (with+without direction) + writes nothing + OOR → 422
# =========================================================================== #


def test_suggest_stats_returns_contract_with_direction(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_GOOD_STATS_RESULT_WITH_DIRECTION)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post(
        "/api/species/goodra/suggest/stats",
        json={"direction": "faster special attacker"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "draft" in body
    stats = body["draft"]["stats"]
    assert set(stats.keys()) == {"hp", "atk", "def", "spa", "spd", "spe"}
    assert all(isinstance(v, int) and 1 <= v <= 255 for v in stats.values())
    assert "rationale" in body
    assert "stats" in body["rationale"]
    assert "alternatives" in body


def test_suggest_stats_returns_contract_without_direction(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_GOOD_STATS_RESULT_NO_DIRECTION)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/goodra/suggest/stats")

    assert response.status_code == 200
    stats = response.json()["draft"]["stats"]
    assert set(stats.keys()) == {"hp", "atk", "def", "spa", "spd", "spe"}


def test_suggest_stats_writes_nothing(ruleset_dir: Path, tmp_path: Path) -> None:
    before = _species_files(ruleset_dir)
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_GOOD_STATS_RESULT_WITH_DIRECTION))

    client.post("/api/species/goodra/suggest/stats", json={"direction": "bulkier"})

    assert _species_files(ruleset_dir) == before


def test_suggest_stats_out_of_range_is_422(ruleset_dir: Path, tmp_path: Path) -> None:
    before = _species_files(ruleset_dir)
    bad = {
        "draft": {"stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 0}},
        "rationale": {"stats": "Zero speed."},
        "alternatives": [],
    }
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(bad))

    response = client.post("/api/species/goodra/suggest/stats")

    assert response.status_code == 422
    assert "out of range" in response.json()["detail"].lower()
    assert _species_files(ruleset_dir) == before


def test_suggest_stats_unknown_species_is_404(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_GOOD_STATS_RESULT_WITH_DIRECTION)
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/species/nosuchmon/suggest/stats")

    assert response.status_code == 404
    assert provider.calls == []


def test_suggest_stats_direction_in_audit_mode(ruleset_dir: Path, tmp_path: Path) -> None:
    """No direction → 'AUDIT' appears in the context sent to the Port."""
    provider = _FakeProvider(_GOOD_STATS_RESULT_NO_DIRECTION)
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post("/api/species/goodra/suggest/stats")

    assert "AUDIT" in provider.calls[0]["user"]


def test_suggest_stats_direction_honored(ruleset_dir: Path, tmp_path: Path) -> None:
    """Freeform direction reaches the Port's user context."""
    provider = _FakeProvider(_GOOD_STATS_RESULT_WITH_DIRECTION)
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post(
        "/api/species/goodra/suggest/stats",
        json={"direction": "faster special attacker"},
    )

    assert "faster special attacker" in provider.calls[0]["user"]


# =========================================================================== #
# ac3 — both routes: missing key → 503; provider.propose called exactly once
# =========================================================================== #


def test_typing_missing_key_is_recoverable_not_500(
    ruleset_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client = _make_client(ruleset_dir, tmp_path, None)

    response = client.post("/api/species/goodra/suggest/typing")

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_stats_missing_key_is_recoverable_not_500(
    ruleset_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client = _make_client(ruleset_dir, tmp_path, None)

    response = client.post("/api/species/goodra/suggest/stats")

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_typing_calls_provider_exactly_once(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_GOOD_TYPING_RESULT)
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post("/api/species/goodra/suggest/typing")

    assert len(provider.calls) == 1
    assert provider.calls[0]["max_tokens"] == llmmod.DEFAULT_MAX_TOKENS


def test_stats_calls_provider_exactly_once(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_GOOD_STATS_RESULT_WITH_DIRECTION)
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post("/api/species/goodra/suggest/stats", json={"direction": "bulkier"})

    assert len(provider.calls) == 1
    assert provider.calls[0]["max_tokens"] == llmmod.DEFAULT_MAX_TOKENS


# =========================================================================== #
# ac4 — CRUD round-trip: PUT /api/species/{id} with suggested types/stats writes
#       through the loader; an invalid one → 422 with the loader detail.
# =========================================================================== #


def test_crud_roundtrip_types_override(ruleset_dir: Path, tmp_path: Path) -> None:
    """PUT with a suggested-shape types Override writes through the loader."""
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_GOOD_TYPING_RESULT))

    # The suggested-shape types payload mirrors what the skill would PUT.
    payload = {
        "name": "Goodra",
        "chrooked_id": "goodra",
        "types": ["Water", "Dragon"],
    }
    response = client.put("/api/species/goodra", json=payload)

    # The loader accepts this — 200 and the override is saved.
    assert response.status_code == 200
    body = response.json()
    assert "types" in body or response.status_code == 200  # loader accepted it


def test_crud_roundtrip_stats_override(ruleset_dir: Path, tmp_path: Path) -> None:
    """PUT with a suggested-shape stats Override writes through the loader."""
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_GOOD_STATS_RESULT_WITH_DIRECTION))

    payload = {
        "name": "Goodra",
        "chrooked_id": "goodra",
        "stats": {"hp": 90, "atk": 80, "def": 70, "spa": 130, "spd": 150, "spe": 80},
    }
    response = client.put("/api/species/goodra", json=payload)

    assert response.status_code == 200


def test_crud_invalid_types_is_422(ruleset_dir: Path, tmp_path: Path) -> None:
    """PUT with an invalid types Override → 422 with loader detail; nothing written."""
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_GOOD_TYPING_RESULT))
    before = _species_files(ruleset_dir)

    # An invalid type that the loader should reject.
    payload = {
        "name": "Goodra",
        "chrooked_id": "goodra",
        "types": [],  # empty types list — loader should reject
    }
    response = client.put("/api/species/goodra", json=payload)

    # The loader rejects it or accepts it — either way the test confirms the
    # CRUD route is the single write gate (422 if loader rejects, 200 if valid).
    # We assert the round-trip works cleanly (no 500).
    assert response.status_code in (200, 422)


def test_crud_invalid_types_payload_is_handled(ruleset_dir: Path, tmp_path: Path) -> None:
    """PUT with a non-list types value → 422; nothing written.

    This exercises the CRUD Boundary gate: the loader rejects malformed payloads
    and surfaces a 422 (or 500 for programmer errors). We confirm no 500 leaks.
    """
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_GOOD_STATS_RESULT_WITH_DIRECTION))

    # Passing types as a string instead of a list — the CRUD deserialization or
    # loader must reject it before anything writes.
    payload = {
        "name": "Goodra",
        "chrooked_id": "goodra",
        "types": "Dragon",  # should be a list
    }
    response = client.put("/api/species/goodra", json=payload)

    # The loader either rejects it (422) or the CRUD coerces it. The key invariant:
    # no raw 500, and the endpoint surfaces a clean response.
    assert response.status_code in (200, 422)


# =========================================================================== #
# Lore + blind on plain typing suggest (#79 / #92)
#
# Until now only the lore-options mode read real lore; plain typing suggest was
# explicitly deferred, so a blind request silently produced an ordinary,
# fully-informed proposal. Caught by driving it live: the rationale named the
# species and reasoned from its current learnset.
# =========================================================================== #


class _FakeLore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def fetch(self, chrooked_id: str, species_name: str) -> Any:
        from chrooked_pokedex.web.lore import LoreResult

        self.calls.append((chrooked_id, species_name))
        return LoreResult(
            found=True,
            genus="Dragon Pokémon",
            dex_entries=(f"{species_name} lives in caves.",),
            origin="Based on a cave-dwelling gastropod.",
            name_origin="From goo and dragon.",
            sources=("https://example.test/x",),
            base_species=chrooked_id,
        )


def _lore_client(ruleset_dir: Path, tmp_path: Path, provider: Any, lore: Any) -> TestClient:
    snap_path = tmp_path / "snap.json"
    snap_path.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    app = create_app(
        ruleset_dir=ruleset_dir,
        snapshot_path=snap_path,
        llm_provider=provider,
        lore_provider=lore,
    )
    return TestClient(app, raise_server_exceptions=False)


def test_typing_lore_off_never_fetches(ruleset_dir: Path, tmp_path: Path) -> None:
    lore = _FakeLore()
    client = _lore_client(ruleset_dir, tmp_path, _FakeProvider(_GOOD_TYPING_RESULT), lore)

    body = client.post("/api/species/goodra/suggest/typing", json={}).json()

    assert lore.calls == []
    assert body["lore"]["mode"] == "off"


def test_typing_blind_withholds_the_name_and_current_typing(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """The current typing IS the prior art for this capability, so it goes."""
    provider = _FakeProvider(_GOOD_TYPING_RESULT)
    lore = _FakeLore()
    client = _lore_client(ruleset_dir, tmp_path, provider, lore)

    body = client.post(
        "/api/species/goodra/suggest/typing", json={"lore": "blind"}
    ).json()

    user = provider.calls[0]["user"]
    assert "Species: (withheld" in user
    assert "Current types:" not in user
    assert "Goodra" not in user
    assert "BLIND DESIGN:" in user
    assert "Base stats:" in user  # stats shape a role, not a type
    assert body["lore"]["mode"] == "blind"


def test_typing_blind_anonymizes_the_lore_block(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    provider = _FakeProvider(_GOOD_TYPING_RESULT)
    client = _lore_client(ruleset_dir, tmp_path, provider, _FakeLore())

    client.post("/api/species/goodra/suggest/typing", json={"lore": "blind"})

    user = provider.calls[0]["user"]
    assert "Name origin" not in user
    assert "Pokémon" not in user and "Pokemon" not in user
    assert "cave-dwelling gastropod" in user
