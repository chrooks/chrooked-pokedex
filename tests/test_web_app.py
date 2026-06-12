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
