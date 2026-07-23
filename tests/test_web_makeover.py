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
    },
    "moves": {},
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
def test_design_log_requires_direction(ruleset_dir: Path, tmp_path: Path) -> None:
    client = _client(ruleset_dir, tmp_path)
    log_path = ruleset_dir / "DESIGN-LOG.md"
    before = log_path.read_text(encoding="utf-8") if log_path.exists() else None

    response = client.post("/api/design-log", json={"line": "Goodra line"})

    assert response.status_code == 422
    # Nothing was written on the reject.
    after = log_path.read_text(encoding="utf-8") if log_path.exists() else None
    assert after == before


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
