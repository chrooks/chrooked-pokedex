"""Makeover Workbench backend additions — the four small Seams the workbench needs.

All hermetic (``-m unit``): the LLM Port is mocked, the design log writes to a tmp
Ruleset copy, and the read-back differ is a pure function. Covers:

- ``POST /api/species/{id}/suggest/typing`` with ``mode: "lore-options"`` returns
  2-3 lore-grounded typing+role options through the SAME Seam (One Seam), drops an
  option with a hallucinated type, and writes nothing.
- ``GET /api/meta/learnset-rubric`` serves the pacing bands from the repo JSON.
- ``POST /api/design-log`` validates + appends a dated section, and 422s without a
  direction; nothing is written on the reject.
- ``readback.diff_species`` / ``read_back`` — the pure proof differ.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.web import design_log as designlogmod
from chrooked_pokedex.web import readback as readbackmod
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
    "abilities": {
        "sap-sipper": {"chrooked_id": "sap-sipper", "name": "Sap Sipper", "description": "x", "aka": {}},
        "gooey": {"chrooked_id": "gooey", "name": "Gooey", "description": "x", "aka": {}},
    },
    "moves": {
        "tackle": {
            "chrooked_id": "tackle", "name": "Tackle", "type": "Normal",
            "category": "Physical", "power": 40, "accuracy": 100, "pp": 35,
            "description": "x", "effect": "hit", "argument": None,
            "additional_effects": [], "flags": [], "priority": 0,
            "target": "selected", "aka": {},
        },
        "dragon-pulse": {
            "chrooked_id": "dragon-pulse", "name": "Dragon Pulse", "type": "Dragon",
            "category": "Special", "power": 85, "accuracy": 100, "pp": 10,
            "description": "x", "effect": "hit", "argument": None,
            "additional_effects": [], "flags": [], "priority": 0,
            "target": "selected", "aka": {},
        },
    },
    # The type pool is the distinct set across the chart; list the types the
    # lore/typing tests pick from so the validator recognizes them.
    "type_chart": [
        {"attacker": "Water", "defender": "Fire", "multiplier": 2.0},
        {"attacker": "Dragon", "defender": "Dragon", "multiplier": 2.0},
        {"attacker": "Poison", "defender": "Grass", "multiplier": 2.0},
    ],
}


class _FakeProvider:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def propose(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.result


@pytest.fixture
def ruleset_dir(tmp_path: Path) -> Path:
    dst = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, dst)
    return dst


def _client(ruleset_dir: Path, tmp_path: Path, provider: Any = None) -> TestClient:
    snap_path = tmp_path / "1.11.2.json"
    snap_path.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    app = create_app(
        ruleset_dir=ruleset_dir, snapshot_path=snap_path, llm_provider=provider
    )
    return TestClient(app, raise_server_exceptions=False)


# --------------------------------------------------------------------------- #
# Lore options — the makeover opening move, on the typing Seam
# --------------------------------------------------------------------------- #

_LORE_RESULT = {
    "draft": {
        "options": [
            {"types": ["Water", "Dragon"], "role": "bulky special attacker", "rationale": "amphibious slug"},
            {"types": ["Poison", "Dragon"], "role": "stall pivot", "rationale": "gooey venom"},
            {"types": ["Fake", "Dragon"], "role": "dropped", "rationale": "hallucinated type"},
        ]
    },
    "rationale": {"options": "Goodra is a gentle amphibious slug."},
}


@pytest.mark.unit
def test_lore_options_returns_valid_options(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_LORE_RESULT)
    client = _client(ruleset_dir, tmp_path, provider)

    response = client.post(
        "/api/species/goodra/suggest/typing", json={"mode": "lore-options"}
    )

    assert response.status_code == 200
    options = response.json()["draft"]["options"]
    # The hallucinated-type option is dropped; the two valid ones survive.
    assert [o["role"] for o in options] == ["bulky special attacker", "stall pivot"]
    assert options[0]["types"] == ["Water", "Dragon"]
    assert len(provider.calls) == 1


@pytest.mark.unit
def test_lore_options_writes_nothing(ruleset_dir: Path, tmp_path: Path) -> None:
    before = {p.name for p in (ruleset_dir / "species").iterdir()}
    client = _client(ruleset_dir, tmp_path, _FakeProvider(_LORE_RESULT))

    client.post("/api/species/goodra/suggest/typing", json={"mode": "lore-options"})

    assert {p.name for p in (ruleset_dir / "species").iterdir()} == before


@pytest.mark.unit
def test_lore_options_all_hallucinated_is_422(ruleset_dir: Path, tmp_path: Path) -> None:
    bad = {"draft": {"options": [{"types": ["Nope"], "role": "x", "rationale": "y"}]}, "rationale": {}}
    client = _client(ruleset_dir, tmp_path, _FakeProvider(bad))

    response = client.post(
        "/api/species/goodra/suggest/typing", json={"mode": "lore-options"}
    )

    assert response.status_code == 422


@pytest.mark.unit
def test_plain_typing_mode_unaffected(ruleset_dir: Path, tmp_path: Path) -> None:
    # Without the lore-options mode the endpoint still returns a single typing draft.
    typing = {
        "draft": {"types": ["Water", "Dragon"]},
        "rationale": {"types": "STAB."},
        "alternatives": [],
    }
    client = _client(ruleset_dir, tmp_path, _FakeProvider(typing))

    response = client.post("/api/species/goodra/suggest/typing", json={})

    assert response.status_code == 200
    assert response.json()["draft"]["types"] == ["Water", "Dragon"]


# --------------------------------------------------------------------------- #
# Kept facets (à la carte): a KEPT typing constrains the lore options — every
# option keeps the current typing verbatim and differs only by role.
# --------------------------------------------------------------------------- #


class _SeqProvider:
    """Returns a scripted result per call (last repeats)."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.calls: list[dict[str, Any]] = []

    def propose(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.results[min(len(self.calls) - 1, len(self.results) - 1)]


# Goodra's current type in the fixture snapshot is Dragon.
_KEPT_OK = {
    "draft": {"options": [
        {"types": ["Dragon"], "role": "physical wallbreaker", "rationale": "a"},
        {"types": ["Dragon"], "role": "bulky trapper", "rationale": "b"},
    ]},
    "rationale": {"options": "Two roles within Dragon."},
}
_KEPT_VIOLATING = {
    "draft": {"options": [
        {"types": ["Water", "Dragon"], "role": "changed typing", "rationale": "a"},
        {"types": ["Poison", "Dragon"], "role": "also changed", "rationale": "b"},
    ]},
    "rationale": {"options": "These change the typing."},
}


@pytest.mark.unit
def test_kept_typing_puts_constraint_in_the_prompt(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _FakeProvider(_KEPT_OK)
    client = _client(ruleset_dir, tmp_path, provider)

    client.post(
        "/api/species/goodra/suggest/typing",
        json={"mode": "lore-options", "kept_types": ["Dragon"]},
    )

    system = provider.calls[0]["system"]
    assert "KEPT" in system and "Dragon" in system


@pytest.mark.unit
def test_kept_typing_options_echo_the_kept_typing(ruleset_dir: Path, tmp_path: Path) -> None:
    client = _client(ruleset_dir, tmp_path, _FakeProvider(_KEPT_OK))

    response = client.post(
        "/api/species/goodra/suggest/typing",
        json={"mode": "lore-options", "kept_types": ["Dragon"]},
    )

    assert response.status_code == 200
    options = response.json()["draft"]["options"]
    assert len(options) >= 2
    assert all(o["types"] == ["Dragon"] for o in options)


@pytest.mark.unit
def test_kept_typing_violation_triggers_one_retry(ruleset_dir: Path, tmp_path: Path) -> None:
    # First response changes the typing (all dropped -> <2 survive -> retry); the
    # retry keeps it -> a valid 200.
    provider = _SeqProvider([_KEPT_VIOLATING, _KEPT_OK])
    client = _client(ruleset_dir, tmp_path, provider)

    response = client.post(
        "/api/species/goodra/suggest/typing",
        json={"mode": "lore-options", "kept_types": ["Dragon"]},
    )

    assert response.status_code == 200
    assert all(o["types"] == ["Dragon"] for o in response.json()["draft"]["options"])
    assert len(provider.calls) == 2  # exactly one retry


@pytest.mark.unit
def test_kept_typing_violation_twice_is_honest_error(ruleset_dir: Path, tmp_path: Path) -> None:
    provider = _SeqProvider([_KEPT_VIOLATING, _KEPT_VIOLATING])
    client = _client(ruleset_dir, tmp_path, provider)

    response = client.post(
        "/api/species/goodra/suggest/typing",
        json={"mode": "lore-options", "kept_types": ["Dragon"]},
    )

    assert response.status_code == 422
    assert "typing" in response.json()["detail"].lower()
    assert len(provider.calls) == 2


# --------------------------------------------------------------------------- #
# Learnset rubric — the pacing bands as data
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_learnset_rubric_served(ruleset_dir: Path, tmp_path: Path) -> None:
    client = _client(ruleset_dir, tmp_path)

    response = client.get("/api/meta/learnset-rubric")

    assert response.status_code == 200
    body = response.json()
    bands = body["bands"]
    # The documented anchor: nothing above 60 BP before L20.
    first = bands[0]
    assert first["level_min"] == 1 and first["level_max"] == 19
    assert first["bp_max"] == 60
    # The late capstone band opens at 100 BP.
    assert bands[-1]["bp_min"] == 100


# --------------------------------------------------------------------------- #
# Design log — validated append, mirroring the file format
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_design_log_appends_section(ruleset_dir: Path, tmp_path: Path) -> None:
    client = _client(ruleset_dir, tmp_path)
    log_path = ruleset_dir / "DESIGN-LOG.md"
    before = log_path.read_text(encoding="utf-8") if log_path.exists() else ""

    response = client.post(
        "/api/design-log",
        json={
            "line": "Goodra line",
            "direction": "bulky special attacker",
            "corrections": "kept Dragon Pulse at L0",
        },
    )

    assert response.status_code == 200
    after = log_path.read_text(encoding="utf-8")
    assert "## " in response.json()["section"]
    assert "Goodra line" in after
    assert "kept Dragon Pulse at L0" in after
    # Append-only: the prior content is preserved.
    assert after.startswith(before) or before in after


@pytest.mark.unit
def test_design_log_accepts_directionless_run(ruleset_dir: Path, tmp_path: Path) -> None:
    # A direction-less à la carte run (learnset-only/mirror-only) sends a
    # facet-derived summary as the direction — the endpoint must NOT 422 (ac6).
    client = _client(ruleset_dir, tmp_path)
    log_path = ruleset_dir / "DESIGN-LOG.md"

    response = client.post(
        "/api/design-log",
        json={"line": "Goodra line", "direction": "learnset-only repass"},
    )

    assert response.status_code == 200
    assert "learnset-only repass" in log_path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_design_log_omits_direction_bullet_when_blank(ruleset_dir: Path, tmp_path: Path) -> None:
    # Even a truly blank direction must not 422; the Direction bullet is omitted.
    client = _client(ruleset_dir, tmp_path)

    response = client.post("/api/design-log", json={"line": "Goodra line", "corrections": "x"})

    assert response.status_code == 200
    section = response.json()["section"]
    assert "## " in section
    assert "**Direction:**" not in section
    assert "**Corrections:**" in section


@pytest.mark.unit
def test_design_log_still_requires_a_line(ruleset_dir: Path, tmp_path: Path) -> None:
    client = _client(ruleset_dir, tmp_path)
    response = client.post("/api/design-log", json={"direction": "whatever"})
    assert response.status_code == 422


@pytest.mark.unit
def test_design_log_render_omits_blank_bullets() -> None:
    section = designlogmod.render_entry(
        line="Test line", direction="a role", on_date="2026-07-23"
    )
    assert "## 2026-07-23 — Test line" in section
    assert "New mechanics" not in section
    assert "Corrections" not in section


# --------------------------------------------------------------------------- #
# Read-back — the pure proof differ
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_read_back_all_match() -> None:
    expected = {
        "chrooked_id": "goodra",
        "name": "Goodra",
        "types": ["Water", "Dragon"],
        "stats": {"hp": 90, "atk": 80, "def": 70, "spa": 130, "spd": 150, "spe": 80},
        "abilities": {"primary": "Sap Sipper", "secondary": None, "hidden": "Gooey"},
        "learnset": [{"level": 0, "move": "Dragon Pulse"}, {"level": 1, "move": "Tackle"}],
    }
    actual = {
        "types": ["Water", "Dragon"],
        "stats": {"hp": 90, "atk": 80, "def": 70, "spa": 130, "spd": 150, "spe": 80},
        "abilities": {"primary": "Sap Sipper", "secondary": None, "hidden": "Gooey"},
        "learnset": [{"level": 1, "move": "Tackle"}, {"level": 0, "move": "Dragon Pulse"}],
    }
    diff = readbackmod.diff_species(
        expected, actual, fields=["types", "stats", "abilities", "learnset"]
    )
    assert diff["ok"] is True
    assert diff["ok_count"] == diff["total"] > 0
    roll = readbackmod.read_back([diff])
    assert roll["ok"] is True


@pytest.mark.unit
def test_read_back_flags_a_mismatch() -> None:
    expected = {"chrooked_id": "x", "name": "X", "types": ["Water", "Dragon"]}
    actual = {"types": ["Dragon"]}  # apply did not land the Water half
    diff = readbackmod.diff_species(expected, actual, fields=["types"])
    assert diff["ok"] is False
    assert diff["checks"][0]["ok"] is False
    assert diff["checks"][0]["expected"] == ["Water", "Dragon"]


@pytest.mark.unit
def test_read_back_missing_species_fails() -> None:
    expected = {"chrooked_id": "x", "name": "X", "types": ["Water"]}
    diff = readbackmod.diff_species(expected, None, fields=["types"])
    assert diff["missing"] is True
    assert diff["ok"] is False


# --------------------------------------------------------------------------- #
# Resolution-space normalization: PBS stores engine symbols (SERENEGRACE) while
# the Ruleset stores display names (Serene Grace) — compare in symbol space so
# these are NOT false mismatches, but a genuinely different value still mismatches.
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_read_back_display_vs_symbol_matches() -> None:
    expected = {
        "chrooked_id": "mismagius", "name": "Mismagius",
        "types": ["Ghost", "Fairy"],
        "abilities": {"primary": "Levitate", "secondary": "Serene Grace", "hidden": "Pixilate"},
        "learnset": [{"level": 0, "move": "Shadow Ball"}, {"level": 1, "move": "Magical Leaf"}],
    }
    actual = {  # what Essentials PBS holds on disk — engine symbols / uppercase
        "types": ["GHOST", "FAIRY"],
        "abilities": {"primary": "LEVITATE", "secondary": "SERENEGRACE", "hidden": "PIXILATE"},
        "learnset": [{"level": 0, "move": "SHADOWBALL"}, {"level": 1, "move": "MAGICALLEAF"}],
    }
    diff = readbackmod.diff_species(
        expected, actual, fields=["types", "abilities", "learnset"]
    )
    assert diff["ok"] is True, [c for c in diff["checks"] if not c["ok"]]
    assert diff["ok_count"] == diff["total"] > 0


@pytest.mark.unit
def test_read_back_genuine_ability_mismatch_shows_both_representations() -> None:
    expected = {"chrooked_id": "x", "name": "X", "abilities": {"primary": "Levitate"}}
    actual = {"abilities": {"primary": "PIXILATE"}}  # engine holds a different one
    diff = readbackmod.diff_species(expected, actual, fields=["abilities"])
    assert diff["ok"] is False
    check = diff["checks"][0]
    assert check["ok"] is False
    # Both representations are kept verbatim so the user sees what the engine holds.
    assert check["expected"] == "Levitate"
    assert check["actual"] == "PIXILATE"


@pytest.mark.unit
def test_read_back_respects_aka_essentials_hint() -> None:
    # An ability whose engine symbol deviates from the derived form: the aka hint
    # is the expected symbol (the applier used it), so it matches the disk value.
    expected = {"chrooked_id": "x", "name": "X", "abilities": {"primary": "Odd Ability"}}
    actual = {"abilities": {"primary": "ODDABILITYX"}}
    aka = {"odd ability": {"essentials": "ODDABILITYX"}}
    diff = readbackmod.diff_species(
        expected, actual, fields=["abilities"], aka_by_name=aka
    )
    assert diff["ok"] is True
    # Without the hint, the derived "ODDABILITY" would (correctly) NOT match.
    assert readbackmod.diff_species(expected, actual, fields=["abilities"])["ok"] is False


@pytest.mark.unit
def test_read_back_learnset_move_symbol_matches_but_wrong_move_mismatches() -> None:
    expected = {"chrooked_id": "x", "name": "X", "learnset": [{"level": 5, "move": "Aerial Ace"}]}
    assert readbackmod.diff_species(
        expected, {"learnset": [{"level": 5, "move": "AERIALACE"}]}, fields=["learnset"]
    )["ok"] is True
    assert readbackmod.diff_species(
        expected, {"learnset": [{"level": 5, "move": "TACKLE"}]}, fields=["learnset"]
    )["ok"] is False


# --------------------------------------------------------------------------- #
# ac9 — referential validation at the species write gate
# --------------------------------------------------------------------------- #


def _species_files_now(ruleset_dir: Path) -> set[str]:
    d = ruleset_dir / "species"
    return {p.name for p in d.iterdir()} if d.exists() else set()


@pytest.mark.unit
def test_write_gate_rejects_unknown_move(ruleset_dir: Path, tmp_path: Path) -> None:
    client = _client(ruleset_dir, tmp_path)
    before = _species_files_now(ruleset_dir)

    response = client.put(
        "/api/species/goodra",
        json={
            "name": "Goodra",
            "chrooked_id": "goodra",
            "learnset": [{"level": 1, "move": "Nonexistent Move"}],
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "learnset" in detail and "Nonexistent Move" in detail
    # Nothing new written on the reject (the gate ran before the write).
    assert _species_files_now(ruleset_dir) == before or "goodra.yaml" in before


@pytest.mark.unit
def test_write_gate_rejects_unknown_type(ruleset_dir: Path, tmp_path: Path) -> None:
    client = _client(ruleset_dir, tmp_path)
    response = client.put(
        "/api/species/goodra",
        json={"name": "Goodra", "chrooked_id": "goodra", "types": ["Faketype"]},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "types" in detail and "Faketype" in detail


@pytest.mark.unit
def test_write_gate_rejects_unknown_ability(ruleset_dir: Path, tmp_path: Path) -> None:
    client = _client(ruleset_dir, tmp_path)
    response = client.put(
        "/api/species/goodra",
        json={"name": "Goodra", "chrooked_id": "goodra", "abilities": {"primary": "Imaginary"}},
    )
    assert response.status_code == 422
    assert "Imaginary" in response.json()["detail"]


@pytest.mark.unit
def test_write_gate_accepts_valid_references(ruleset_dir: Path, tmp_path: Path) -> None:
    client = _client(ruleset_dir, tmp_path)
    response = client.put(
        "/api/species/goodra",
        json={
            "name": "Goodra",
            "chrooked_id": "goodra",
            "types": ["Water", "Dragon"],
            "abilities": {"primary": "Sap Sipper", "hidden": "Gooey"},
            "learnset": [{"level": 1, "move": "Tackle"}, {"level": 0, "move": "Dragon Pulse"}],
        },
    )
    assert response.status_code == 200


@pytest.mark.unit
def test_write_gate_accepts_owned_custom_ability(ruleset_dir: Path, tmp_path: Path) -> None:
    # A custom ability created this session (written BEFORE the species) must
    # resolve — the merged view includes owned content (ac9).
    client = _client(ruleset_dir, tmp_path)
    made = client.put(
        "/api/abilities/tidalforce",
        json={"chrooked_id": "tidalforce", "name": "Tidal Force", "description": "x", "aka": {}},
    )
    assert made.status_code == 200

    response = client.put(
        "/api/species/goodra",
        json={"name": "Goodra", "chrooked_id": "goodra", "abilities": {"hidden": "Tidal Force"}},
    )
    assert response.status_code == 200
