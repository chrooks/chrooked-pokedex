"""Unit tests for the handheld sync helper (src/chrooked_pokedex/sync.py).

Hermetic: every test patches ``subprocess.run``. Nothing here touches a network
or a real device.
"""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from chrooked_pokedex.sync import (
    SyncConfig,
    SyncResult,
    build_push_argv,
    build_save_pull_argv,
    run_save_backup,
    run_sync,
    sync_config_for_path,
)

pytestmark = pytest.mark.unit


DEVICE_GAME = "/storage/emulated/0/Pokemon Rejuvenation"


def _config(**overrides) -> SyncConfig:
    base = dict(
        host="ayn-thor",
        port=8022,
        user="u0_a132",
        dest=f"{DEVICE_GAME}/patch/",
        src_subdir="patch",
    )
    base.update(overrides)
    return SyncConfig(**base)


class _FakeRun:
    """Stands in for subprocess.run, recording argv and replaying an outcome."""

    def __init__(self, returncode=0, stdout="", stderr="", raises=None):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.raises = raises
        self.argv: list[str] | None = None

    def __call__(self, argv, **kwargs):
        self.argv = argv
        if self.raises is not None:
            raise self.raises
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, self.stderr)


# --- argv construction --------------------------------------------------------

def test_push_argv_escapes_spaces_in_the_remote_path():
    """The device path has a space; openrsync has no --protect-args."""
    argv = build_push_argv(Path("/Applications/Rejuvenation.app/Contents/Game"), _config())
    assert argv[-1] == r"u0_a132@ayn-thor:/storage/emulated/0/Pokemon\ Rejuvenation/patch/"


def test_push_argv_sends_folder_contents_not_the_folder():
    """A trailing slash on the source is the difference between patch/* and patch/patch/*."""
    argv = build_push_argv(Path("/games/rejuv"), _config())
    assert argv[-2] == "/games/rejuv/patch/"


def test_push_argv_mirrors_and_preserves_times_without_archive_mode():
    """-a would imply owner/group/perms, which Android's storage layer rejects."""
    argv = build_push_argv(Path("/games/rejuv"), _config())
    assert "-rtvz" in argv
    assert "--delete" in argv
    assert "-a" not in argv


def test_push_argv_transport_fails_fast_instead_of_prompting():
    argv = build_push_argv(Path("/games/rejuv"), _config())
    transport = argv[argv.index("-e") + 1]
    assert "-p 8022" in transport
    assert "BatchMode=yes" in transport
    assert "ConnectTimeout=" in transport


def test_save_pull_never_mirrors_deletions():
    """A save removed on the device must not disappear from the backup."""
    argv = build_save_pull_argv(_config(save_src=f"{DEVICE_GAME}/Save Data/"), Path("/backups/latest"))
    assert "--delete" not in argv
    assert argv[-2] == r"u0_a132@ayn-thor:/storage/emulated/0/Pokemon\ Rejuvenation/Save\ Data/"
    assert argv[-1] == "/backups/latest/"


def test_config_without_user_omits_the_at_sign():
    argv = build_push_argv(Path("/games/rejuv"), _config(user=None))
    assert argv[-1].startswith("ayn-thor:")


# --- outcome mapping ----------------------------------------------------------

def test_sync_reports_file_count_from_openrsync_output(tmp_path, monkeypatch):
    (tmp_path / "patch").mkdir()
    fake = _FakeRun(stdout="Transfer starting: 134 files\nMods/a.rb\nsent 100 bytes\n")
    monkeypatch.setattr(subprocess, "run", fake)
    result = run_sync(tmp_path, _config())
    assert result.ok
    assert result.files == 134
    assert "ayn-thor" in result.detail


def test_sync_counts_file_lines_when_rsync_prints_no_summary(tmp_path, monkeypatch):
    (tmp_path / "patch").mkdir()
    monkeypatch.setattr(subprocess, "run", _FakeRun(stdout="Mods/a.rb\nMods/b.rb\nsent 10 bytes\n"))
    assert run_sync(tmp_path, _config()).files == 2


def test_unreachable_device_names_the_fix(tmp_path, monkeypatch):
    """An asleep handheld must produce an instruction, not an errno."""
    (tmp_path / "patch").mkdir()
    monkeypatch.setattr(subprocess, "run", _FakeRun(returncode=255, stderr="ssh: connect to host ayn-thor port 8022: Connection refused"))
    result = run_sync(tmp_path, _config())
    assert not result.ok
    assert "sshd" in result.detail


def test_rejected_key_is_distinguished_from_an_absent_device(tmp_path, monkeypatch):
    (tmp_path / "patch").mkdir()
    monkeypatch.setattr(subprocess, "run", _FakeRun(returncode=255, stderr="Permission denied (publickey)."))
    result = run_sync(tmp_path, _config())
    assert not result.ok
    assert "key" in result.detail
    assert "sshd" not in result.detail


def test_timeout_is_reported_not_raised(tmp_path, monkeypatch):
    (tmp_path / "patch").mkdir()
    monkeypatch.setattr(subprocess, "run", _FakeRun(raises=subprocess.TimeoutExpired("rsync", 60)))
    result = run_sync(tmp_path, _config(), timeout=60)
    assert not result.ok
    assert "timed out" in result.detail


def test_missing_rsync_binary_is_reported_not_raised(tmp_path, monkeypatch):
    (tmp_path / "patch").mkdir()
    monkeypatch.setattr(subprocess, "run", _FakeRun(raises=FileNotFoundError()))
    result = run_sync(tmp_path, _config())
    assert not result.ok
    assert "rsync" in result.detail


