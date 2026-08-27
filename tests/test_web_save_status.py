"""#88 — the save-state row's data source.

Three things matter and nothing else: a healthy poll reports per-device
last-sync, a conflict file on disk is named back to its origin device, and an
unreachable Syncthing degrades to ``{"available": false}`` instead of a 500.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from chrooked_pokedex.web import save_sync

_THOR = "UMA523D-RCOYQHE-SDKYPK2-5CLFSMH-2T6O6O5-S2UQGSY-Y3V555Q-Y4DBWAY"
_MAC = "MFJ6AQQ-TNQDT4Y-YLGJWWF-X3W5CGU-WFPBNP3-4AUJIYW-XN3ZXDD-QXMMTA6"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SAVES_DIR", str(tmp_path))
    monkeypatch.setenv("SYNCTHING_DEVICES", f"thor={_THOR},macbook={_MAC}")
    monkeypatch.setenv("SYNCTHING_FOLDER_ID", "rejuv-saves")
    monkeypatch.setenv("SYNCTHING_API_KEY", "test-key")
    return tmp_path


def _fake_poll(thor_ago_s: int, mac_ago_s: int | None):
    now = datetime.now(timezone.utc)

    def poll(folder, devices):
        assert folder == "rejuv-saves"
        rows = []
        for name, ago in (("thor", thor_ago_s), ("macbook", mac_ago_s)):
            seen = None if ago is None else (now - timedelta(seconds=ago))
            rows.append(
                {
                    "name": name,
                    "id": devices[name],
                    "completion": 100.0,
                    "last_seen": seen.isoformat() if seen else None,
                    "seconds_ago": ago,
                }
            )
        return rows

    return poll


def test_healthy_names_the_newest_device(env, monkeypatch):
    monkeypatch.setattr(save_sync, "_poll_syncthing", _fake_poll(720, 3600))

    status = save_sync.save_status()

    assert status["available"] is True
    assert status["newest"] == "thor"
    assert status["newest_seconds_ago"] == 720
    assert status["stale"] == []
    assert status["conflicts"] == []


def test_stale_device_is_flagged_only_when_another_synced(env, monkeypatch):
    monkeypatch.setattr(save_sync, "_poll_syncthing", _fake_poll(300, None))

    status = save_sync.save_status()

    assert status["stale"] == ["macbook"]


def test_conflict_file_is_named_back_to_its_device(env, monkeypatch):
    monkeypatch.setattr(save_sync, "_poll_syncthing", _fake_poll(60, 120))
    name = f"Game.sync-conflict-20260827-101500-{_THOR[:7]}.rxdata"
    (env / name).write_text("save", encoding="utf-8")

    status = save_sync.save_status()

    assert status["conflicts"] == [{"file": name, "device": "thor"}]


def test_syncthing_unreachable_degrades_quietly(env, monkeypatch):
    monkeypatch.setattr(save_sync, "_poll_syncthing", lambda *_: None)

    status = save_sync.save_status()

    assert status == {"available": False, "folder": "rejuv-saves", "conflicts": []}


def test_missing_api_key_is_not_reachable(env, monkeypatch):
    monkeypatch.delenv("SYNCTHING_API_KEY")

    assert save_sync._poll_syncthing("rejuv-saves", {"thor": _THOR}) is None
