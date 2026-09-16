"""`/api/design/*/propose` (#103, M2) — hermetic over TestClient.

Reuses the M1 scaffold (goomy→sliggoo→goodra snapshot, sample ruleset,
NullLoreProvider). The fake provider answers by the schema it receives: the
packet schema gets canned packets, the learnset schema gets a skeleton-
conforming draft, so the pre-draft path runs for real.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_web_design import _SAMPLE, _SNAPSHOT  # noqa: E402

from chrooked_pokedex.model import Ruleset  # noqa: E402
from chrooked_pokedex.web import design_propose as dp  # noqa: E402
from chrooked_pokedex.web import dex as dexmod  # noqa: E402
from chrooked_pokedex.web import learnset_skeleton as skmod  # noqa: E402
from chrooked_pokedex.web import lore as loremod  # noqa: E402
from chrooked_pokedex.web.app import create_app  # noqa: E402

pytestmark = pytest.mark.unit

_QUEUE = "Goomy line, mirror Eevee BST\nVaporeon\n"
_GROUP_QUEUE = "Goomy line & Vaporeon together\n"

LINE_NAMES = ("Goomy", "Sliggoo", "Goodra", "Eevee", "Vaporeon")


def _packet(**over: Any) -> dict[str, Any]:
    base = {
        "profile": [{"stage": "Stage 1", "ecological_role": "wet cave", "fantastical": "slime"}],
        "axis": "a slow, sheltered gastropod",
        "inferred_types": ["Dragon"],
        "abilities": [
            {"name": "Gooey", "slot": "primary", "reason": "mucus", "pros": "p", "cons": "c"},
            {"name": "Sap Sipper", "slot": "hidden", "reason": "grazes", "pros": "p", "cons": "c"},
        ],
        "bench": [{"name": "Poison Heal", "reason": "r", "pros": "p", "cons": "c"}],
        "moves": [
            {"move": "Dragon Pulse", "role": "STAB", "reason": "r", "pays_off": ""},
            {"move": "Tackle", "role": "utility", "reason": "r", "pays_off": ""},
        ],
    }
    return {**base, **over}


class _SchemaFake:
    """Answers packet schemas with `packets`, learnset schemas with a skeleton draft."""

    def __init__(self, packets: list[dict[str, Any]], fail_learnset_for: str | None = None):
        self.packets = packets
        self.fail_learnset_for = fail_learnset_for
        self.calls: list[dict[str, Any]] = []
        self.ruleset_dir: Path | None = None

    def propose(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        props = kwargs["schema"]["properties"]
        if "packets" in props:
            n = props["packets"]["minItems"]
            if n == 1:
                # The prompt is blind, so the only tell is the stage count:
                # goodra has three stages, vaporeon two. Tag the axis so the
                # learnset call (which carries the direction) can tell too.
                cid = "goodra" if "Stage 3" in kwargs["user"] else "vaporeon"
                return {"packets": [{**self.packets[0], "axis": f"{self.packets[0]['axis']} [{cid}]"}]}
            return {"packets": self.packets[:n]}
        return self._learnset(kwargs["user"])

    def _learnset(self, user: str) -> dict[str, Any]:
        ruleset = Ruleset.load(self.ruleset_dir)
        pool = dexmod.build_move_pool(_SNAPSHOT, ruleset)
        abilities = dexmod.build_abilities(_SNAPSHOT, ruleset)
        cid = "vaporeon" if "[vaporeon]" in user else "goodra"
        if self.fail_learnset_for == cid:
            raise RuntimeError("boom")
        entry = dexmod.build_dex_entry(_SNAPSHOT, ruleset, cid)
        anchors = ["Dragon Pulse", "Tackle"]
        skeleton = skmod.build_skeleton(entry, abilities, pool, anchors=anchors)
        rows, used = [], set()
        for slot in skeleton["slots"]:
            pick = next((c for c in slot["candidates"] if c.casefold() not in used), slot["candidates"][0])
            if slot["level"] > 0:
                used.add(pick.casefold())
            rows.append({"level": slot["level"], "move": pick, "reasoning": "fills slot"})
        return {"draft": {"learnset": rows}, "rationale": {"learnset": "x"}, "alternatives": []}


def _make(tmp_path: Path, provider: _SchemaFake, queue: str) -> tuple[TestClient, Path]:
    ruleset_dir = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, ruleset_dir)
    (ruleset_dir / "QUEUE.md").write_text(queue, encoding="utf-8")
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    provider.ruleset_dir = ruleset_dir
    app = create_app(
        ruleset_dir=ruleset_dir, snapshot_path=snap, llm_provider=provider,
        lore_provider=loremod.NullLoreProvider(), design_dir=tmp_path / "design",
    )
    client = TestClient(app, raise_server_exceptions=False)
    client.post("/api/design/ingest")
    return client, ruleset_dir


def test_propose_all_from_queued(tmp_path: Path) -> None:
    fake = _SchemaFake([_packet()])
    client, _ = _make(tmp_path, fake, _QUEUE)

    resp = client.post("/api/design/propose")

    assert resp.status_code == 200 and sorted(resp.json()["started"]) == ["goodra", "vaporeon"]
    records = {r["id"]: r for r in client.get("/api/design").json()}
    assert {r["state"] for r in records.values()} == {"proposed"}
    assert {r["activity"] for r in records.values()} == {"ready"}
    goodra = records["goodra"]["packet"]
    assert goodra["abilities"][0]["name"] == "Gooey"
    assert goodra["current"]["types"] == ["Water", "Dragon"]  # the Ruleset's current kit
    assert goodra["current"]["bst"] > 0
    assert goodra["reference_stats"][0]["id"] == "eevee"
    assert goodra["draft_learnset"]["rows"]
    assert all({"level", "move"} <= set(r) for r in goodra["draft_learnset"]["rows"])
    # Two Port calls per record: one packet, one learnset.
    assert len(fake.calls) == 4
    packet_call = next(c for c in fake.calls if "packets" in c["schema"]["properties"])
    assert packet_call["system"] == dp.BLIND_RUBRIC
    assert "Excalibur | Steel" in packet_call["cached_context"]
    assert "[CUSTOM]" in packet_call["cached_context"]
    assert packet_call["max_tokens"] == dp.PROPOSE_MAX_TOKENS
    # A proposed record may be re-proposed (proposed -> proposing is a legal edge).
    assert client.post("/api/design/goodra/propose").status_code == 200


def test_group_yields_two_packets_from_one_call(tmp_path: Path) -> None:
    fake = _SchemaFake([_packet(axis="variant A"), _packet(axis="variant B")])
    client, _ = _make(tmp_path, fake, _GROUP_QUEUE)

    client.post("/api/design/propose")

    packet_calls = [c for c in fake.calls if "packets" in c["schema"]["properties"]]
    assert len(packet_calls) == 1
    assert packet_calls[0]["schema"]["properties"]["packets"]["minItems"] == 2
    assert "Variant A:" in packet_calls[0]["user"] and "Variant B:" in packet_calls[0]["user"]
    records = {r["id"]: r for r in client.get("/api/design").json()}
    assert records["goodra"]["packet"]["axis"] == "variant A"
    assert records["vaporeon"]["packet"]["axis"] == "variant B"
    assert {r["state"] for r in records.values()} == {"proposed"}


def test_hallucinated_ability_dropped_with_warning(tmp_path: Path) -> None:
    packet = _packet(abilities=[
        {"name": "Snow Cloak Plus", "slot": "primary", "reason": "r", "pros": "p", "cons": "c"},
        {"name": "gooey", "slot": "hidden", "reason": "r", "pros": "p", "cons": "c"},
    ])
    client, _ = _make(tmp_path, _SchemaFake([packet]), "Goomy line\n")

    client.post("/api/design/goodra/propose")

    got = client.get("/api/design/goodra").json()["packet"]
    assert [a["name"] for a in got["abilities"]] == ["Gooey"]  # canonical case
    assert any("Snow Cloak Plus" in w for w in got["warnings"])


def test_provider_error_isolates_one_record(tmp_path: Path) -> None:
    """A packet-call failure errors that record only."""
    fake = _SchemaFake([_packet()])
    client, _ = _make(tmp_path, fake, _QUEUE)
    calls = {"n": 0}
    original = fake.propose

    def flaky(**kw):
        if "packets" in kw["schema"]["properties"] and "Stage 3" not in kw["user"]:
            raise RuntimeError("boom")  # vaporeon's packet call only
        return original(**kw)

    fake.propose = flaky
    client.post("/api/design/propose")

    records = {r["id"]: r for r in client.get("/api/design").json()}
    assert records["goodra"]["state"] == "proposed"
    assert records["vaporeon"]["state"] == "error"
    assert records["vaporeon"]["activity"] == "error"
    assert "boom" in records["vaporeon"]["error"]
    # An errored record can be re-proposed.
    assert client.post("/api/design/vaporeon/propose").status_code == 200


def test_predraft_failure_keeps_the_packet(tmp_path: Path) -> None:
    """A learnset skeleton the model cannot fill (seen on the first real batch:
    Alakazam, Slurpuff) leaves the record proposed with a warning — the packet
    is the deliverable, the pre-draft a bonus that Realize rebuilds anyway."""
    fake = _SchemaFake([_packet()], fail_learnset_for="vaporeon")
    client, _ = _make(tmp_path, fake, _QUEUE)

    client.post("/api/design/propose")

    rec = client.get("/api/design/vaporeon").json()
    assert rec["state"] == "proposed"
    assert rec["packet"]["draft_learnset"] is None
    assert any(w.startswith("pre-draft skipped") for w in rec["packet"]["warnings"])


def test_group_call_scales_the_token_cap(tmp_path: Path) -> None:
    """Two packets in one call need twice the output budget (a pair truncated
    at the flat cap on the first real batch)."""
    fake = _SchemaFake([_packet(), _packet()])
    client, _ = _make(tmp_path, fake, "Goodra & Vaporeon lines\n")

    client.post("/api/design/propose")

    packet_calls = [c for c in fake.calls if "packets" in c["schema"]["properties"]]
    assert packet_calls[0]["max_tokens"] == dp.PROPOSE_MAX_TOKENS * 2


def test_prompt_is_blind(tmp_path: Path) -> None:
    fake = _SchemaFake([_packet()])
    client, _ = _make(tmp_path, fake, "Goomy line\n")

    client.post("/api/design/goodra/propose")

    packet_call = next(c for c in fake.calls if "packets" in c["schema"]["properties"])
    assert "Stage 1" in packet_call["user"] and "Stage 3" in packet_call["user"]
    for name in LINE_NAMES:
        assert name not in packet_call["user"]
        assert name not in packet_call["system"]
    assert "Dragon" not in packet_call["user"].split("Steer")[0]  # no typing leaks


def test_propose_from_confirmed_is_409(tmp_path: Path) -> None:
    client, _ = _make(tmp_path, _SchemaFake([_packet()]), "Goomy line\n")
    path = tmp_path / "design" / "goodra.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "state": "confirmed"}))

    assert client.post("/api/design/goodra/propose").status_code == 409


def test_build_pools_matches_pool_dump_shape(tmp_path: Path) -> None:
    ruleset = Ruleset.load(_SAMPLE)
    moves, abilities = dp.build_pools(_SNAPSHOT, ruleset)
    assert "Tackle | Normal | Physical | BP 40 | acc 100 | hit | \n" in moves
    assert "Excalibur | Steel | physical | BP 90" in moves and "[CUSTOM]" in moves
    assert "Poison Heal | Heals each turn instead of taking poison damage. [CUSTOM]\n" in abilities
    assert "Gooey | x\n" in abilities


def test_wants_custom_and_schema_flags() -> None:
    assert dp.wants_custom("give it a Custom ability")
    assert not dp.wants_custom("mirror Eevee BST")
    schema = dp.packet_schema(want_custom=True, want_stats=True)
    assert {"custom", "stats"} <= set(schema["properties"])
    assert "custom" not in dp.packet_schema(False, False)["properties"]
