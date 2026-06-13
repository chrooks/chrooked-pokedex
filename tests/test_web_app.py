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
    "moves": {},
    "abilities": {},
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


def test_moves_endpoint_lists_owned_moves(client: TestClient) -> None:
    response = client.get("/api/moves")
    assert response.status_code == 200
    moves = response.json()
    excalibur = next(m for m in moves if m["chrooked_id"] == "excalibur")
    assert excalibur["type"] == "Steel"
    assert excalibur["category"] == "physical"


def test_abilities_endpoint_lists_owned_abilities(client: TestClient) -> None:
    response = client.get("/api/abilities")
    assert response.status_code == 200
    assert any(a["chrooked_id"] == "poisonheal" for a in response.json())


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
    # snapshot must not 503 them (only /api/dex* merges onto the base).
    app = create_app(ruleset_dir=_SAMPLE, snapshot_path=tmp_path / "absent.json")
    client = TestClient(app, raise_server_exceptions=False)
    for path in ("/api/moves", "/api/abilities", "/api/type-chart", "/api/behaviors"):
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
    (bad_ruleset / "moves").mkdir(parents=True)
    (bad_ruleset / "moves" / "broken.yaml").write_text(
        "name: [unterminated", encoding="utf-8"
    )
    app = create_app(ruleset_dir=bad_ruleset, snapshot_path=tmp_path / "absent.json")
    response = TestClient(app, raise_server_exceptions=False).get("/api/moves")
    assert response.status_code == 503
    assert "Ruleset" in response.json()["detail"]
