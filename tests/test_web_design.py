"""`/api/design` routes (#103) — hermetic over TestClient.

M1 half: ingest from a queue file into records, idempotence, decisions
validation against the pools, confirm gating, delete. Later milestones append
their halves (propose, realize, ship, proof) to this file.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.web import lore as loremod
from chrooked_pokedex.web.app import create_app
from chrooked_pokedex.web.design_store import DesignRecord

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SAMPLE = _REPO_ROOT / "tests" / "fixtures" / "sample_ruleset"


def _move(cid: str, name: str, mtype: str, power: int) -> dict[str, Any]:
    return {
        "chrooked_id": cid, "name": name, "type": mtype, "category": "Physical",
        "power": power, "accuracy": 100, "pp": 20, "description": "x", "effect": "hit",
        "argument": None, "additional_effects": [], "flags": [], "priority": 0,
        "target": "selected", "aka": {},
    }


def _species(cid: str, name: str, dex: int, **extra: Any) -> dict[str, Any]:
    base = {
        "dex": dex, "chrooked_id": cid, "name": name, "types": ["Dragon"],
        "abilities": {"primary": "Sap Sipper", "secondary": None, "hidden": "Gooey"},
        "stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 60},
        "learnset": [{"level": 1, "move": "Tackle"}],
        "evolution": None, "evolves_into": [],
    }
    return {**base, **extra}


def _evo(to: str, name: str, dex: int) -> dict[str, Any]:
    return {"method": "Level", "method_detail": {"kind": "EVO_LEVEL", "param": "1"}, "to": to, "to_dex": dex, "to_name": name}


_SNAPSHOT = {
    "version": "1.11.2",
    "species": {
        "goomy": _species("goomy", "Goomy", 704, evolves_into=[_evo("sliggoo", "Sliggoo", 705)]),
        "sliggoo": _species(
            "sliggoo", "Sliggoo", 705,
            evolution={"from": "goomy", "from_name": "Goomy"},
            evolves_into=[_evo("goodra", "Goodra", 706)],
        ),
        "goodra": _species("goodra", "Goodra", 706, evolution={"from": "sliggoo", "from_name": "Sliggoo"}),
        "goodramega": _species("goodramega", "Goodra Mega", 706),
        "eevee": _species(
            "eevee", "Eevee", 133,
            evolves_into=[_evo("vaporeon", "Vaporeon", 134), _evo("jolteon", "Jolteon", 135)],
        ),
        "vaporeon": _species("vaporeon", "Vaporeon", 134, evolution={"from": "eevee"}),
        "jolteon": _species("jolteon", "Jolteon", 135, evolution={"from": "eevee"}),
    },
    "abilities": {
        "sap-sipper": {"chrooked_id": "sap-sipper", "name": "Sap Sipper", "description": "x", "aka": {}},
        "gooey": {"chrooked_id": "gooey", "name": "Gooey", "description": "x", "aka": {}},
    },
    "moves": {
        "tackle": _move("tackle", "Tackle", "Normal", 40),
        "dragon-pulse": _move("dragon-pulse", "Dragon Pulse", "Dragon", 85),
    },
    "type_chart": [
        {"attacker": "Water", "defender": "Dragon", "multiplier": 0.5},
        {"attacker": "Dragon", "defender": "Dragon", "multiplier": 2.0},
    ],
}

_QUEUE = """# design backlog
Goomy line, mirror Eevee BST
Eevee
Notamon
"""


class _FakeProvider:
    def __init__(self, result: dict[str, Any] | None = None) -> None:
        self.result = result or {}
        self.calls: list[dict[str, Any]] = []

    def propose(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.result


@pytest.fixture
def env(tmp_path: Path) -> tuple[TestClient, Path]:
    ruleset_dir = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, ruleset_dir)
    (ruleset_dir / "QUEUE.md").write_text(_QUEUE, encoding="utf-8")
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    app = create_app(
        ruleset_dir=ruleset_dir,
        snapshot_path=snap,
        llm_provider=_FakeProvider(),
        lore_provider=loremod.NullLoreProvider(),
        design_dir=tmp_path / "design",
    )
    return TestClient(app, raise_server_exceptions=False), tmp_path / "design"


def test_list_is_empty_before_ingest(env):
    client, _ = env
    assert client.get("/api/design").json() == []


def test_ingest_creates_records_and_reports_rejects(env):
    client, _ = env
    body = client.post("/api/design/ingest").json()
    assert body["created"] == ["goodra"]
    assert body["existing"] == []
    reasons = {u["row"]: u["reason"] for u in body["unresolved"]}
    assert "Vaporeon" in reasons["Eevee"] and "Jolteon" in reasons["Eevee"]
    assert "Notamon" in reasons

    rec = client.get("/api/design/goodra").json()
    assert rec["line"] == ["goomy", "sliggoo", "goodra"]
    assert rec["forms"] == ["goodramega"]
    assert rec["steer"] == "mirror Eevee BST"
    assert rec["references"] == ["eevee"]
    assert rec["state"] == "queued" and rec["activity"] == "idle"
    assert rec["group"] is None


def test_ingest_is_idempotent(env):
    client, _ = env
    client.post("/api/design/ingest")
    second = client.post("/api/design/ingest").json()
    assert second["created"] == [] and second["existing"] == ["goodra"]
    assert len(client.get("/api/design").json()) == 1


def test_missing_record_is_404(env):
    client, _ = env
    assert client.get("/api/design/nope").status_code == 404


def _force_state(design_dir: Path, state: str) -> None:
    path = design_dir / "goodra.json"
    data = json.loads(path.read_text())
    path.write_text(json.dumps({**data, "state": state}))


def test_decisions_reject_unknown_ability(env):
    client, design_dir = env
    client.post("/api/design/ingest")
    _force_state(design_dir, "proposed")
    resp = client.put("/api/design/goodra/decisions", json={"abilities": ["Snow Cloak Plus"]})
    assert resp.status_code == 422
    assert "Snow Cloak Plus" in resp.json()["detail"]
    assert client.get("/api/design/goodra").json()["decisions"] is None


def test_decisions_reject_unknown_anchor_and_custom_clash(env):
    client, design_dir = env
    client.post("/api/design/ingest")
    _force_state(design_dir, "proposed")
    resp = client.put("/api/design/goodra/decisions", json={"anchors": ["Nope Slam"]})
    assert resp.status_code == 422 and "Nope Slam" in resp.json()["detail"]
    resp = client.put(
        "/api/design/goodra/decisions",
        json={"custom": {"kind": "ability", "name": "Poison Heal", "mechanic": "x"}},
    )
    assert resp.status_code == 422 and "Poison Heal" in resp.json()["detail"]


def test_decisions_from_queued_is_409(env):
    client, _ = env
    client.post("/api/design/ingest")
    resp = client.put("/api/design/goodra/decisions", json={"abilities": ["Gooey"]})
    assert resp.status_code == 409


def test_decisions_written_from_proposed(env):
    client, design_dir = env
    client.post("/api/design/ingest")
    _force_state(design_dir, "proposed")
    body = {
        "typing": ["Dragon"],
        "abilities": ["Gooey", "Poison Heal"],
        "anchors": ["Dragon Pulse", "Excalibur"],
        "drop": ["Tackle"],
        "custom": {"kind": "move", "name": "Slime Wave", "mechanic": "x"},
        "stats": {"delta": {"atk": -5, "def": 5}},
        "notes": "gentle giant",
    }
    resp = client.put("/api/design/goodra/decisions?realize=false", json=body)
    assert resp.status_code == 200, resp.text
    rec = resp.json()
    assert rec["state"] == "decided"
    assert rec["decisions"]["abilities"] == ["Gooey", "Poison Heal"]
    assert rec["decisions"]["custom"]["written"] is False
    assert rec["decisions"]["skip_pre"] == []
    assert rec["decisions"]["typing"] == ["Dragon"]


def test_confirm_from_queued_is_409(env):
    client, _ = env
    client.post("/api/design/ingest")
    assert client.post("/api/design/goodra/confirm").status_code == 409


def test_confirm_from_previewed(env):
    client, design_dir = env
    client.post("/api/design/ingest")
    _force_state(design_dir, "previewed")
    resp = client.post("/api/design/goodra/confirm")
    assert resp.status_code == 200 and resp.json()["state"] == "confirmed"


def test_delete_removes_record_not_queue_row(env):
    client, design_dir = env
    client.post("/api/design/ingest")
    assert client.delete("/api/design/goodra").status_code == 200
    assert client.get("/api/design").json() == []
    assert client.delete("/api/design/goodra").status_code == 404
    assert "Goomy line" in (design_dir.parent / "ruleset" / "QUEUE.md").read_text()
    # A re-ingest recreates it from the untouched queue row.
    assert client.post("/api/design/ingest").json()["created"] == ["goodra"]


def test_record_dataclass_roundtrip():
    rec = DesignRecord(id="goodra", line=["goodra"])
    assert DesignRecord.from_dict({**rec.as_dict(), "extra": 1}) == rec


def test_pending_custom_may_be_anchored_and_written_must_exist(env):
    """A custom decided in the sitting is anchored before it exists; once the
    custom lane writes it, `written: true` demands it be in the pool."""
    client, design_dir = env
    client.post("/api/design/ingest")
    _force_state(design_dir, "proposed")
    body = {"anchors": ["Volley"],
            "custom": {"kind": "move", "name": "Volley", "mechanic": "x", "written": False}}
    resp = client.put("/api/design/goodra/decisions?realize=false", json=body)
    assert resp.status_code == 200, resp.text
    body["custom"]["written"] = True
    resp = client.put("/api/design/goodra/decisions?realize=false", json=body)
    assert resp.status_code == 422 and "not in the pool yet" in resp.json()["detail"]
