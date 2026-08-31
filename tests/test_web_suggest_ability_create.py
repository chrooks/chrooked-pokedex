"""Issue #8 Phase A — custom-ability creation: propose endpoint + multi-write accept.

Exercises the ability-creation capability end to end through the API, with the
LLM Port **mocked** — so the suite runs with no ``litellm`` install, no API key,
and never makes a network call. Mirrors ``test_web_suggest_learnset.py``.

Capability:
- ``POST /api/abilities/suggest`` →
  ``{draft:{ability,behavior,distribution}, rationale:{ability,ai_rating,distribution}, alternatives}``

This is the FIRST capability that *creates* owned content (not picks from a pool)
and the FIRST to write to three places on accept (ability → behavior → species×N).

ACs covered (see the Throughline):
- ac1: propose returns the full draft shape; writes nothing on disk.
- ac2: behavior stub has empty engine_hints + the grounding note; a filled
  engine_hints → 422; the stub round-trips through the loader.
- ac3: slugify unit; an id colliding with an existing ability/behavior → 422.
- ac4: distribution validation (softened at bounce 1) — an out-of-dex species or
  an invalid slot row is DROPPED + recorded in `warnings` (valid rows kept, the
  proposal still 200); `replaces` enriched from the current slot; empty
  distribution accepted. The in-dex species roster is fed in cached_context.
- ac5: PUT /abilities, /behaviors, /species round-trip; a forced mid-sequence
  loader failure (invalid slot) → 422 with that file unwritten.
- ac6: missing key → 503 via the REAL adapter; provider.propose called once; no write.
- ac7: skill inspection — SKILL.md drives propose + the three writes, gated.
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
# In-memory snapshot: two species with named ability slots so distribution
# validation can resolve a species by name and enrich `replaces`.
# ---------------------------------------------------------------------------

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
            "evolution": {"from": "sliggoo", "method": {"kind": "EVO_LEVEL", "param": 50}},
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
    "type_chart": [
        {"attacker": "Water", "defender": "Fire", "multiplier": 2.0},
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


def _good_result(
    *,
    name: str = "Tidal Force",
    engine_hints: dict[str, str] | None = None,
    distribution: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    behavior: dict[str, Any] = {
        "effects": [
            {
                "summary": "Absorbs Water moves, gaining Speed.",
                "trigger": "on-hit",
                "when": "the incoming move is Water-type",
                "effect": "Negate the damage and raise Speed by one stage.",
            }
        ],
        "test_cases": [
            {"given": "hit by Surf", "expect": "no damage, +1 Speed"},
        ],
        "notes": ["Designed as a defensive pivot."],
    }
    if engine_hints is not None:
        behavior["engine_hints"] = engine_hints
    if distribution is None:
        distribution = [
            {"species": "Poliwag", "slot": "hidden", "reasoning": "thematic fit"},
        ]
    return {
        "draft": {
            "ability": {
                "name": name,
                "description": "Absorbs Water moves; gains Speed instead of damage.",
            },
            "behavior": behavior,
            "distribution": distribution,
        },
        "rationale": {
            "ability": "A Speed-scaling Water sponge.",
            "ai_rating": "B+ — strong but fair.",
            "distribution": "Underused Water line.",
        },
        "alternatives": [
            {"value": "Hydro Engine", "rationale": "boost power instead of Speed"},
        ],
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


def _files(ruleset_dir: Path, kind: str) -> set[str]:
    sub = ruleset_dir / kind
    if not sub.exists():
        return set()
    return {p.name for p in sub.iterdir()}


# ===========================================================================
# Unit tests — slugify_ability_id (M1)
# ===========================================================================


def test_slugify_basic() -> None:
    assert suggestmod.slugify_ability_id("Tidal Force") == "tidalforce"


def test_slugify_strips_punctuation_and_case() -> None:
    assert suggestmod.slugify_ability_id("Bone-Breaker!") == "bonebreaker"
    assert suggestmod.slugify_ability_id("AeroDynamic") == "aerodynamic"


def test_slugify_keeps_digits() -> None:
    assert suggestmod.slugify_ability_id("Form 2 Guard") == "form2guard"


# ===========================================================================
# Unit tests — _validate_ability_creation_result (M2 validator)
# ===========================================================================


def _dex_lookup() -> dict[str, dict[str, Any]]:
    """Name → merged-entry lookup mirroring what the route builds."""
    return {
        entry["name"].strip().casefold(): entry
        for entry in _SNAPSHOT["species"].values()
    }


def _validate(result: dict[str, Any], **kw: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "ability_ids": set(),
        "behavior_ids": set(),
        "dex_lookup": _dex_lookup(),
    }
    defaults.update(kw)
    return suggestmod._validate_ability_creation_result(result, **defaults)


def test_validate_accepts_good_draft() -> None:
    out = _validate(_good_result())
    assert out["draft"]["ability"]["chrooked_id"] == "tidalforce"
    assert out["draft"]["behavior"]["engine_hints"] == {}
    assert len(out["draft"]["distribution"]) == 1


def test_validate_empty_name_raises() -> None:
    bad = _good_result()
    bad["draft"]["ability"]["name"] = "   "
    with pytest.raises(suggestmod.SuggestError, match="no name"):
        _validate(bad)


def test_validate_filled_engine_hints_raises() -> None:
    """D1: a draft that fills engine_hints is refused."""
    bad = _good_result(engine_hints={"pokeemerald": "src/battle.c:1234"})
    with pytest.raises(suggestmod.SuggestError, match="engine_hints"):
        _validate(bad)


def test_validate_empty_engine_hints_ok_and_note_present() -> None:
    out = _validate(_good_result(engine_hints={}))
    behavior = out["draft"]["behavior"]
    assert behavior["engine_hints"] == {}
    assert any("STUB" in note for note in behavior["notes"])


def test_validate_no_effects_raises() -> None:
    bad = _good_result()
    bad["draft"]["behavior"]["effects"] = []
    with pytest.raises(suggestmod.SuggestError, match="no effects"):
        _validate(bad)


def test_validate_bad_trigger_raises() -> None:
    bad = _good_result()
    bad["draft"]["behavior"]["effects"][0]["trigger"] = "made-up-trigger"
    with pytest.raises(suggestmod.SuggestError, match="trigger"):
        _validate(bad)


def test_validate_collision_with_ability_id_raises() -> None:
    """D4: id matching an existing owned ability → refused."""
    with pytest.raises(suggestmod.SuggestError, match="already exists"):
        _validate(_good_result(), ability_ids={"tidalforce"})


def test_validate_collision_with_behavior_id_raises() -> None:
    """D4: id matching an existing behavior → refused."""
    with pytest.raises(suggestmod.SuggestError, match="already exists"):
        _validate(_good_result(), behavior_ids={"tidalforce"})


def test_validate_unknown_species_dropped_with_warning() -> None:
    """Bounce-1: an out-of-dex species is DROPPED + warned, not a request failure."""
    bad = _good_result(
        distribution=[
            {"species": "Mewthree", "slot": "hidden", "reasoning": "x"},
            {"species": "Poliwag", "slot": "hidden", "reasoning": "kept"},
        ]
    )
    out = _validate(bad)
    # The valid row survives (with replaces enriched); the bad one is gone.
    assert [r["species"] for r in out["draft"]["distribution"]] == ["poliwag"]
    assert out["draft"]["distribution"][0]["replaces"] == "Swift Swim"
    assert any("Mewthree" in w and "not in the dex" in w for w in out["warnings"])


def test_validate_bad_slot_dropped_with_warning() -> None:
    """Bounce-1: an invalid slot is DROPPED + warned, not a request failure."""
    bad = _good_result(
        distribution=[
            {"species": "Poliwag", "slot": "tertiary", "reasoning": "x"},
            {"species": "Goodra", "slot": "hidden", "reasoning": "kept"},
        ]
    )
    out = _validate(bad)
    assert [r["species"] for r in out["draft"]["distribution"]] == ["goodra"]
    assert any("tertiary" in w and "invalid slot" in w for w in out["warnings"])


def test_validate_all_rows_dropped_is_empty_with_warnings() -> None:
    """All-dropped distribution → empty list (allowed) + warnings explaining."""
    bad = _good_result(
        distribution=[{"species": "Mewthree", "slot": "hidden", "reasoning": "x"}]
    )
    out = _validate(bad)
    assert out["draft"]["distribution"] == []
    assert out["warnings"]


def test_validate_good_draft_has_empty_warnings() -> None:
    """A wholly-valid distribution carries an empty warnings list."""
    out = _validate(_good_result())
    assert out["warnings"] == []


def test_validate_replaces_enriched_from_current_slot() -> None:
    """`replaces` reflects the species' real current slot occupant."""
    out = _validate(
        _good_result(
            distribution=[{"species": "Poliwag", "slot": "primary", "reasoning": "x"}]
        )
    )
    row = out["draft"]["distribution"][0]
    assert row["species"] == "poliwag"
    assert row["replaces"] == "Water Absorb"  # Poliwag's primary slot


