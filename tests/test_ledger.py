"""Unit tests for the Change Ledger core (append/read/diff_fields)."""

from pathlib import Path

import pytest

from chrooked_pokedex import ledger


@pytest.mark.unit
def test_diff_fields_reports_only_changes() -> None:
    before = {"types": ["Bug", "Normal"], "name": "Kricketune", "stats": {"hp": 50}}
    after = {"types": ["Bug", "Fighting"], "name": "Kricketune", "stats": {"hp": 50}}

    diff = ledger.diff_fields(before, after)

    assert diff == {"types": {"from": ["Bug", "Normal"], "to": ["Bug", "Fighting"]}}


@pytest.mark.unit
def test_diff_fields_create_and_delete() -> None:
    assert ledger.diff_fields(None, {"types": ["Bug"]}) == {
        "types": {"from": None, "to": ["Bug"]}
    }
    assert ledger.diff_fields({"types": ["Bug"]}, None) == {
        "types": {"from": ["Bug"], "to": None}
    }


@pytest.mark.unit
def test_append_then_read_is_newest_first(tmp_path: Path) -> None:
    ledger.append(tmp_path, {"scope": "base", "kind": "species", "chrooked_id": "a", "source": "web-edit"})
    ledger.append(tmp_path, {"scope": "base", "kind": "species", "chrooked_id": "b", "source": "web-edit"})

    entries = ledger.read(tmp_path)

    assert [e["chrooked_id"] for e in entries] == ["b", "a"]
    assert (tmp_path / "ledger.ndjson").exists()


@pytest.mark.unit
def test_read_filters_by_scope_kind_chrooked_id(tmp_path: Path) -> None:
    ledger.append(tmp_path, {"scope": "base", "kind": "species", "chrooked_id": "a"})
    ledger.append(tmp_path, {"scope": "target:africanvs", "kind": "species", "chrooked_id": "b"})
    ledger.append(tmp_path, {"scope": "target:africanvs", "kind": "apply", "chrooked_id": None})

    assert len(ledger.read(tmp_path, scope="target:africanvs")) == 2
    assert len(ledger.read(tmp_path, kind="apply")) == 1
    assert len(ledger.read(tmp_path, chrooked_id="a")) == 1
    assert len(ledger.read(tmp_path, limit=1)) == 1


@pytest.mark.unit
def test_read_missing_ledger_is_empty(tmp_path: Path) -> None:
    assert ledger.read(tmp_path) == []