def test_sync_refuses_when_patch_folder_is_absent(tmp_path, monkeypatch):
    """Syncing before an apply would mirror an empty folder and --delete the device."""
    called = _FakeRun()
    monkeypatch.setattr(subprocess, "run", called)
    result = run_sync(tmp_path, _config())
    assert not result.ok
    assert "apply" in result.detail
    assert called.argv is None, "must not invoke rsync when there is nothing to send"


# --- save backup --------------------------------------------------------------

def _seed_pull(tmp_path):
    """Make the fake rsync 'pull' a save file into the latest/ folder."""
    def fake(argv, **kwargs):
        Path(argv[-1]).mkdir(parents=True, exist_ok=True)
        (Path(argv[-1]) / "Game.rxdata").write_text("save")
        return subprocess.CompletedProcess(argv, 0, "Transfer starting: 1 files\n", "")
    return fake


def test_save_backup_writes_latest_and_a_dated_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _seed_pull(tmp_path))
    config = _config(save_src=f"{DEVICE_GAME}/Save Data/", save_backup_dir=str(tmp_path / "backups"))
    result = run_save_backup(config, today=date(2026, 8, 22))
    assert result.ok
    assert (tmp_path / "backups" / "latest" / "Game.rxdata").read_text() == "save"
    assert (tmp_path / "backups" / "2026-08-22" / "Game.rxdata").read_text() == "save"


def test_snapshots_are_hardlinks_so_history_is_nearly_free(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _seed_pull(tmp_path))
    config = _config(save_src=f"{DEVICE_GAME}/Save Data/", save_backup_dir=str(tmp_path / "backups"))
    run_save_backup(config, today=date(2026, 8, 22))
    latest = (tmp_path / "backups" / "latest" / "Game.rxdata").stat()
    snap = (tmp_path / "backups" / "2026-08-22" / "Game.rxdata").stat()
    assert latest.st_ino == snap.st_ino


def test_second_run_the_same_day_keeps_the_existing_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _seed_pull(tmp_path))
    config = _config(save_src=f"{DEVICE_GAME}/Save Data/", save_backup_dir=str(tmp_path / "backups"))
    run_save_backup(config, today=date(2026, 8, 22))
    (tmp_path / "backups" / "2026-08-22" / "marker").write_text("keep me")
    result = run_save_backup(config, today=date(2026, 8, 22))
    assert result.ok
    assert (tmp_path / "backups" / "2026-08-22" / "marker").exists()


def test_old_snapshots_are_pruned_and_recent_ones_survive(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _seed_pull(tmp_path))
    root = tmp_path / "backups"
    for name in ("2026-06-01", "2026-08-20", "not-a-date"):
        (root / name).mkdir(parents=True)
    config = _config(save_src=f"{DEVICE_GAME}/Save Data/", save_backup_dir=str(root))
    run_save_backup(config, today=date(2026, 8, 22))
    assert not (root / "2026-06-01").exists()
    assert (root / "2026-08-20").exists()
    assert (root / "not-a-date").exists(), "unrecognized folders are left alone"


def test_save_backup_failure_leaves_no_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _FakeRun(returncode=255, stderr="Connection refused"))
    config = _config(save_src=f"{DEVICE_GAME}/Save Data/", save_backup_dir=str(tmp_path / "backups"))
    result = run_save_backup(config, today=date(2026, 8, 22))
    assert not result.ok
    assert not (tmp_path / "backups" / "2026-08-22").exists()


def test_save_backup_without_config_is_refused_clearly(tmp_path, monkeypatch):
    called = _FakeRun()
    monkeypatch.setattr(subprocess, "run", called)
    result = run_save_backup(_config(), today=date(2026, 8, 22))
    assert not result.ok
    assert "not configured" in result.detail
    assert called.argv is None


# --- registry lookup ----------------------------------------------------------

def _write_targets(tmp_path, entries) -> Path:
    path = tmp_path / "targets.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def test_lookup_finds_the_sync_block_for_a_registered_target(tmp_path):
    targets = _write_targets(tmp_path, [
        {"engine": "rejuv", "path": "/games/rejuv", "sync": {"host": "ayn-thor", "port": 8022}},
    ])
    config = sync_config_for_path(targets, Path("/games/rejuv"))
    assert config is not None
    assert config.host == "ayn-thor"
    assert config.port == 8022


def test_lookup_ignores_targets_without_a_sync_block(tmp_path):
    targets = _write_targets(tmp_path, [{"engine": "rejuv", "path": "/games/rejuv"}])
    assert sync_config_for_path(targets, Path("/games/rejuv")) is None


def test_lookup_normalizes_paths_before_matching(tmp_path):
    targets = _write_targets(tmp_path, [
        {"path": "/games/rejuv", "sync": {"host": "ayn-thor"}},
    ])
    assert sync_config_for_path(targets, Path("/games/./rejuv/")) is not None


def test_lookup_survives_a_missing_or_corrupt_registry(tmp_path):
    assert sync_config_for_path(tmp_path / "absent.json", Path("/games/rejuv")) is None
    corrupt = tmp_path / "targets.json"
    corrupt.write_text("{not json", encoding="utf-8")
    assert sync_config_for_path(corrupt, Path("/games/rejuv")) is None


def test_config_round_trips_through_the_registry_shape():
    config = _config(save_src="/dev/Save Data/", save_backup_dir="~/Backups/rejuv-saves")
    assert SyncConfig.from_dict(config.to_dict()) == config


def test_config_requires_a_host():
    with pytest.raises(ValueError):
        SyncConfig.from_dict({"port": 8022})


def test_result_omits_absent_fields_when_serialized():
    assert SyncResult(ok=False, detail="nope").to_dict() == {"ok": False, "detail": "nope"}
