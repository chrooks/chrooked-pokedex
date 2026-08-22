"""Mirror an applied ``patch/`` folder to a handheld, and pull its saves back.

The Rejuvenation Ruleset is applied to a build copy of the game on this machine;
the copy that gets *played* lives on an Android handheld running Kirin (an
mkxp-z build for Android).  Everything an apply writes lands in one folder --
``<target>/patch/`` -- so mirroring that one folder moves the whole mod.

Two directions, deliberately asymmetric:

  * ``run_sync``        pushes ``patch/`` to the device and mirrors deletions,
    because a stale mod file left behind is a real failure mode (it loads and
    breaks the game).  Anything hand-placed on the device that is not in the
    Ruleset is therefore destroyed -- harvest it into ``references/`` first.
  * ``run_save_backup`` pulls ``Save Data/`` back and NEVER deletes, because
    the save is the one artifact here that cannot be regenerated.

Both shell out to ``rsync`` rather than using a library: delta transfer,
mirror semantics, and mtime preservation are one battle-tested binary away.

mtime preservation (``-t``) is load-bearing in the push direction.  The game
recompiles a data category at boot only when its Definitions file is *newer*
than the compiled ``.dat`` (see ``appliers/rejuv/init_script.py``).  If the
device filesystem refuses to set times the file simply lands newer and the
device recompiles -- slower, still correct.

Note: macOS ships openrsync, not GNU rsync, so ``--protect-args``/``-s`` is
unavailable and remote paths containing spaces are backslash-escaped by hand
(``_remote_spec``).  The real remote path here has a space in it.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Fail fast rather than hang: an asleep handheld should report in seconds.
CONNECT_TIMEOUT_SECONDS = 5
# rsync's own stall timeout, well inside the caller's process timeout.
IO_TIMEOUT_SECONDS = 15
DEFAULT_TIMEOUT_SECONDS = 60.0
# Dated save snapshots older than this are pruned.
SAVE_RETENTION_DAYS = 30

_TRANSFER_COUNT = re.compile(r"Transfer starting:\s*(\d+)\s*file", re.IGNORECASE)
# Lines rsync prints that are not file names.
_SUMMARY_PREFIXES = ("sent ", "total size", "Transfer starting", "building file list", "created directory")


@dataclass(frozen=True)
class SyncConfig:
    """Where a Target's files go on the handheld, and where its saves come back.

    ``dest`` and ``save_src`` are absolute paths *on the device*; the save
    fields are optional so a Target can mirror its patch without opting into
    save handling.
    """

    host: str
    port: int = 22
    user: str | None = None
    dest: str = ""
    src_subdir: str = "patch"
    save_src: str | None = None
    save_backup_dir: str | None = None
    desktop_save_dir: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SyncConfig":
        """Build from a ``targets.json`` sync block, ignoring unknown keys."""
        if not raw.get("host"):
            raise ValueError("sync config needs a 'host'")
        return cls(
            host=str(raw["host"]),
            port=int(raw.get("port", 22)),
            user=(str(raw["user"]) if raw.get("user") else None),
            dest=str(raw.get("dest", "")),
            src_subdir=str(raw.get("src_subdir", "patch")).strip("/"),
            save_src=(str(raw["save_src"]) if raw.get("save_src") else None),
            save_backup_dir=(str(raw["save_backup_dir"]) if raw.get("save_backup_dir") else None),
            desktop_save_dir=(str(raw["desktop_save_dir"]) if raw.get("desktop_save_dir") else None),
        )

    def to_dict(self) -> dict[str, Any]:
        """Round-trip back to the ``targets.json`` shape, omitting empty keys."""
        out: dict[str, Any] = {"host": self.host, "port": self.port, "dest": self.dest,
                               "src_subdir": self.src_subdir}
        for key in ("user", "save_src", "save_backup_dir", "desktop_save_dir"):
            value = getattr(self, key)
            if value:
                out[key] = value
        return out


@dataclass(frozen=True)
class SyncResult:
    """Outcome of one transfer. ``detail`` is written to be shown to a human."""

    ok: bool
    detail: str
    files: int | None = None
    seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok, "detail": self.detail}
        if self.files is not None:
            out["files"] = self.files
        if self.seconds is not None:
            out["seconds"] = self.seconds
        return out


def _remote_spec(config: SyncConfig, path: str) -> str:
    """``user@host:/escaped/path`` — spaces escaped for the remote shell.

    rsync hands the remote path to a shell on the far side, so a literal space
    would split the argument.  openrsync has no ``--protect-args``, so the
    backslashes go in here.
    """
    prefix = f"{config.user}@{config.host}" if config.user else config.host
    return f"{prefix}:{path.replace(' ', chr(92) + ' ')}"


def _ssh_transport(config: SyncConfig) -> str:
    """The ``-e`` argument. BatchMode means a missing key fails, never hangs."""
    return (
        f"ssh -p {config.port}"
        f" -o ConnectTimeout={CONNECT_TIMEOUT_SECONDS}"
        f" -o BatchMode=yes"
    )


def _count_files(stdout: str) -> int | None:
    """Files transferred, from whichever dialect of rsync produced the output."""
    match = _TRANSFER_COUNT.search(stdout)
    if match:
        return int(match.group(1))
    lines = [
        line for line in stdout.splitlines()
        if line.strip() and not line.startswith(_SUMMARY_PREFIXES)
    ]
    return len(lines) or None


def _explain_failure(returncode: int, stderr: str, config: SyncConfig) -> str:
    """Turn an rsync exit into something that names the fix, not the errno."""
    text = stderr.strip()
    lowered = text.lower()
    unreachable = (
        "connection refused", "connection timed out", "no route to host",
        "could not resolve", "name or service not known", "connection closed",
        "operation timed out",
    )
    if any(term in lowered for term in unreachable):
        return (
            f"{config.host} unreachable — is the device awake and on the network? "
            f"If it rebooted, open Termux and run: sshd"
        )
    if "permission denied" in lowered or "publickey" in lowered:
        return f"{config.host} refused the key — check ~/.ssh/config and authorized_keys on the device"
    if "host key verification failed" in lowered:
        return f"{config.host} host key is not trusted — verify it, then add it to ~/.ssh/known_hosts"
    last = text.splitlines()[-1] if text else f"rsync exited {returncode}"
    return f"rsync failed ({returncode}): {last}"


def _run_rsync(argv: list[str], timeout: float, config: SyncConfig, success: str) -> SyncResult:
    """Run one rsync and map its outcome onto a SyncResult. Never raises."""
    started = time.monotonic()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return SyncResult(False, "rsync is not installed on this machine")
    except subprocess.TimeoutExpired:
        return SyncResult(
            False,
            f"timed out after {timeout:.0f}s — {config.host} may have dropped off the network",
        )
    elapsed = round(time.monotonic() - started, 1)
    if proc.returncode != 0:
        return SyncResult(False, _explain_failure(proc.returncode, proc.stderr, config), seconds=elapsed)
    return SyncResult(True, success, files=_count_files(proc.stdout), seconds=elapsed)


def build_push_argv(fork: Path, config: SyncConfig) -> list[str]:
    """The exact rsync command that mirrors ``<fork>/<src_subdir>/`` to the device.

    Trailing slashes matter: ``patch/`` means *the contents of* patch.  ``-a``
    is deliberately not used — it implies owner/group/perm preservation, which
    Android's storage layer rejects.
    """
    source = f"{fork / config.src_subdir}/"
    return [
        "rsync", "-rtvz", "--delete", f"--timeout={IO_TIMEOUT_SECONDS}",
        "-e", _ssh_transport(config),
        source, _remote_spec(config, config.dest),
    ]


def build_save_pull_argv(config: SyncConfig, destination: Path) -> list[str]:
    """Pull the device's saves into ``destination``. No ``--delete``, ever.

    A save that vanishes on the device must not vanish from the backup — that
    is the whole point of holding a copy.
    """
    return [
        "rsync", "-rtvz", f"--timeout={IO_TIMEOUT_SECONDS}",
        "-e", _ssh_transport(config),
        _remote_spec(config, config.save_src or ""), f"{destination}/",
    ]


def run_sync(fork: Path, config: SyncConfig, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> SyncResult:
    """Mirror ``<fork>/patch/`` onto the device. Returns; never raises."""
    source = fork / config.src_subdir
    if not source.is_dir():
        return SyncResult(False, f"nothing to sync — {source} does not exist (run apply first)")
    if not config.dest:
        return SyncResult(False, "sync config has no 'dest' path on the device")
    return _run_rsync(
        build_push_argv(fork, config), timeout, config,
        success=f"mirrored {config.src_subdir}/ to {config.host}",
    )


def run_save_backup(
    config: SyncConfig,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    today: date | None = None,
) -> SyncResult:
    """Pull the device's saves to ``save_backup_dir`` and keep dated snapshots.

    Layout::

        <save_backup_dir>/latest/         mirror of the device, refreshed each run
        <save_backup_dir>/2026-08-22/     hardlinked snapshot, one per day

    Snapshots are hardlinks, so thirty days of a 34 MB save folder costs ~34 MB
    plus whatever actually changed.  History matters because a pull that lands
    while the game is mid-save can capture a torn file; a single mirror would
    overwrite the last good copy with it.
    """
    if not config.save_src or not config.save_backup_dir:
        return SyncResult(False, "sync config has no 'save_src'/'save_backup_dir' — save backup not configured")
    root = Path(config.save_backup_dir).expanduser()
    latest = root / "latest"
    try:
        latest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return SyncResult(False, f"cannot create backup folder {root}: {exc}")

    result = _run_rsync(
        build_save_pull_argv(config, latest), timeout, config,
        success=f"pulled saves from {config.host}",
    )
    if not result.ok:
        return result

    stamp = (today or date.today()).isoformat()
    snapshot = root / stamp
    if not snapshot.exists():
        try:
            shutil.copytree(latest, snapshot, copy_function=os.link)
        except OSError as exc:
            # The pull succeeded; a snapshot failure must not report data loss.
            return replace(result, detail=f"{result.detail} (snapshot {stamp} failed: {exc})")
    pruned = _prune_snapshots(root, today or date.today())
    detail = result.detail + f" → {root}"
    if pruned:
        detail += f"; pruned {pruned} snapshot(s) older than {SAVE_RETENTION_DAYS}d"
    return replace(result, detail=detail)


def _prune_snapshots(root: Path, today: date) -> int:
    """Delete dated snapshot folders older than the retention window."""
    cutoff = today - timedelta(days=SAVE_RETENTION_DAYS)
    removed = 0
    for child in root.iterdir():
        if not child.is_dir() or child.name == "latest":
            continue
        try:
            stamp = date.fromisoformat(child.name)
        except ValueError:
            continue  # not a dated snapshot — leave it alone
        if stamp < cutoff:
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    return removed


def sync_config_for_path(targets_json: Path, fork: Path) -> SyncConfig | None:
    """Find the sync block of the registered Target living at ``fork``.

    Reads ``targets.json`` directly so the CLI never has to import the web
    layer.  Returns None when the file is missing, unreadable, has no matching
    Target, or that Target has no sync block — a sync is opt-in per Target.
    """
    try:
        raw = json.loads(targets_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, list):
        return None
    wanted = _resolve(fork)
    for entry in raw:
        if not isinstance(entry, dict) or not entry.get("sync"):
            continue
        if _resolve(Path(str(entry.get("path", "")))) != wanted:
            continue
        try:
            return SyncConfig.from_dict(entry["sync"])
        except (ValueError, TypeError):
            return None
    return None


def _resolve(path: Path) -> Path:
    """Normalize for comparison without requiring the path to exist."""
    return Path(os.path.normpath(str(path.expanduser())))
