"""Blind design for Target-original forms — Rejuv's Aevian lines (#112).

The design pipeline resolved queue rows against the base snapshot only, which
has never heard of an Aevian form, so `Aevian Golisopod` came back "no species
name recognised". The design snapshot now carries every registered Rejuv
Target's ORIGINAL forms (`--` ids no canon id bridges to): an Aevian row queues
like a canon line, and its mega rides with it. Canon re-slugs
(`absol--megaform`) stay out — canon already holds them as `absolmega`.

The Rejuv snapshot builder is monkeypatched (no Ruby, no game folder).
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chrooked_pokedex.model.ruleset import Ruleset
from chrooked_pokedex.web import design_queue as q
from chrooked_pokedex.web import targets as targetsmod
from chrooked_pokedex.web.app import create_app

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SAMPLE = _REPO_ROOT / "tests" / "fixtures" / "sample_ruleset"


def _species(cid: str, name: str, **extra: Any) -> dict[str, Any]:
    return {
        "dex": 286, "chrooked_id": cid, "name": name, "types": ["Grass"],
        "abilities": {"primary": "Effect Spore", "secondary": None, "hidden": None},
        "stats": {"hp": 60, "atk": 130, "def": 80, "spa": 60, "spd": 60, "spe": 70},
        "learnset": [{"level": 1, "move": "Tackle"}],
        "evolution": None, "evolves_into": [], "fully_evolved": True,
        **extra,
    }


def _edge(to: str, name: str) -> list[dict[str, Any]]:
    return [{"to": to, "to_name": name, "to_dex": 286, "method": "Level 23",
             "method_detail": {"kind": "EVO_LEVEL", "param": "23"}}]


def _from(cid: str, name: str) -> dict[str, Any]:
    return {"from": cid, "from_name": name, "from_dex": 285, "method": "Level 23",
            "method_detail": {"kind": "EVO_LEVEL", "param": "23"}}


_CANON = {
    "version": "1.11.2",
    "species": {
        "shroomish": _species("shroomish", "Shroomish", evolves_into=_edge("breloom", "Breloom"),
                              fully_evolved=False),
        "breloom": _species("breloom", "Breloom", evolution=_from("shroomish", "Shroomish")),
        "absol": _species("absol", "Absol"),
        "absolmega": _species("absolmega", "Absol Mega"),
    },
    "abilities": {
        "effectspore": {"chrooked_id": "effectspore", "name": "Effect Spore",
                        "description": "Contact may poison.", "aka": {}},
        "technician": {"chrooked_id": "technician", "name": "Technician",
                       "description": "Powers up weak moves.", "aka": {}},
    },
    "moves": {},
    "type_chart": [{"attacker": "Grass", "defender": "Ghost", "multiplier": 1.0}],
}

# Rejuv's view: canon entries, a canon re-slug, and the Aevian line + its mega.
# Abilities are raw engine symbols here, as the real Rejuv snapshot keeps them.
_TARGET = {
    "version": "rejuv",
    "species": {
        **copy.deepcopy(_CANON["species"]),
        "absol--megaform": _species("absol--megaform", "Absol (Mega Form)", form="Mega Form"),
        "shroomish--aevianform": _species(
            "shroomish--aevianform", "Shroomish (Aevian Form)", form="Aevian Form",
            evolves_into=_edge("breloom--aevianform", "Breloom (Aevian Form)"), fully_evolved=False,
        ),
        "breloom--aevianform": _species(
            "breloom--aevianform", "Breloom (Aevian Form)", form="Aevian Form",
            types=["Grass", "Electric"],
            abilities={"primary": "TECHNICIAN", "secondary": None, "hidden": None},
            evolution=_from("shroomish--aevianform", "Shroomish (Aevian Form)"),
            genus="Shock Mushroom", dex_entry="It stores lightning in its cap.",
        ),
        "breloom--aevianmegaform": _species(
            "breloom--aevianmegaform", "Breloom (Aevian Mega Form)", form="Aevian Mega Form",
        ),
    },
    "abilities": {}, "moves": {}, "type_chart": [],
}


def _design_snapshot() -> dict[str, Any]:
    originals = targetsmod.original_forms(_TARGET, _CANON, Ruleset())
    return {**_CANON, "species": {**_CANON["species"], **originals}}


# --- the original-forms filter --------------------------------------------- #


def test_original_forms_skip_canon_reslugs_and_relabel_abilities():
    originals = targetsmod.original_forms(_TARGET, _CANON, Ruleset())
    assert set(originals) == {
        "shroomish--aevianform", "breloom--aevianform", "breloom--aevianmegaform",
    }
    # Engine symbol -> the canon display name the design pools validate against.
    assert originals["breloom--aevianform"]["abilities"]["primary"] == "Technician"
    assert originals["breloom--aevianform"]["dex_entry"] == "It stores lightning in its cap."


# --- the queue grammar ----------------------------------------------------- #


def test_aevian_prefix_resolves_the_line_and_its_mega():
    snapshot = _design_snapshot()
    names = q.display_names(snapshot)
    (row,) = q.parse_rows("Aevian Breloom, keep the spark\n", names)
    assert row.subjects == ("Breloom (Aevian Form)",)
    assert row.steer == "keep the spark"
    (resolved,) = q.resolve_row(row, snapshot, names)
    assert resolved.id == "breloom--aevianform"
    assert resolved.line == ["shroomish--aevianform", "breloom--aevianform"]
    assert resolved.forms == ["breloom--aevianmegaform"]


def test_canon_final_never_claims_an_original_forms_mega():
    snapshot = _design_snapshot()
    names = q.display_names(snapshot)
    (row,) = q.parse_rows("Breloom\n", names)
    (resolved,) = q.resolve_row(row, snapshot, names)
    assert resolved.line == ["shroomish", "breloom"]
    assert resolved.forms == []


# --- the router wiring ----------------------------------------------------- #


@pytest.fixture
def make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def build(queue: str, snapshot_builder) -> TestClient:
        ruleset_dir = tmp_path / "ruleset"
        shutil.copytree(_SAMPLE, ruleset_dir)
        (ruleset_dir / "QUEUE.md").write_text(queue, encoding="utf-8")
        snap_path = tmp_path / "snap.json"
        snap_path.write_text(json.dumps(_CANON), encoding="utf-8")
        fork = tmp_path / "fork"
        fork.mkdir()
        targets_path = tmp_path / "targets.json"
        targets_path.write_text(json.dumps(
            [{"id": "t-rejuv", "label": "Rejuvenation", "path": str(fork), "engine": "rejuv"}]
        ), encoding="utf-8")
        monkeypatch.setattr(targetsmod.snapmod_rejuv, "build_snapshot_rejuv", snapshot_builder)
        app = create_app(
            ruleset_dir=ruleset_dir, snapshot_path=snap_path,
            targets_path=targets_path, design_dir=tmp_path / "design",
        )
        return TestClient(app, raise_server_exceptions=False)

    return build


def test_ingest_queues_an_aevian_row(make_client):
    http = make_client("Aevian Breloom\n", lambda path: copy.deepcopy(_TARGET))
    body = http.post("/api/design/ingest").json()
    assert body["created"] == ["breloom--aevianform"]
    assert "warnings" not in body
    record = http.get("/api/design/breloom--aevianform").json()
    assert record["line"] == ["shroomish--aevianform", "breloom--aevianform"]
    assert record["forms"] == ["breloom--aevianmegaform"]


def test_ingest_names_the_reason_when_the_target_cannot_snapshot(make_client):
    def no_ruby(path):
        raise targetsmod.snapmod_rejuv.RejuvSnapshotError(
            "ruby is required to snapshot a Rejuvenation target and was not found on PATH."
        )

    http = make_client("Aevian Breloom\nBreloom\n", no_ruby)
    body = http.post("/api/design/ingest").json()
    # Canon still queues; the Aevian row is unresolved WITH the real reason
    # beside it, not a bare "no species name" that reads as a typo.
    assert body["created"] == ["breloom"]
    assert [u["row"] for u in body["unresolved"]] == ["Aevian Breloom"]
    assert any("ruby is required" in w for w in body["warnings"])
