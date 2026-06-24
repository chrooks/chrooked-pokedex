"""Move-distribution engine + endpoint.

The engine (`chrooked_pokedex.distribute`) is pure and data-source-agnostic; the
endpoint (`POST /api/moves/{id}/distribute`) wires it over the merged dex with two
recipient modes (deterministic rule, LLM prompt). Covered here:

- engine: split/type selection, gap placement, evolution-line expansion,
  append-only row shape, evolved-at-1.
- endpoint: rule mode is deterministic (never calls the LLM), prompt mode routes
  through the Port and validates ids, plus the honest error paths.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex import distribute as engine
from chrooked_pokedex.web import llm as llmmod
from chrooked_pokedex.web.app import create_app

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SAMPLE = _REPO_ROOT / "tests" / "fixtures" / "sample_ruleset"


# --------------------------------------------------------------------------- #
# A small roster: one Ground physical line (sandshrew→sandslash), one off-type
# special mon (psyduck), plus a Ground line whose base is a different type only
# at the final stage is not needed here.
# --------------------------------------------------------------------------- #

def _sp(cid, name, dex, types, atk, spa, learnset, evolves_into=None):
    return {
        "chrooked_id": cid, "name": name, "dex": dex, "types": types,
        "abilities": {"primary": None, "secondary": None, "hidden": None},
        "stats": {"hp": 50, "atk": atk, "def": 50, "spa": spa, "spd": 50, "spe": 50},
        "learnset": learnset, "evolution": None,
        "evolves_into": evolves_into or [], "fully_evolved": not evolves_into,
    }


_SNAPSHOT: dict[str, Any] = {
    "version": "1.11.2",
    "species": {
        "sandshrew": _sp(
            "sandshrew", "Sandshrew", 27, ["Ground"], 75, 20,
            [{"level": 1, "move": "Scratch"}, {"level": 3, "move": "Sand Attack"}],
            [{"to": "sandslash", "to_name": "Sandslash", "method": "EVO_STONE",
              "method_detail": {"kind": "EVO_ITEM", "param": "Sun Stone"}}],
        ),
        "sandslash": _sp(
            "sandslash", "Sandslash", 28, ["Ground"], 100, 45,
            [{"level": 1, "move": "Scratch"}, {"level": 22, "move": "Slash"}],
        ),
        "psyduck": _sp(
            "psyduck", "Psyduck", 54, ["Water"], 52, 65,
            [{"level": 1, "move": "Scratch"}],
        ),
        "groudon": _sp(
            "groudon", "Groudon", 383, ["Ground"], 150, 100,
            [{"level": 1, "move": "Scratch"}],
        ),
    },
    "abilities": {},
    "moves": {
        "clodtoss": {
            "chrooked_id": "clodtoss", "name": "Clod Toss", "type": "Ground",
            "category": "Physical", "power": 50, "accuracy": 100, "pp": 25,
            "description": "Flings a clump of dirt and stone.", "effect": "hit",
            "argument": None, "additional_effects": [], "flags": [], "priority": 0,
            "target": "selected", "aka": {},
        },
    },
    "type_chart": [{"attacker": "Ground", "defender": "Fire", "multiplier": 2.0}],
}


class _FakeProvider:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def propose(self, *, system, cached_context, user, schema,
                max_tokens=llmmod.DEFAULT_MAX_TOKENS):
        self.calls.append({"user": user, "cached_context": cached_context})
        return self.result


class _ExplodingProvider:
    """Proves rule mode never touches the LLM: any call fails the test."""

    def propose(self, **_kwargs):  # noqa: ANN003
        raise AssertionError("rule mode must not call the LLM Port")


def _client(tmp_path: Path, provider: Any) -> TestClient:
    ruleset_dir = tmp_path / "ruleset"
    shutil.copytree(_SAMPLE, ruleset_dir)
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    app = create_app(ruleset_dir=ruleset_dir, snapshot_path=snap, llm_provider=provider)
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# Engine — pure unit
# ===========================================================================


def _records():
    out = {}
    for cid, v in _SNAPSHOT["species"].items():
        st = v["stats"]
        out[cid] = engine.SpeciesRecord(
            chrooked_id=cid, name=v["name"], dex=v["dex"], types=tuple(v["types"]),
            atk=st["atk"], spa=st["spa"],
            levels=tuple(m["level"] for m in v["learnset"]),
            bst=sum(st.values()),
            has_move=False,
        )
    return out


def test_best_level_picks_widest_gap_earliest() -> None:
    # moves at 1, 3, 22 → window 4..14. L12 and L13 both sit distance 9 from the
    # nearest neighbor; the earliest of the tie wins.
    assert engine.best_level([1, 3, 22], 4, 14) == 12


def test_best_level_never_collides_when_a_gap_exists() -> None:
    chosen = engine.best_level([4, 8, 12], 4, 14)
    assert chosen not in {4, 8, 12}


def test_parse_window_numbers_override_preset() -> None:
    assert engine.parse_window(levels=(9, 4)) == (4, 9)  # normalized
    assert engine.parse_window(preset="mid") == (16, 35)


def test_select_by_rule_filters_type_split_and_legendaries() -> None:
    ids = engine.select_by_rule(_records().values(), types={"Ground"}, split="physical")
    assert "sandshrew" in ids and "sandslash" in ids
    assert "psyduck" not in ids  # wrong type
    assert "groudon" not in ids  # legendary excluded by default


def test_select_by_rule_can_include_legendaries() -> None:
    ids = engine.select_by_rule(
        _records().values(), types={"Ground"}, split="physical",
        include_legendaries=True)
    assert "groudon" in ids


def test_distribute_expands_evolution_line_with_matched_flag() -> None:
    recs = _records()
    evo = engine.build_evolution_index(_SNAPSHOT["species"])
    rows = engine.distribute(recs, evo, matched_ids=["sandshrew"], window=(4, 14))
    by_id = {r.chrooked_id: r for r in rows}
    assert by_id["sandshrew"].matched is True
    assert by_id["sandslash"].matched is False  # pulled in via the line
    assert by_id["sandslash"].stage == "evolved"
    assert by_id["sandshrew"].stage == "first"


def test_distribute_evolved_at_1() -> None:
    recs = _records()
    evo = engine.build_evolution_index(_SNAPSHOT["species"])
    rows = engine.distribute(recs, evo, matched_ids=["sandshrew"], window=(4, 14),
                             evolved_at_1=True)
    assert {r.chrooked_id: r.level for r in rows}["sandslash"] == 1


def test_apply_breadth_keeps_top_by_bst() -> None:
    recs = _records()
    # sandslash (BST 345) outranks sandshrew (BST 295); signature keeps the one.
    kept = engine.apply_breadth(recs, ["sandshrew", "sandslash"], "signature")
    assert kept == ["sandslash"]


def test_apply_breadth_common_keeps_all() -> None:
    recs = _records()
    kept = engine.apply_breadth(recs, ["sandshrew", "sandslash"], "common")
    assert set(kept) == {"sandshrew", "sandslash"}


def test_best_level_bias_pushes_later() -> None:
    early = engine.best_level([1, 3, 22], 4, 14, 0.0)
    late = engine.best_level([1, 3, 22], 4, 14, 1.0)
    assert late > early  # rarer biases toward the back of the window


def test_distribute_no_evolution_expansion() -> None:
    recs = _records()
    evo = engine.build_evolution_index(_SNAPSHOT["species"])
    rows = engine.distribute(recs, evo, matched_ids=["sandshrew"], window=(4, 14),
                             include_evolutions=False)
    assert [r.chrooked_id for r in rows] == ["sandshrew"]


# ===========================================================================
# Endpoint
# ===========================================================================


def test_endpoint_rule_mode_is_deterministic(tmp_path: Path) -> None:
    client = _client(tmp_path, _ExplodingProvider())  # LLM must not be called
    resp = client.post("/api/moves/clodtoss/distribute",
                       json={"rule": {"types": ["Ground"], "split": "physical"},
                             "levels": [4, 14]})
    assert resp.status_code == 200
    body = resp.json()
    ids = {r["chrooked_id"] for r in body["rows"]}
    assert {"sandshrew", "sandslash"} <= ids
    assert "psyduck" not in ids and "groudon" not in ids
    assert body["window"] == [4, 14]


def test_endpoint_prompt_mode_routes_through_port(tmp_path: Path) -> None:
    provider = _FakeProvider({
        "species": ["psyduck", "not_real"],  # flat id list (new compact schema)
        "rationale": "things that can scratch",
    })
    client = _client(tmp_path, provider)
    resp = client.post("/api/moves/clodtoss/distribute",
                       json={"prompt": "anything that can scratch", "preset": "early"})
    assert resp.status_code == 200
    body = resp.json()
    assert provider.calls, "prompt mode should call the Port"
    ids = {r["chrooked_id"] for r in body["rows"]}
    assert "psyduck" in ids
    assert any("not_real" in w for w in body["warnings"])  # unknown id dropped
    assert body["rationale"] == "things that can scratch"


def test_endpoint_combines_rule_and_prompt(tmp_path: Path) -> None:
    # Rule (Ground physical) pre-filters the pool; the prompt refines within it.
    provider = _FakeProvider({"species": ["sandshrew"], "rationale": "digs"})
    client = _client(tmp_path, provider)
    resp = client.post("/api/moves/clodtoss/distribute", json={
        "rule": {"types": ["Ground"], "split": "physical"},
        "prompt": "burrowers", "include_evolutions": False})
    assert resp.status_code == 200
    assert provider.calls, "a prompt must route through the Port"
    # The roster handed to the LLM was pre-filtered to the rule — no Water psyduck.
    roster = provider.calls[0]["cached_context"]
    assert "sandshrew" in roster and "psyduck" not in roster
    assert {r["chrooked_id"] for r in resp.json()["rows"]} == {"sandshrew"}


def test_endpoint_unknown_move_404(tmp_path: Path) -> None:
    resp = _client(tmp_path, _ExplodingProvider()).post(
        "/api/moves/nope/distribute", json={"rule": {"types": ["Ground"]}})
    assert resp.status_code == 404


def test_endpoint_requires_rule_or_prompt(tmp_path: Path) -> None:
    resp = _client(tmp_path, _ExplodingProvider()).post(
        "/api/moves/clodtoss/distribute", json={"levels": [4, 14]})
    assert resp.status_code == 422


def test_endpoint_rarity_narrows_preset(tmp_path: Path) -> None:
    client = _client(tmp_path, _ExplodingProvider())
    common = client.post("/api/moves/clodtoss/distribute", json={
        "rule": {"types": ["Ground"], "split": "physical"},
        "include_evolutions": False, "rarity": "common"}).json()
    signature = client.post("/api/moves/clodtoss/distribute", json={
        "rule": {"types": ["Ground"], "split": "physical"},
        "include_evolutions": False, "rarity": "signature"}).json()
    assert len(signature["rows"]) < len(common["rows"])
    # The kept signature pick is the highest-BST Ground physical (sandslash).
    assert {r["chrooked_id"] for r in signature["rows"]} == {"sandslash"}


def test_endpoint_bad_rarity_422(tmp_path: Path) -> None:
    resp = _client(tmp_path, _ExplodingProvider()).post(
        "/api/moves/clodtoss/distribute",
        json={"rule": {"types": ["Ground"]}, "rarity": "mythic"})
    assert resp.status_code == 422


def test_endpoint_bad_split_422(tmp_path: Path) -> None:
    resp = _client(tmp_path, _ExplodingProvider()).post(
        "/api/moves/clodtoss/distribute",
        json={"rule": {"types": ["Ground"], "split": "sideways"}})
    assert resp.status_code == 422


# ===========================================================================
# Bulk apply endpoint
# ===========================================================================


def test_apply_writes_appendonly(tmp_path: Path) -> None:
    client = _client(tmp_path, _ExplodingProvider())
    resp = client.post("/api/moves/clodtoss/distribute/apply",
                       json={"rows": [{"chrooked_id": "sandshrew", "level": 7}]})
    assert resp.status_code == 200
    assert resp.json()["applied"] == ["sandshrew"]
    # The written Override keeps the base learnset AND adds Clod Toss at 7.
    ov = client.get("/api/species/sandshrew").json()
    moves = {m["move"]: m["level"] for m in ov["learnset"]}
    assert moves["Clod Toss"] == 7
    assert "Scratch" in moves and "Sand Attack" in moves  # nothing dropped


def test_apply_relevels_in_place(tmp_path: Path) -> None:
    client = _client(tmp_path, _ExplodingProvider())
    client.post("/api/moves/clodtoss/distribute/apply",
                json={"rows": [{"chrooked_id": "sandshrew", "level": 7}]})
    client.post("/api/moves/clodtoss/distribute/apply",
                json={"rows": [{"chrooked_id": "sandshrew", "level": 9}]})
    ov = client.get("/api/species/sandshrew").json()
    clod = [m for m in ov["learnset"] if m["move"] == "Clod Toss"]
    assert len(clod) == 1 and clod[0]["level"] == 9  # re-levelled, not duplicated


def test_apply_is_one_request_for_many_species(tmp_path: Path) -> None:
    client = _client(tmp_path, _ExplodingProvider())
    rows = [{"chrooked_id": c, "level": 5} for c in ("sandshrew", "sandslash", "psyduck")]
    resp = client.post("/api/moves/clodtoss/distribute/apply", json={"rows": rows})
    assert resp.status_code == 200
    assert set(resp.json()["applied"]) == {"sandshrew", "sandslash", "psyduck"}


def test_apply_bad_rows_land_in_failed(tmp_path: Path) -> None:
    client = _client(tmp_path, _ExplodingProvider())
    resp = client.post("/api/moves/clodtoss/distribute/apply", json={"rows": [
        {"chrooked_id": "sandshrew", "level": 7},
        {"chrooked_id": "not_real", "level": 7},
        {"chrooked_id": "psyduck", "level": 999},
    ]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] == ["sandshrew"]
    failed_ids = {f["chrooked_id"] for f in body["failed"]}
    assert failed_ids == {"not_real", "psyduck"}


def test_apply_unknown_move_404(tmp_path: Path) -> None:
    resp = _client(tmp_path, _ExplodingProvider()).post(
        "/api/moves/nope/distribute/apply",
        json={"rows": [{"chrooked_id": "sandshrew", "level": 7}]})
    assert resp.status_code == 404


def test_apply_empty_rows_422(tmp_path: Path) -> None:
    resp = _client(tmp_path, _ExplodingProvider()).post(
        "/api/moves/clodtoss/distribute/apply", json={"rows": []})
    assert resp.status_code == 422