def test_validate_empty_slot_replaces_none() -> None:
    """An empty current slot enriches `replaces` to '(none)'."""
    out = _validate(
        _good_result(
            distribution=[{"species": "Goodra", "slot": "secondary", "reasoning": "x"}]
        )
    )
    assert out["draft"]["distribution"][0]["replaces"] == "(none)"


def test_validate_empty_distribution_accepted() -> None:
    """Zero-or-more species (D4): an empty distribution is valid."""
    out = _validate(_good_result(distribution=[]))
    assert out["draft"]["distribution"] == []


# ===========================================================================
# ac1 — propose returns the full draft + writes nothing
# ===========================================================================


def test_suggest_returns_contract(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_good_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post(
        "/api/abilities/suggest",
        json={"direction": "a Water sponge that boosts Speed when hit"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["draft"]["ability"]["chrooked_id"] == "tidalforce"
    assert body["draft"]["ability"]["name"] == "Tidal Force"
    assert "description" in body["draft"]["ability"]
    behavior = body["draft"]["behavior"]
    assert behavior["applies_to"] == "ability"
    assert behavior["engine_hints"] == {}
    assert behavior["effects"]
    assert body["draft"]["distribution"][0]["slot"] == "hidden"
    assert "ai_rating" in body["rationale"]
    assert "alternatives" in body


def test_suggest_writes_nothing(ruleset_dir: Path, tmp_path: Path) -> None:
    before = (
        _files(ruleset_dir, "abilities"),
        _files(ruleset_dir, "behaviors"),
        _files(ruleset_dir, "species"),
    )
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_good_result()))

    client.post("/api/abilities/suggest", json={"direction": "a Water sponge"})

    after = (
        _files(ruleset_dir, "abilities"),
        _files(ruleset_dir, "behaviors"),
        _files(ruleset_dir, "species"),
    )
    assert after == before


def test_suggest_missing_direction_is_422(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_good_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    response = client.post("/api/abilities/suggest", json={})

    assert response.status_code == 422
    assert provider.calls == [], "direction is required before the Port call"


# ===========================================================================
# ac2 — behavior stub: empty engine_hints + grounding note; filled → 422
# ===========================================================================


def test_suggest_filled_engine_hints_is_422(ruleset_dir: Path, tmp_path: Path) -> None:
    bad = _good_result(engine_hints={"pokeemerald": "src/battle_main.c:42"})
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(bad))

    response = client.post("/api/abilities/suggest", json={"direction": "x"})

    assert response.status_code == 422
    assert "engine_hints" in response.json()["detail"]


def test_behavior_stub_round_trips_through_loader(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """The stub (empty engine_hints) is a loader-valid write via PUT /behaviors."""
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_good_result()))
    propose = client.post(
        "/api/abilities/suggest", json={"direction": "a Water sponge"}
    )
    behavior = propose.json()["draft"]["behavior"]

    response = client.put(f"/api/behaviors/{behavior['chrooked_id']}", json=behavior)

    assert response.status_code == 200
    assert response.json()["engine_hints"] == {}


