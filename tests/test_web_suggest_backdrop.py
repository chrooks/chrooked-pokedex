"""Suggest for Target-original forms — the backdrop fallback join.

A Rejuv-only mon (an Aevian form) exists in the Target's data but has no canon
entry: base 1.11.2 never heard of it and the Ruleset may not yet. A makeover
launched from that Target's backdrop hands the suggest routes the backdrop id
(`breloom--aevianform`); the payload's ``target`` names the backdrop so the
server builds the entry from the Target's dex (target ⊕ effective Ruleset)
instead of 404ing. Pools stay canon — an accepted draft lands in the Ruleset.

ACs:
- ac1: suggest with ``target`` resolves a backdrop-only id and runs the Port call
  with the backdrop entry as context.
- ac2: the same id WITHOUT ``target`` stays an honest 404 (no implicit scan).
- ac3: an id neither canon nor the backdrop knows 404s even with ``target``.
- ac4: read-back covers a backdrop-only id instead of silently skipping it.

The LLM Port is mocked (no litellm, no key, no network); the Rejuv snapshot
builder is monkeypatched (no ruby, no game folder).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.web import llm as llmmod
from chrooked_pokedex.web import targets as targetsmod
from chrooked_pokedex.web.app import create_app

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SAMPLE = _REPO_ROOT / "tests" / "fixtures" / "sample_ruleset"

# Canon: one ordinary species. The type_chart supplies the real type pool the
# typing suggest validates the draft against.
_CANON_SNAPSHOT = {
    "version": "1.11.2",
    "species": {
        "breloom": {
            "dex": 286,
            "chrooked_id": "breloom",
            "name": "Breloom",
            "types": ["Grass", "Fighting"],
            "abilities": {"primary": "Effect Spore", "secondary": None, "hidden": "Technician"},
            "stats": {"hp": 60, "atk": 130, "def": 80, "spa": 60, "spd": 60, "spe": 70},
            "learnset": [{"level": 1, "move": "Tackle"}],
        },
    },
    "abilities": {
        "effect-spore": {
            "chrooked_id": "effect-spore", "name": "Effect Spore",
            "description": "Contact may poison, sleep, or paralyze.", "aka": {},
        },
    },
    "moves": {},
    "type_chart": [
        {"attacker": "Grass", "defender": "Ghost", "multiplier": 1.0},
        {"attacker": "Ghost", "defender": "Fighting", "multiplier": 0.0},
        {"attacker": "Fighting", "defender": "Grass", "multiplier": 1.0},
    ],
}

# The Target: carries the Rejuv-original Aevian form canon has no entry for.
# `form` is what rekey_ruleset_to_rejuv reads to bridge Ruleset overrides on.
_TARGET_SNAPSHOT = {
    "version": "rejuv",
    "species": {
        "breloom": {
            "dex": 286,
            "chrooked_id": "breloom",
            "name": "Breloom",
            "form": "",
            "types": ["Grass", "Fighting"],
            "abilities": {"primary": "Effect Spore", "secondary": None, "hidden": "Technician"},
            "stats": {"hp": 60, "atk": 130, "def": 80, "spa": 60, "spd": 60, "spe": 70},
            "learnset": [{"level": 1, "move": "Tackle"}],
        },
        "breloom--aevianform": {
            "dex": 286,
            "chrooked_id": "breloom--aevianform",
            "name": "Breloom (Aevian Form)",
            "form": "Aevian Form",
            "types": ["Grass", "Ghost"],
            "abilities": {"primary": "Effect Spore", "secondary": None, "hidden": None},
            "stats": {"hp": 60, "atk": 130, "def": 80, "spa": 60, "spd": 60, "spe": 70},
            "learnset": [
                {"level": 1, "move": "Tackle"},
                {"level": 12, "move": "Needle Arm"},
            ],
        },
    },
    "abilities": {},
    "moves": {},
    "type_chart": [],
}

_GOOD_TYPING_RESULT = {
    "draft": {"types": ["Grass", "Ghost"]},
    "rationale": {"types": "Keeps the Aevian form's spectral identity."},
    "alternatives": [],
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
            {"system": system, "cached_context": cached_context, "user": user}
        )
        return self.result


@pytest.fixture
def ruleset_dir(tmp_path: Path) -> Path:
    dst = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, dst)
    return dst


@pytest.fixture
def client(
    ruleset_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[TestClient, str, _FakeProvider]:
    """An app with one registered rejuv Target whose snapshot is canned."""
    snap_path = tmp_path / "snap.json"
    snap_path.write_text(json.dumps(_CANON_SNAPSHOT), encoding="utf-8")
    # Registry row written directly — registration-time path validation is not
    # under test, and the snapshot builder below never touches the path.
    fork = tmp_path / "fork"
    fork.mkdir()
    targets_path = tmp_path / "targets.json"
    targets_path.write_text(
        json.dumps(
            [{"id": "t-rejuv", "label": "Rejuv", "path": str(fork), "engine": "rejuv"}]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        targetsmod.snapmod_rejuv,
        "build_snapshot_rejuv",
        lambda path: json.loads(json.dumps(_TARGET_SNAPSHOT)),
    )
    provider = _FakeProvider(_GOOD_TYPING_RESULT)
    app = create_app(
        ruleset_dir=ruleset_dir,
        snapshot_path=snap_path,
        llm_provider=provider,
        targets_path=targets_path,
    )
    return TestClient(app, raise_server_exceptions=False), "t-rejuv", provider


# --- ac1: suggest with `target` resolves the backdrop-only form ------------ #


def test_suggest_typing_falls_back_to_backdrop_target(
    client: tuple[TestClient, str, _FakeProvider],
) -> None:
    http, target_id, provider = client
    response = http.post(
        "/api/species/breloom--aevianform/suggest/typing",
        json={"target": target_id},
    )
    assert response.status_code == 200, response.text
    assert response.json()["draft"]["types"] == ["Grass", "Ghost"]
    # The Port call reasoned about the BACKDROP entry, not base Breloom.
    assert len(provider.calls) == 1
    context = provider.calls[0]["cached_context"] + provider.calls[0]["user"]
    assert "Breloom (Aevian Form)" in context


# --- ac2: no `target` in the payload → the honest 404 stays ---------------- #


def test_suggest_typing_404_without_target(
    client: tuple[TestClient, str, _FakeProvider],
) -> None:
    http, _, provider = client
    response = http.post("/api/species/breloom--aevianform/suggest/typing", json={})
    assert response.status_code == 404
    assert provider.calls == []


# --- ac3: an id neither side knows 404s even with `target` ----------------- #


def test_suggest_typing_404_for_unknown_id_with_target(
    client: tuple[TestClient, str, _FakeProvider],
) -> None:
    http, target_id, provider = client
    response = http.post(
        "/api/species/missingno--weirdform/suggest/typing",
        json={"target": target_id},
    )
    assert response.status_code == 404
    assert provider.calls == []


# --- ac4: read-back covers the backdrop-only species ----------------------- #


def test_read_back_covers_backdrop_only_species(
    client: tuple[TestClient, str, _FakeProvider],
) -> None:
    http, target_id, _ = client
    response = http.post(
        f"/api/targets/{target_id}/read-back",
        json={"chrooked_ids": ["breloom--aevianform"]},
    )
    assert response.status_code == 200, response.text
    rows = response.json()["species"]
    assert [row["chrooked_id"] for row in rows] == ["breloom--aevianform"]
    # The expected side came from the backdrop merge, so the fresh target parse
    # matches it — a covered row, not a silent skip.
    assert rows[0]["ok"] is True
