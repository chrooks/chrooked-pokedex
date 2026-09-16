"""`/api/design` realize routes (#103, M4) — hermetic over TestClient.

Decisions → linted learnset + stats preview in a background task (TestClient
runs it inline), the work-ahead hook on PUT decisions, the pending-custom
409, corrections, drops, anchors, and the pre-evo stat scaling.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.model import Ruleset
from chrooked_pokedex.web import design_realize, learnset_skeleton
from chrooked_pokedex.web import lore as loremod
from chrooked_pokedex.web.app import create_app
from chrooked_pokedex.web.design_store import DesignRecord, DesignStore
from tests.test_web_design import _QUEUE, _SNAPSHOT

pytestmark = pytest.mark.unit

_SAMPLE = Path(__file__).resolve().parent / "fixtures" / "sample_ruleset"


class _SkeletonProvider:
    """Answers the learnset schema by filling the skeleton the server builds
    for the record under realize (read from the store at call time)."""

    def __init__(self, design_dir: Path, ruleset_dir: Path) -> None:
        self.design_dir, self.ruleset_dir = design_dir, ruleset_dir
        self.calls: list[dict[str, Any]] = []

    def propose(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        record = DesignStore(self.design_dir).get("goodra")
        inputs = design_realize.learnset_inputs(record, _SNAPSHOT, Ruleset.load(self.ruleset_dir))
        skeleton = learnset_skeleton.build_skeleton(
            inputs["entry"], inputs["abilities"], inputs["move_pool"],
            direction=inputs["direction"], anchors=inputs["anchors"],
        )
        rows, used = [], set()
        for slot in skeleton["slots"]:
            pick = next((c for c in slot["candidates"] if c.casefold() not in used), slot["candidates"][0])
            if slot["level"] > 0:
                used.add(pick.casefold())
            rows.append({"level": slot["level"], "move": pick, "reasoning": "fills slot"})
        return {"draft": {"learnset": rows}, "rationale": "canned", "alternatives": []}


@pytest.fixture
def env(tmp_path: Path) -> tuple[TestClient, Path, Path]:
    ruleset_dir = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, ruleset_dir)
    (ruleset_dir / "QUEUE.md").write_text(_QUEUE, encoding="utf-8")
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    design_dir = tmp_path / "design"
    app = create_app(
        ruleset_dir=ruleset_dir, snapshot_path=snap,
        llm_provider=_SkeletonProvider(design_dir, ruleset_dir),
        lore_provider=loremod.NullLoreProvider(), design_dir=design_dir,
    )
    client = TestClient(app, raise_server_exceptions=False)
    client.post("/api/design/ingest")
    _force_state(design_dir, "proposed")
    return client, design_dir, ruleset_dir


def _force_state(design_dir: Path, state: str) -> None:
    path = design_dir / "goodra.json"
    data = json.loads(path.read_text())
    path.write_text(json.dumps({**data, "state": state}))


_DECISIONS = {"abilities": ["Gooey"], "anchors": ["Dragon Pulse"], "drop": ["Tackle"], "notes": "gentle"}


def test_put_decisions_realizes_to_previewed(env):
    client, _, _ = env
    resp = client.put("/api/design/goodra/decisions", json=_DECISIONS)
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "realizing"
    rec = client.get("/api/design/goodra").json()
    assert rec["state"] == "previewed" and rec["activity"] == "ready", rec["error"]
    preview = rec["preview"]
    moves = [r["move"] for r in preview["learnset"]["rows"]]
    assert "Dragon Pulse" in moves  # anchor present
    assert "Tackle" not in moves  # drop honoured
    assert preview["abilities"] == ["Gooey"]
    assert preview["typing"] == ["Water", "Dragon"]  # the sample Ruleset overrides Goodra
    assert set(preview["stats"]) == {"goomy", "sliggoo", "goodra", "goodramega"}
    assert set(preview["learnset"]) == {"rows", "warnings", "lint"}


def test_put_decisions_with_realize_false_rests_at_decided(env):
    client, _, _ = env
    client.put("/api/design/goodra/decisions?realize=false", json=_DECISIONS)
    assert client.get("/api/design/goodra").json()["state"] == "decided"


def test_pending_custom_is_409_and_put_does_not_enqueue(env):
    client, _, _ = env
    body = {**_DECISIONS, "custom": {"kind": "ability", "name": "Slime Coat", "mechanic": "x"}}
    assert client.put("/api/design/goodra/decisions", json=body).json()["state"] == "decided"
    resp = client.post("/api/design/goodra/realize", json={})
    assert resp.status_code == 409
    assert "Slime Coat" in resp.json()["detail"] and "written" in resp.json()["detail"]
    # The custom lane finishes with written=true → realize runs.
    body["custom"]["written"] = True
    client.put("/api/design/goodra/decisions", json=body)
    assert client.get("/api/design/goodra").json()["state"] == "previewed"


def test_correction_rerun_appends_and_replaces_preview(env):
    client, _, _ = env
    client.put("/api/design/goodra/decisions", json=_DECISIONS)
    first = client.get("/api/design/goodra").json()["preview"]
    resp = client.post("/api/design/goodra/realize", json={"correction": "swap the capstone"})
    assert resp.status_code == 200, resp.text
    rec = client.get("/api/design/goodra").json()
    assert rec["state"] == "previewed"
    assert rec["corrections"] == ["swap the capstone"]
    assert rec["preview"] is not first or rec["preview"] == first
    assert "swap the capstone" in design_realize.build_direction(DesignRecord.from_dict(rec))


def test_realize_without_decisions_is_409(env):
    client, _, _ = env
    assert client.post("/api/design/goodra/realize").status_code == 409


def test_provider_failure_lands_in_error(env):
    client, design_dir, _ = env
    body = {**_DECISIONS, "anchors": []}
    client.put("/api/design/goodra/decisions?realize=false", json=body)
    _force_state(design_dir, "queued")  # realizing from queued is an illegal edge
    assert client.post("/api/design/goodra/realize").status_code == 409


# --- stats ------------------------------------------------------------------


def _record(**decisions: Any) -> DesignRecord:
    return DesignRecord(
        id="goodra", line=["goomy", "sliggoo", "goodra"], forms=["goodramega"],
        decisions={"abilities": [], "anchors": [], "drop": [], "skip_pre": [], **decisions},
    )


def _ruleset(tmp_path: Path) -> Ruleset:
    shutil.copytree(_SAMPLE, tmp_path / "rs")
    return Ruleset.load(tmp_path / "rs")


def test_stats_none_leaves_every_stage_unchanged(tmp_path):
    out = design_realize.stats_for_line(_record(stats=None), _SNAPSHOT, _ruleset(tmp_path))
    # Goodra carries a Ruleset override (spe 80); the pre-evos are canon.
    assert out["goodra"] == {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 80}
    assert out["sliggoo"] == {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 60}


def test_delta_scales_pre_evos_by_the_same_bst_delta(tmp_path):
    ruleset = _ruleset(tmp_path)
    before = design_realize.stats_for_line(_record(stats=None), _SNAPSHOT, ruleset)
    out = design_realize.stats_for_line(_record(stats={"delta": {"atk": 20}}), _SNAPSHOT, ruleset)
    assert out["goodra"]["atk"] == 120 and sum(out["goodra"].values()) == sum(before["goodra"].values()) + 20
    for cid in ("goomy", "sliggoo"):
        assert sum(out[cid].values()) == sum(before[cid].values()) + 20
        # shape follows the final: atk is now the second-highest stat after spd
        assert out[cid]["atk"] > out[cid]["spa"]
    assert out["goodramega"] == {**before["goodramega"], "atk": before["goodramega"]["atk"] + 20}


def test_full_spread_and_skip_pre(tmp_path):
    ruleset = _ruleset(tmp_path)
    before = design_realize.stats_for_line(_record(stats=None), _SNAPSHOT, ruleset)
    spread = {"hp": 100, "atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100}
    out = design_realize.stats_for_line(
        _record(stats=spread, skip_pre=["goomy"]), _SNAPSHOT, ruleset
    )
    assert out["goodra"] == spread
    assert out["goomy"] == before["goomy"]  # untouched
    delta = 600 - sum(before["goodra"].values())
    assert sum(out["sliggoo"].values()) == sum(before["sliggoo"].values()) + delta
    assert len({out["sliggoo"][k] for k in ("atk", "def", "spa", "spd", "spe")}) == 1  # flat like the final; HP takes the rounding