# ===========================================================================
# ac3 — slugified id + collision refusal
# ===========================================================================


def test_suggest_collision_with_existing_ability_is_422(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """A draft whose id matches an existing owned ability → 422 (no clobber)."""
    # The sample ruleset owns ability `poisonheal`; name "Poison Heal" → that id.
    bad = _good_result(name="Poison Heal", distribution=[])
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(bad))

    response = client.post("/api/abilities/suggest", json={"direction": "x"})

    assert response.status_code == 422
    assert "already exists" in response.json()["detail"]


def test_suggest_collision_with_existing_behavior_is_422(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """A draft whose id matches an existing behavior → 422 (no clobber)."""
    # The sample ruleset owns behavior `excalibur`.
    bad = _good_result(name="Excalibur", distribution=[])
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(bad))

    response = client.post("/api/abilities/suggest", json={"direction": "x"})

    assert response.status_code == 422
    assert "already exists" in response.json()["detail"]


def test_upsert_ability_still_overwrites(ruleset_dir: Path, tmp_path: Path) -> None:
    """upsert_ability is NOT guarded — it remains the editor's overwrite path."""
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_good_result()))
    payload = {"chrooked_id": "poisonheal", "name": "Poison Heal", "description": "v1"}
    first = client.put("/api/abilities/poisonheal", json=payload)
    assert first.status_code == 200
    payload["description"] = "v2 overwrite"
    second = client.put("/api/abilities/poisonheal", json=payload)
    assert second.status_code == 200
    assert second.json()["description"] == "v2 overwrite"


