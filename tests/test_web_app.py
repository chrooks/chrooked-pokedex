"""Milestone 0 — the FastAPI surface.

`web/app.create_app` mounts the API over a snapshot file and a Ruleset folder.
These tests drive it through Starlette's TestClient against the in-repo
`sample_ruleset` and a tiny written snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
            "learnset": [{"level": 1, "move": "Tackle"}],
        },
    },
    # Base moves so canon /api/moves is the FULL base ⊕ Ruleset list.
    # `excalibur` is also owned by the sample Ruleset; the base entry below differs
    # so the merge flags it (overridden). `ember` is base-only (unflagged).
    "moves": {
        "ember": {
            "chrooked_id": "ember",
            "name": "Ember",
            "aka": {"pokeemerald": "MOVE_EMBER"},
            "type": "Fire",
            "category": "special",
            "power": 40,
            "accuracy": 100,
            "pp": 25,
            "description": "A weak fire attack.",
            "effect": "hit",
            "argument": None,
            "additional_effects": [],
            "flags": [],
            "priority": 0,
            "target": "selected",
        },
        "excalibur": {
            "chrooked_id": "excalibur",
            "name": "Excalibur",
            "aka": {"pokeemerald": "MOVE_EXCALIBUR"},
            "type": "Normal",
            "category": "physical",
            "power": 50,
            "accuracy": 95,
            "pp": 15,
            "description": "A base blade strike.",
            "effect": "hit",
            "argument": None,
            "additional_effects": [],
            "flags": [],
            "priority": 0,
            "target": "selected",
        },
    },
    # Base abilities so canon /api/abilities is the FULL base ⊕ Ruleset list.
    # `poisonheal` is also owned by the sample Ruleset (an overridden ability);
    # `overgrow` is base-only (unflagged).
    "abilities": {
        "overgrow": {
            "chrooked_id": "overgrow",
            "name": "Overgrow",
            "description": "Ups Grass moves in a pinch.",
            "aka": {"pokeemerald": "ABILITY_OVERGROW"},
        },
        "poisonheal": {
            "chrooked_id": "poisonheal",
            "name": "Poison Heal",
            "description": "A base description the Ruleset replaces.",
            "aka": {"pokeemerald": "ABILITY_POISON_HEAL"},
        },
    },
    "type_chart": [],
}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    snap_path = tmp_path / "1.11.2.json"
    snap_path.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    app = create_app(ruleset_dir=_SAMPLE, snapshot_path=snap_path)
    return TestClient(app)


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dex_returns_503_when_snapshot_missing(tmp_path: Path) -> None:
    app = create_app(ruleset_dir=_SAMPLE, snapshot_path=tmp_path / "absent.json")
    response = TestClient(app, raise_server_exceptions=False).get("/api/dex")
    assert response.status_code == 503
    assert "absent.json" in response.json()["detail"]


def test_dex_returns_merged_entries(client: TestClient) -> None:
    response = client.get("/api/dex")
    assert response.status_code == 200
    entries = response.json()
    assert isinstance(entries, list)
    goodra = next(e for e in entries if e["chrooked_id"] == "goodra")
    assert goodra["types"] == ["Water", "Dragon"]
    assert "types" in goodra["overridden_fields"]
    assert "abilities" in goodra["overridden_fields"]


def test_single_dex_entry_returns_merged_species(client: TestClient) -> None:
    response = client.get("/api/dex/goodra")
    assert response.status_code == 200
    goodra = response.json()
    assert goodra["chrooked_id"] == "goodra"
    assert goodra["types"] == ["Water", "Dragon"]
    assert goodra["stats"]["spe"] == 80


def test_single_dex_entry_404_for_unknown_id(client: TestClient) -> None:
    response = client.get("/api/dex/missingno")
    assert response.status_code == 404


def test_moves_endpoint_returns_full_base_merged_with_ruleset(
    client: TestClient,
) -> None:
    # ac2: canon moves is the FULL base ⊕ Ruleset list, not the sparse Ruleset-only
    # list. The base-only move is present and unflagged; the Ruleset-owned one is
    # flagged (overridden) with a base→now diff.
    response = client.get("/api/moves")
    assert response.status_code == 200
    moves = response.json()
    ids = {m["chrooked_id"] for m in moves}
    assert {"ember", "excalibur"} <= ids
    assert len(moves) >= 2  # exceeds the Ruleset-owned count (1 ruleset move)
    ember = next(m for m in moves if m["chrooked_id"] == "ember")
    assert ember["overridden_fields"] == []  # base-only, unflagged
    excalibur = next(m for m in moves if m["chrooked_id"] == "excalibur")
    # the Ruleset def (Steel) replaces the base (Normal) -> flagged
    assert excalibur["type"] == "Steel"
    assert "type" in excalibur["overridden_fields"]
    assert excalibur["base"]["type"] == "Normal"


def test_moves_endpoint_503_when_snapshot_missing(tmp_path: Path) -> None:
    # ac2: moves is now a merge endpoint (like /api/dex), so a missing base
    # snapshot is a 503 with an actionable message.
    app = create_app(ruleset_dir=_SAMPLE, snapshot_path=tmp_path / "absent.json")
    response = TestClient(app, raise_server_exceptions=False).get("/api/moves")
    assert response.status_code == 503


def test_abilities_endpoint_returns_full_base_merged_with_ruleset(
    client: TestClient,
) -> None:
    # ac2: canon abilities is the FULL base ⊕ Ruleset list, not the sparse
    # Ruleset-only list. The base-only ability is present and unflagged; the
    # Ruleset-owned one is flagged (overridden).
    response = client.get("/api/abilities")
    assert response.status_code == 200
    abilities = response.json()
    ids = {a["chrooked_id"] for a in abilities}
    # Both the base-only and the Ruleset-touched ability are present.
    assert {"overgrow", "poisonheal"} <= ids
    # Count exceeds the Ruleset-owned count (here 2 base >= 1 ruleset ability).
    assert len(abilities) >= 2
    overgrow = next(a for a in abilities if a["chrooked_id"] == "overgrow")
    assert overgrow["overridden_fields"] == []  # base-only, unflagged
    poisonheal = next(a for a in abilities if a["chrooked_id"] == "poisonheal")
    assert "description" in poisonheal["overridden_fields"]  # Ruleset edited it


def test_abilities_endpoint_503_when_snapshot_missing(tmp_path: Path) -> None:
    # ac2: abilities is now a merge endpoint (like /api/dex), so a missing base
    # snapshot is a 503 with an actionable message.
    app = create_app(ruleset_dir=_SAMPLE, snapshot_path=tmp_path / "absent.json")
    response = TestClient(app, raise_server_exceptions=False).get("/api/abilities")
    assert response.status_code == 503


def test_type_chart_endpoint_lists_overrides(client: TestClient) -> None:
    response = client.get("/api/type-chart")
    assert response.status_code == 200
    assert {"attacker": "Flying", "defender": "Ice", "multiplier": 0.5} in response.json()


def test_behaviors_endpoint_lists_specs(client: TestClient) -> None:
    response = client.get("/api/behaviors")
    assert response.status_code == 200
    excalibur = next(b for b in response.json() if b["chrooked_id"] == "excalibur")
    assert excalibur["applies_to"] == "move"


def test_collection_endpoints_work_without_snapshot(tmp_path: Path) -> None:
    # The Ruleset-owned collections don't need the base snapshot, so a missing
    # snapshot must not 503 them (only the base-merging routes — /api/dex*, and
    # since these slices /api/abilities and /api/moves — read the snapshot).
    app = create_app(ruleset_dir=_SAMPLE, snapshot_path=tmp_path / "absent.json")
    client = TestClient(app, raise_server_exceptions=False)
    for path in ("/api/type-chart", "/api/behaviors"):
        assert client.get(path).status_code == 200, path


def test_dex_returns_503_when_snapshot_is_wrong_shape(tmp_path: Path) -> None:
    # Valid JSON but missing the "species" key must 503, not crash with a 500.
    snap_path = tmp_path / "wrong.json"
    snap_path.write_text(json.dumps({"version": "1.11.2"}), encoding="utf-8")
    app = create_app(ruleset_dir=_SAMPLE, snapshot_path=snap_path)
    response = TestClient(app, raise_server_exceptions=False).get("/api/dex")
    assert response.status_code == 503
    assert "species" in response.json()["detail"]


def test_collection_returns_503_when_ruleset_is_corrupt(tmp_path: Path) -> None:
    # A malformed YAML file in the Ruleset folder must surface as an actionable
    # 503, never an unhandled parser error (500).
    bad_ruleset = tmp_path / "ruleset"
    (bad_ruleset / "behaviors").mkdir(parents=True)
    (bad_ruleset / "behaviors" / "broken.yaml").write_text(
        "name: [unterminated", encoding="utf-8"
    )
    # Use a Ruleset-only route (/api/behaviors) so the assertion isolates the
    # corrupt-Ruleset path — /api/moves now loads the snapshot first, which would
    # 503 on the snapshot before ever reaching the Ruleset load.
    app = create_app(ruleset_dir=bad_ruleset, snapshot_path=tmp_path / "absent.json")
    response = TestClient(app, raise_server_exceptions=False).get("/api/behaviors")
    assert response.status_code == 503
    assert "Ruleset" in response.json()["detail"]
