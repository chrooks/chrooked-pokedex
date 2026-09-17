"""`/api/design/ship` and `/proof` (#103, M5) — hermetic over TestClient.

Apply and read-back are monkeypatched (module attribute and `app.state` Seam);
the Ruleset writes are real and reload through `Ruleset.load`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.web import design_ship
from chrooked_pokedex.web import lore as loremod
from chrooked_pokedex.web import targets as targetsmod
from chrooked_pokedex.web.app import create_app
from chrooked_pokedex.web.design_store import DesignRecord, DesignStore

from test_web_design import _SNAPSHOT, _FakeProvider

pytestmark = pytest.mark.unit

_SAMPLE = Path(__file__).resolve().parent / "fixtures" / "sample_ruleset"
_QUEUE = "# backlog\nGoomy line, mirror Eevee BST\nGoodra & Jolteon\nEevee\n"
_ROWS = [{"level": 0, "move": "Dragon Pulse"}, {"level": 5, "move": "Tackle"}]
_STATS = {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 80}
_DECISIONS = {
    "typing": ["Dragon"], "abilities": ["Gooey", "Poison Heal", "Sap Sipper"],
    "anchors": [], "drop": [], "custom": None, "stats": None, "skip_pre": [],
    "notes": "gentle giant",
}
_PREVIEW = {"learnset": {"rows": _ROWS}, "stats": {"goodra": _STATS}}


def _record(cid: str, line: list[str], state: str = "confirmed", **extra: Any) -> DesignRecord:
    defaults = dict(decisions=_DECISIONS, preview=_PREVIEW, packet={"axis": "slow wall"})
    return DesignRecord(id=cid, line=line, state=state, **{**defaults, **extra})


@pytest.fixture
def env(tmp_path: Path, monkeypatch) -> SimpleNamespace:
    ruleset_dir = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, ruleset_dir)
    (ruleset_dir / "QUEUE.md").write_text(_QUEUE, encoding="utf-8")
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    app = create_app(
        ruleset_dir=ruleset_dir, snapshot_path=snap, llm_provider=_FakeProvider(),
        lore_provider=loremod.NullLoreProvider(), design_dir=tmp_path / "design",
    )
    target = targetsmod.Target(id="rejuv", label="Rejuv", path=str(tmp_path / "game"), engine="essentials")
    app.state.targets_registry = SimpleNamespace(get=lambda tid: target)
    app.state.read_back_ids = lambda target, ids: {
        "ok": True, "ok_count": len(ids), "total": len(ids), "species": [],
    }
    applies: list[Any] = []
    report = {"md": "| status | category | chrooked_id | symbol | reason |\n"}

    def fake_apply(target, effective, state, force, ledger_dir=None, ruleset_dir=None):
        applies.append(effective)
        return {"applied": 3, "partial": 0, "blocked": 0, "report_md": report["md"]}

    monkeypatch.setattr(design_ship.targetsmod, "apply_target", fake_apply)
    return SimpleNamespace(
        client=TestClient(app, raise_server_exceptions=False), app=app, store=app.state.design_store,
        ruleset_dir=ruleset_dir, applies=applies, report=report, snapshot=_SNAPSHOT,
    )


# --- line_plan ------------------------------------------------------------- #


def test_line_plan_rows_per_stage():
    rec = _record("goodra", ["goomy", "sliggoo", "goodra"], forms=["goodramega"])
    plan = design_ship.line_plan(rec, _DECISIONS, _PREVIEW)
    assert plan["goodra"] == _ROWS
    assert plan["goodramega"] == _ROWS  # forms mirror the final, L0 kept
    assert plan["goomy"] == plan["sliggoo"] == [{"level": 5, "move": "Tackle"}]


def test_line_plan_honours_skip_pre():
    rec = _record("goodra", ["goomy", "sliggoo", "goodra"])
    plan = design_ship.line_plan(rec, {**_DECISIONS, "skip_pre": ["goomy"]}, _PREVIEW)
    assert set(plan) == {"goodra", "sliggoo"}


# --- write_line ------------------------------------------------------------ #


def test_write_line_writes_yaml_that_reloads(env):
    rec = _record("goodra", ["goomy", "sliggoo", "goodra"], forms=["goodramega"])
    ctx = SimpleNamespace(ruleset_dir=env.ruleset_dir)
    ruleset = Ruleset.load(env.ruleset_dir)
    written = design_ship.write_line(rec, ctx, env.snapshot, ruleset)
    assert set(written) == {"goodra", "goodramega", "goomy", "sliggoo"}
    reloaded = Ruleset.load(env.ruleset_dir)
    goodra, goomy, mega = reloaded.species["goodra"], reloaded.species["goomy"], reloaded.species["goodramega"]
    assert [(m.level, m.move) for m in goodra.learnset] == [(0, "Dragon Pulse"), (5, "Tackle")]
    assert [(m.level, m.move) for m in goomy.learnset] == [(5, "Tackle")]
    assert goodra.abilities.primary == "Gooey" and goomy.abilities.hidden == "Sap Sipper"
    assert mega.abilities is None  # forms keep their own abilities
    assert goodra.types == ("Dragon",) and goomy.types == ("Dragon",)
    assert goodra.stats == _STATS and goomy.stats is None
    assert goodra.aka.get("pokeemerald") == "SPECIES_GOODRA"  # merged over the stored file


# --- ship ------------------------------------------------------------------ #


def test_ship_writes_applies_once_reads_back_logs_and_drops_queue_row(env):
    env.store.save(_record("goodra", ["goomy", "sliggoo", "goodra"], forms=["goodramega"], corrections=["add Tackle"]))
    resp = env.client.post("/api/design/ship", json={"target_id": "rejuv"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["goodra"]["state"] == "shipped"
    assert body["goodra"]["apply"] == {"applied": 3, "partial": 0, "blocked": 0}
    assert body["goodra"]["readback"]["ok"] is True and body["goodra"]["bad_rows"] == []
    assert len(env.applies) == 1
    log = (env.ruleset_dir / "DESIGN-LOG.md").read_text()
    assert "— Goodra" in log and "gentle giant; slow wall" in log and "add Tackle" in log
    assert body["goodra"]["log_section"] in log
    rec = env.store.get("goodra")
    assert rec.state == "shipped" and rec.ship["log_section"] == body["goodra"]["log_section"]
    queue = (env.ruleset_dir / "QUEUE.md").read_text()
    assert "Goomy line" not in queue and "Goodra & Jolteon" in queue and "Eevee" in queue


def test_ship_isolates_a_blocked_record(env):
    env.store.save(_record("goodra", ["goomy", "sliggoo", "goodra"]))
    env.store.save(_record("jolteon", ["jolteon"]))
    env.report["md"] += "| blocked | species | jolteon |  | no such symbol |\n"
    body = env.client.post("/api/design/ship", json={"target_id": "rejuv"}).json()
    assert body["goodra"]["state"] == "shipped"
    assert body["jolteon"]["state"] == "error" and "jolteon" in body["jolteon"]["bad_rows"][0]
    assert env.store.get("jolteon").state == "error"
    assert len(env.applies) == 1
    assert "Goodra & Jolteon" in (env.ruleset_dir / "QUEUE.md").read_text()


def test_ship_errors_on_readback_mismatch_and_write_failure(env):
    env.store.save(_record("goodra", ["goomy", "sliggoo", "goodra"]))
    bad_preview = {"learnset": {"rows": [{"level": 1, "move": "Nope Slam"}]}}
    env.store.save(_record("jolteon", ["jolteon"], preview=bad_preview))
    env.app.state.read_back_ids = lambda target, ids: {
        "ok": False, "ok_count": 0, "total": 1, "species": [{"chrooked_id": ids[0], "ok": False}],
    }
    body = env.client.post("/api/design/ship", json={"target_id": "rejuv"}).json()
    assert body["jolteon"]["state"] == "error" and "Nope Slam" in body["jolteon"]["error"]
    assert body["goodra"]["state"] == "error" and body["goodra"]["readback"]["diff"]
    assert not (env.ruleset_dir / "DESIGN-LOG.md").exists()


def test_ship_refuses_an_unconfirmed_id(env):
    env.store.save(_record("goodra", ["goomy", "sliggoo", "goodra"], state="previewed"))
    resp = env.client.post("/api/design/ship", json={"target_id": "rejuv", "ids": ["goodra"]})
    assert resp.status_code == 409 and "goodra" in resp.json()["detail"]
    assert env.client.post("/api/design/ship", json={"target_id": "rejuv"}).json() == {}
    assert env.client.post("/api/design/ship", json={"target_id": "rejuv", "ids": ["nope"]}).status_code == 404
    assert env.client.post("/api/design/ship", json={}).status_code == 422


# --- remove_queue_rows ------------------------------------------------------- #


def test_grouped_queue_row_stays_until_every_member_ships(tmp_path):
    queue = tmp_path / "QUEUE.md"
    queue.write_text(_QUEUE, encoding="utf-8")
    assert design_ship.remove_queue_rows(queue, {"goodra"}, _SNAPSHOT) == ["Goomy line, mirror Eevee BST"]
    assert queue.read_text() == "# backlog\nGoodra & Jolteon\nEevee\n"
    assert design_ship.remove_queue_rows(queue, {"goodra", "jolteon"}, _SNAPSHOT) == ["Goodra & Jolteon"]
    assert queue.read_text() == "# backlog\nEevee\n"
    assert design_ship.remove_queue_rows(queue, {"goodra"}, _SNAPSHOT) == []


# --- proof ------------------------------------------------------------------- #


def test_proof_transitions(env):
    env.store.save(_record("goodra", ["goodra"], state="shipped", steer="wall"))
    resp = env.client.post("/api/design/goodra/proof", json={"result": "proven", "note": "looks right"})
    assert resp.status_code == 200 and resp.json()["state"] == "proven"
    assert resp.json()["proof"] == {"result": "proven", "note": "looks right"}

    env.store.save(_record("goodra", ["goodra"], state="shipped", steer="wall"))
    resp = env.client.post("/api/design/goodra/proof", json={"result": "problem", "note": "no Tackle in game"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "queued" and resp.json()["steer"] == "wall; no Tackle in game"

    assert env.client.post("/api/design/goodra/proof", json={"result": "proven"}).status_code == 409
    assert env.client.post("/api/design/goodra/proof", json={"result": "maybe"}).status_code == 422


def test_montext_readback_matches_moveset_abilities_and_types(tmp_path):
    from chrooked_pokedex.web import design_ship as ds
    (tmp_path / "patch" / "Definitions").mkdir(parents=True)
    (tmp_path / "patch" / "Definitions" / "montext.rb").write_text(
        'if MONHASH.dig(:KINGLER, "Normal Form")\n'
        '  MONHASH[:KINGLER]["Normal Form"][:Type1] = :WATER\n'
        '  MONHASH[:KINGLER]["Normal Form"][:Type2] = :STEEL\n'
        '  MONHASH[:KINGLER]["Normal Form"][:Abilities][0] = :SHEERFORCE\n'
        '  MONHASH[:KINGLER]["Normal Form"][:Abilities][1] = :SERRATEDJAW\n'
        '  MONHASH[:KINGLER]["Normal Form"][:HiddenAbility] = :HYPERCUTTER\n'
        '  MONHASH[:KINGLER]["Normal Form"][:Moveset] = [[0, :PILEDRIVER], [8, :CLAMP], [14, :AQUAJET]]\n'
        'else\n  puts "skip"\nend\n', encoding="utf-8")
    exp = [{"id": "kingler", "name": "Kingler", "rows": [(0, "Pile Driver"), (8, "Clamp"), (14, "Aqua Jet")],
            "abilities": {"primary": "Sheer Force", "secondary": "Serrated Jaw", "hidden": "Hyper Cutter"},
            "types": ["Water", "Steel"]}]
    out = ds.montext_readback(tmp_path, exp)
    assert out["ok"] and out["ok_count"] == out["total"] == 6
    exp[0]["rows"][1] = (9, "Clamp")
    assert not ds.montext_readback(tmp_path, exp)["ok"]