# ===========================================================================
# ac4 — distribution validation through the route
# ===========================================================================


def test_suggest_unknown_species_dropped_warned_still_200(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """Bounce-1: an out-of-dex species row is dropped + warned; proposal still 200."""
    bad = _good_result(
        distribution=[
            {"species": "Nonexistent", "slot": "hidden", "reasoning": "x"},
            {"species": "Poliwag", "slot": "hidden", "reasoning": "kept"},
        ]
    )
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(bad))

    response = client.post("/api/abilities/suggest", json={"direction": "x"})

    assert response.status_code == 200
    body = response.json()
    assert [r["species"] for r in body["draft"]["distribution"]] == ["poliwag"]
    assert body["draft"]["distribution"][0]["replaces"] == "Swift Swim"
    assert any("Nonexistent" in w and "not in the dex" in w for w in body["warnings"])


def test_suggest_bad_slot_dropped_warned_still_200(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """Bounce-1: an invalid-slot row is dropped + warned; proposal still 200."""
    bad = _good_result(
        distribution=[
            {"species": "Poliwag", "slot": "fourth", "reasoning": "x"},
            {"species": "Goodra", "slot": "hidden", "reasoning": "kept"},
        ]
    )
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(bad))

    response = client.post("/api/abilities/suggest", json={"direction": "x"})

    assert response.status_code == 200
    body = response.json()
    assert [r["species"] for r in body["draft"]["distribution"]] == ["goodra"]
    assert any("fourth" in w and "invalid slot" in w for w in body["warnings"])


# ===========================================================================
# ac5 — accept round-trips through CRUD; mid-sequence failure stops cleanly
# ===========================================================================


def test_accept_three_write_roundtrip(ruleset_dir: Path, tmp_path: Path) -> None:
    """ability → behavior → species each round-trip through the CRUD routes."""
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_good_result()))
    draft = client.post(
        "/api/abilities/suggest", json={"direction": "a Water sponge"}
    ).json()["draft"]

    ability = draft["ability"]
    a = client.put(f"/api/abilities/{ability['chrooked_id']}", json=ability)
    assert a.status_code == 200

    behavior = draft["behavior"]
    b = client.put(f"/api/behaviors/{behavior['chrooked_id']}", json=behavior)
    assert b.status_code == 200

    # Per the skill: merge the new ability into the chosen slot, PUT the species.
    row = draft["distribution"][0]
    species_payload = {
        "name": "Poliwag",
        "chrooked_id": row["species"],
        "abilities": {row["slot"]: ability["name"]},
    }
    s = client.put(f"/api/species/{row['species']}", json=species_payload)
    assert s.status_code == 200
    assert s.json()["abilities"]["hidden"] == "Tidal Force"


