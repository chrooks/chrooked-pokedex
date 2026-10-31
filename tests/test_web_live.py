"""The companion live-state routes: the mod posts a blob, the view polls it."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.web.app import create_app
from chrooked_pokedex.web.live import mon_ids, normalize

pytestmark = pytest.mark.unit

_SAMPLE = Path(__file__).resolve().parent / "fixtures" / "sample_ruleset"
_SNAPSHOT = {"version": "1.11.2", "species": {}, "abilities": {}, "moves": {}, "type_chart": []}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    shutil.copytree(_SAMPLE, tmp_path / "ruleset")
    snap = tmp_path / "1.11.2.json"
    snap.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    return TestClient(create_app(ruleset_dir=tmp_path / "ruleset", snapshot_path=snap), raise_server_exceptions=False)


def test_mon_ids_follow_the_snapshot_rule() -> None:
    assert mon_ids("GOODRA", "", 0) == ("goodra", "goodra")
    assert mon_ids("GOODRA", "Normal Form", 0) == ("goodra", "goodra")
    assert mon_ids("GOODRA", "Normal Form", 1) == ("goodra", "goodra")
    assert mon_ids("GOLISOPOD", "Aevian Form", 1) == ("golisopod--aevianform", "golisopod")
    assert mon_ids(None, None, None) == ("", "")


def test_normalize_mints_ids_and_drops_junk() -> None:
    out = normalize({"scene": "battle", "party": [{"species": "ROTOM", "form": "Wash", "form_index": 3}, "x"], "foes": None})
    assert out["scene"] == "battle"
    assert out["party"] == [{"species": "ROTOM", "form": "Wash", "form_index": 3, "id": "rotom--wash", "base_id": "rotom"}]
    assert out["foes"] == []


def test_routes_round_trip(client: TestClient) -> None:
    assert client.get("/api/live/rejuv").json() == {"available": False, "engine": "rejuv"}
    posted = client.post("/api/live/rejuv", json={"scene": "overworld", "map": "Gearen City", "party": [{"species": "SWAMPERT", "form_index": 0}]})
    assert posted.status_code == 200
    got = client.get("/api/live/rejuv").json()
    assert got["available"] is True
    assert got["map"] == "Gearen City"
    assert got["party"][0]["id"] == "swampert"
    assert got["age_s"] >= 0
    assert client.get("/api/live/essentials").json()["available"] is False


def test_routes_reject_bad_input(client: TestClient) -> None:
    assert client.post("/api/live/gba", json={}).status_code == 404
    assert client.post("/api/live/rejuv", json=[1, 2]).status_code == 422
    assert client.post("/api/live/rejuv", json={"pad": "x" * 70_000}).status_code == 413
