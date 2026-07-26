"""Ability distribution — propose recipients + SLOTS for an EXISTING ability.

Exercises ``POST /api/abilities/{id}/distribute`` and the reusable
``suggest_ability_distribution`` it wraps, with the LLM Port **mocked** (no
``litellm`` install, no key, no network). The distribution twin of
``test_web_suggest_ability_create.py``: it reuses the same ``_validate_distribution``
(species resolved BY NAME, hallucinated species DROPPED into warnings).

Opt-in note: this route fires ONLY when the SPA's ✦ Suggest button is clicked —
there is no server-side auto-trigger. The tests here cover the endpoint contract;
the click-gate lives in the frontend panels.
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

# Two species with named ability slots so distribution validation can resolve a
# species by name and enrich `replaces`; `gooey` is an ability the route can
# distribute (it exists in build_abilities via the snapshot).
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
            "learnset": [{"level": 1, "move": "Tackle"}],
            "evolution": None,
            "evolves_into": [],
            "fully_evolved": True,
        },
        "poliwag": {
            "dex": 60,
            "chrooked_id": "poliwag",
            "name": "Poliwag",
            "types": ["Water"],
            "abilities": {"primary": "Water Absorb", "secondary": "Damp", "hidden": "Swift Swim"},
            "stats": {"hp": 40, "atk": 50, "def": 40, "spa": 40, "spd": 40, "spe": 90},
            "learnset": [{"level": 1, "move": "Tackle"}],
            "evolution": None,
            "evolves_into": [],
            "fully_evolved": False,
        },
    },
    "abilities": {
        "gooey": {
            "chrooked_id": "gooey",
            "name": "Gooey",
            "description": "Contact moves lower the attacker's Speed stat.",
            "aka": {},
        },
        "water-absorb": {
            "chrooked_id": "water-absorb",
            "name": "Water Absorb",
            "description": "Heals when hit by a Water-type move.",
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
    },
    "type_chart": [{"attacker": "Water", "defender": "Fire", "multiplier": 2.0}],
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


def _result(distribution: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if distribution is None:
        distribution = [{"species": "Poliwag", "slot": "hidden", "reasoning": "slimy"}]
    return {
        "draft": {"distribution": distribution},
        "rationale": {"distribution": "Slime-adjacent Water line."},
    }


def _dex_lookup() -> dict[str, dict[str, Any]]:
    return {
        entry["name"].strip().casefold(): entry
        for entry in _SNAPSHOT["species"].values()
    }


def _roster() -> list[str]:
    return sorted(e["name"] for e in _SNAPSHOT["species"].values())


def _gooey() -> dict[str, Any]:
    return dict(_SNAPSHOT["abilities"]["gooey"])


# ===========================================================================
# Unit tests — suggest_ability_distribution (function level)
# ===========================================================================


def test_distribute_valid_rows_resolve() -> None:
    """A valid row resolves to a chrooked_id + slot with `replaces` enriched."""
    out = suggestmod.suggest_ability_distribution(
        provider=_FakeProvider(_result()),
        ability=_gooey(),
        dex_lookup=_dex_lookup(),
        roster=_roster(),
        prompt="slimy Water mons",
    )
    assert out["rows"] == [
        {
            "species": "poliwag",
            "slot": "hidden",
            "replaces": "Swift Swim",
            "reasoning": "slimy",
        }
    ]
    assert out["rationale"] == "Slime-adjacent Water line."
    assert out["warnings"] == []


def test_distribute_hallucinated_species_dropped_to_warnings() -> None:
    """An out-of-dex species is DROPPED into warnings; the valid row survives."""
    out = suggestmod.suggest_ability_distribution(
        provider=_FakeProvider(
            _result(
                [
                    {"species": "Mewthree", "slot": "hidden", "reasoning": "x"},
                    {"species": "Goodra", "slot": "hidden", "reasoning": "kept"},
                ]
            )
        ),
        ability=_gooey(),
        dex_lookup=_dex_lookup(),
        roster=_roster(),
        prompt="slimy mons",
    )
    assert [r["species"] for r in out["rows"]] == ["goodra"]
    assert any("Mewthree" in w and "not in the dex" in w for w in out["warnings"])


def test_distribute_empty_prompt_guarded() -> None:
    """An empty prompt raises before the Port is called (never guesses)."""
    provider = _FakeProvider(_result())
    with pytest.raises(suggestmod.SuggestError, match="prompt is required"):
        suggestmod.suggest_ability_distribution(
            provider=provider,
            ability=_gooey(),
            dex_lookup=_dex_lookup(),
            roster=_roster(),
            prompt="   ",
        )
    assert provider.calls == []


def test_distribute_uses_distribute_token_budget() -> None:
    """The distribution call uses the DISTRIBUTE token budget (a broad pick)."""
    provider = _FakeProvider(_result())
    suggestmod.suggest_ability_distribution(
        provider=provider,
        ability=_gooey(),
        dex_lookup=_dex_lookup(),
        roster=_roster(),
        prompt="slimy mons",
    )
    assert provider.calls[0]["max_tokens"] == suggestmod.DISTRIBUTE_MAX_TOKENS
    assert "roster" in provider.calls[0]["cached_context"].lower()


# ===========================================================================
# Size budget (evolution FAMILIES) — clamp + rubric threading
# ===========================================================================


def test_clamp_distribution_limit_defaults_and_bounds() -> None:
    """Missing/invalid → default; out-of-range → clamped; in-range → itself."""
    clamp = suggestmod.clamp_distribution_limit
    assert clamp(None) == suggestmod.DEFAULT_DISTRIBUTION_LIMIT == 12
    assert clamp("nope") == 12
    assert clamp(True) == 12  # bool is guarded (not treated as 1)
    assert clamp(0) == suggestmod.MIN_DISTRIBUTION_LIMIT == 1
    assert clamp(999) == suggestmod.MAX_DISTRIBUTION_LIMIT == 40
    assert clamp(5) == 5


def test_distribute_limit_bounds_families_in_rubric() -> None:
    """The chosen budget lands in the system rubric ('AT MOST {limit} ... families')."""
    provider = _FakeProvider(_result())
    suggestmod.suggest_ability_distribution(
        provider=provider,
        ability=_gooey(),
        dex_lookup=_dex_lookup(),
        roster=_roster(),
        prompt="slimy mons",
        limit=5,
    )
    system = provider.calls[0]["system"].lower()
    assert "at most 5" in system
    assert "families" in system
    assert "best-first" in system


def test_distribute_default_limit_when_omitted() -> None:
    """Omitting the limit still bounds the ask (12), never unbounded."""
    provider = _FakeProvider(_result())
    suggestmod.suggest_ability_distribution(
        provider=provider,
        ability=_gooey(),
        dex_lookup=_dex_lookup(),
        roster=_roster(),
        prompt="slimy mons",
    )
    assert "at most 12" in provider.calls[0]["system"].lower()


# ===========================================================================
# Route tests — POST /api/abilities/{id}/distribute
# ===========================================================================


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
    sub = ruleset_dir / "species"
    return {p.name for p in sub.iterdir()} if sub.exists() else set()


def test_route_returns_contract_and_writes_nothing(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    provider = _FakeProvider(_result())
    client = _make_client(ruleset_dir, tmp_path, provider)
    before = _species_files(ruleset_dir)

    response = client.post("/api/abilities/gooey/distribute", json={"prompt": "slimy"})

    assert response.status_code == 200
    body = response.json()
    assert body["rows"][0] == {
        "species": "poliwag",
        "slot": "hidden",
        "replaces": "Swift Swim",
        "reasoning": "slimy",
    }
    assert body["warnings"] == []
    assert len(provider.calls) == 1
    assert _species_files(ruleset_dir) == before  # read-only


def test_route_unknown_ability_is_404(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/abilities/nonexistent/distribute", json={"prompt": "x"})

    assert response.status_code == 404
    assert provider.calls == []


def test_route_falls_back_to_description_when_no_prompt(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """No prompt → the ability's own description drives the pick (one-click ✦)."""
    provider = _FakeProvider(_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/abilities/gooey/distribute", json={})

    assert response.status_code == 200
    assert "lower the attacker's Speed" in provider.calls[0]["user"]


def test_route_limit_defaults_and_clamps(ruleset_dir: Path, tmp_path: Path) -> None:
    """The route clamps the requested family budget and threads it to the rubric."""
    # Omitted → default 12.
    provider = _FakeProvider(_result())
    client = _make_client(ruleset_dir, tmp_path, provider)
    client.post("/api/abilities/gooey/distribute", json={"prompt": "x"})
    assert "at most 12" in provider.calls[0]["system"].lower()

    # Out-of-range high → clamped to 40.
    provider = _FakeProvider(_result())
    client = _make_client(ruleset_dir, tmp_path, provider)
    client.post("/api/abilities/gooey/distribute", json={"prompt": "x", "limit": 999})
    assert "at most 40" in provider.calls[0]["system"].lower()

    # In-range → used as-is.
    provider = _FakeProvider(_result())
    client = _make_client(ruleset_dir, tmp_path, provider)
    client.post("/api/abilities/gooey/distribute", json={"prompt": "x", "limit": 7})
    assert "at most 7" in provider.calls[0]["system"].lower()


def test_route_hallucinated_species_dropped_still_200(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    provider = _FakeProvider(
        _result(
            [
                {"species": "Nonexistent", "slot": "hidden", "reasoning": "x"},
                {"species": "Goodra", "slot": "hidden", "reasoning": "kept"},
            ]
        )
    )
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/abilities/gooey/distribute", json={"prompt": "x"})

    assert response.status_code == 200
    body = response.json()
    assert [r["species"] for r in body["rows"]] == ["goodra"]
    assert any("Nonexistent" in w for w in body["warnings"])
