"""DesignStore (#103 M1): JSON records, atomic saves, the state machine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chrooked_pokedex.web.design_store import (
    STATES,
    TRANSITIONS,
    DesignError,
    DesignRecord,
    DesignStore,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def store(tmp_path: Path) -> DesignStore:
    s = DesignStore(tmp_path / "design")
    s.save(DesignRecord(id="stoutland", line=["lillipup", "herdier", "stoutland"]))
    return s


def test_every_transition_target_is_a_state():
    for src, targets in TRANSITIONS.items():
        assert src in STATES
        assert targets <= set(STATES)


def test_save_writes_plan_shape_and_no_tmp_left(store: DesignStore, tmp_path: Path):
    path = tmp_path / "design" / "stoutland.json"
    data = json.loads(path.read_text())
    assert set(data) == {
        "id", "line", "forms", "group", "steer", "references", "state", "activity",
        "created", "updated", "packet", "decisions", "preview", "ship",
        "corrections", "proof", "error",
    }
    assert data["state"] == "queued" and data["activity"] == "idle"
    assert not list((tmp_path / "design").glob("*.tmp"))


def test_list_get_delete(store: DesignStore):
    assert [r.id for r in store.list()] == ["stoutland"]
    assert store.get("stoutland").line == ["lillipup", "herdier", "stoutland"]
    store.delete("stoutland")
    assert store.list() == []
    with pytest.raises(DesignError) as exc:
        store.get("stoutland")
    assert exc.value.status == 404


def test_list_on_missing_dir_is_empty(tmp_path: Path):
    assert DesignStore(tmp_path / "nope").list() == []


def test_legal_walk_through_the_happy_path(store: DesignStore):
    for to in ("proposing", "proposed", "decided", "realizing", "previewed", "confirmed", "shipped", "proven"):
        assert store.transition("stoutland", to).state == to


def test_illegal_edge_is_409(store: DesignStore):
    with pytest.raises(DesignError) as exc:
        store.transition("stoutland", "confirmed")
    assert exc.value.status == 409
    assert store.get("stoutland").state == "queued"


def test_error_is_reachable_and_recoverable(store: DesignStore):
    store.transition("stoutland", "proposing")
    rec = store.transition("stoutland", "error", error="boom", activity="error")
    assert rec.state == "error" and rec.error == "boom"
    back = store.transition("stoutland", "proposing")
    assert back.state == "proposing" and back.error is None


def test_transition_patches_and_stamps_updated(store: DesignStore):
    before = store.get("stoutland")
    rec = store.transition("stoutland", "proposing", activity="proposing")
    assert rec.activity == "proposing"
    assert rec.updated >= before.updated
    assert rec.created == before.created


def test_bad_id_is_rejected(store: DesignStore):
    with pytest.raises(DesignError) as exc:
        store.get("../etc")
    assert exc.value.status == 400