def test_accept_midsequence_failure_writes_nothing_for_that_file(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """A forced loader failure (invalid slot) on the species PUT → 422, unwritten.

    The ability + behavior already landed (valid on disk); only the failing
    species file is not written — the per-file Boundary holds.
    """
    client = _make_client(ruleset_dir, tmp_path, _FakeProvider(_good_result()))
    draft = client.post(
        "/api/abilities/suggest", json={"direction": "a Water sponge"}
    ).json()["draft"]

    ability = draft["ability"]
    assert client.put(f"/api/abilities/{ability['chrooked_id']}", json=ability).status_code == 200
    behavior = draft["behavior"]
    assert client.put(f"/api/behaviors/{behavior['chrooked_id']}", json=behavior).status_code == 200

    before = _files(ruleset_dir, "species")
    # Force a mid-sequence loader rejection: an unknown top-level field is
    # rejected by the CRUD Boundary (a stand-in for any loader failure).
    bad_species = {
        "name": "Poliwag",
        "chrooked_id": "poliwag",
        "abilities": {"hidden": "Tidal Force"},
        "bogus_field": "boom",  # unknown field → 422, nothing written
    }
    s = client.put("/api/species/poliwag", json=bad_species)

    assert s.status_code == 422
    # The species file was NOT written (no poliwag.yaml landed).
    assert _files(ruleset_dir, "species") == before
    assert "poliwag.yaml" not in _files(ruleset_dir, "species")
    # The ability + behavior writes DID land (partial state is valid on disk).
    assert "tidalforce.yaml" in _files(ruleset_dir, "abilities")
    assert "tidalforce.yaml" in _files(ruleset_dir, "behaviors")


# ===========================================================================
# ac6 — Port invariants: one call, no write, missing key → 503
# ===========================================================================


def test_suggest_calls_provider_exactly_once(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_good_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post("/api/abilities/suggest", json={"direction": "a Water sponge"})

    assert len(provider.calls) == 1
    assert provider.calls[0]["max_tokens"] == suggestmod.LEARNSET_MAX_TOKENS


def test_suggest_ability_pool_in_cached_context(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """The existing ability pool lands in cached_context (so it's prompt-cached)."""
    provider = _FakeProvider(_good_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post("/api/abilities/suggest", json={"direction": "a Water sponge"})

    cached = provider.calls[0]["cached_context"]
    assert "Water Absorb" in cached


def test_suggest_species_roster_in_cached_context(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    """Bounce-1: the in-dex species roster lands in cached_context (so picks stay
    in-dex and the prefix is prompt-cached)."""
    provider = _FakeProvider(_good_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post("/api/abilities/suggest", json={"direction": "a Water sponge"})

    cached = provider.calls[0]["cached_context"]
    # Both in-dex species names appear under the roster instruction.
    assert "roster" in cached.lower()
    assert "Poliwag" in cached
    assert "Goodra" in cached


def test_suggest_missing_key_is_recoverable_503(
    ruleset_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default Adapter with no key → 503, not 500, before any network call."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client = _make_client(ruleset_dir, tmp_path, None)  # real Adapter

    response = client.post("/api/abilities/suggest", json={"direction": "x"})

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_suggest_direction_reaches_provider(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_good_result())
    client = _make_client(ruleset_dir, tmp_path, provider)

    client.post(
        "/api/abilities/suggest", json={"direction": "a contact punisher"}
    )

    assert "a contact punisher" in provider.calls[0]["user"]


# ===========================================================================
# ac7 — skill inspection
# ===========================================================================


def test_skill_file_exists_and_is_confirmation_gated() -> None:
    skill_path = _REPO_ROOT / ".claude" / "skills" / "ability-create" / "SKILL.md"
    assert skill_path.exists(), "SKILL.md must exist"
    content = skill_path.read_text(encoding="utf-8")
    assert "disable-model-invocation: true" in content
    assert "explicit" in content.lower()


def test_skill_file_drives_propose_and_three_writes() -> None:
    skill_path = _REPO_ROOT / ".claude" / "skills" / "ability-create" / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8")
    assert "/api/abilities/suggest" in content
    assert "PUT" in content
    assert "/api/abilities/" in content
    assert "/api/behaviors/" in content
    assert "/api/species/" in content


def test_skill_file_never_authors_engine_hints() -> None:
    skill_path = _REPO_ROOT / ".claude" / "skills" / "ability-create" / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8")
    # The skill must instruct leaving engine_hints empty.
    assert "engine_hints" in content
    assert "empty" in content.lower()


# ===========================================================================
# Lore + blind on ability creation, scoped to the anchor species (#79)
#
# lore here means the ANCHOR SPECIES' lore, and blind applies. Standalone
# create (no `species` in the body) is a clean no-op, not an error.
# ===========================================================================


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


def test_ac1_lore_off_never_fetches(ruleset_dir: Path, tmp_path: Path) -> None:
    lore = _FakeLore()
    provider = _FakeProvider(_good_result())
    client = _lore_client(ruleset_dir, tmp_path, provider, lore)

    response = client.post(
        "/api/abilities/suggest",
        json={"direction": "a Water sponge", "species": "goodra"},
    )

    assert response.status_code == 200
    body = response.json()
    assert lore.calls == []
    assert body["lore"]["mode"] == "off"
    assert "Lore" not in provider.calls[0]["user"]


def test_ac1_lore_absent_is_also_off(ruleset_dir: Path, tmp_path: Path) -> None:
    lore = _FakeLore()
    provider = _FakeProvider(_good_result())
    client = _lore_client(ruleset_dir, tmp_path, provider, lore)

    response = client.post("/api/abilities/suggest", json={"direction": "x"})

    assert response.status_code == 200
    assert lore.calls == []
    assert response.json()["lore"]["mode"] == "off"


def test_ac2_anchor_species_full_lore_reaches_prompt(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    lore = _FakeLore()
    provider = _FakeProvider(_good_result())
    client = _lore_client(ruleset_dir, tmp_path, provider, lore)

    response = client.post(
        "/api/abilities/suggest",
        json={"direction": "a Water sponge", "species": "goodra", "lore": "full"},
    )

    assert response.status_code == 200
    assert lore.calls == [("goodra", "Goodra")]
    user = provider.calls[0]["user"]
    assert "cave-dwelling gastropod" in user
    assert "Goodra" in user
    assert response.json()["lore"]["mode"] == "full"


def test_ac3_blind_withholds_name_and_abilities(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    lore = _FakeLore()
    provider = _FakeProvider(_good_result())
    client = _lore_client(ruleset_dir, tmp_path, provider, lore)

    response = client.post(
        "/api/abilities/suggest",
        json={"direction": "a Water sponge", "species": "goodra", "lore": "blind"},
    )

    assert response.status_code == 200
    user = provider.calls[0]["user"]
    assert "Goodra" not in user
    assert "Pokemon" not in user and "Pokémon" not in user
    assert "Pokedex" not in user and "Pokédex" not in user
    assert "Sap Sipper" not in user and "Gooey" not in user  # current abilities
    assert "BLIND DESIGN:" in user
    assert "cave-dwelling gastropod" in user
    assert response.json()["lore"]["mode"] == "blind"


def test_ac4_no_anchor_species_blind_is_clean_noop(
    ruleset_dir: Path, tmp_path: Path
) -> None:
    lore = _FakeLore()
    provider = _FakeProvider(_good_result())
    client = _lore_client(ruleset_dir, tmp_path, provider, lore)

    response = client.post(
        "/api/abilities/suggest",
        json={"direction": "a Water sponge", "lore": "blind"},
    )

    assert response.status_code == 200
    assert lore.calls == []
    assert response.json()["lore"]["mode"] == "off"
    assert "BLIND DESIGN:" not in provider.calls[0]["user"]
