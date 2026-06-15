"""Targets: the registry of game forks, plus preview/apply orchestration.

A *Target* is a registered game fork the Ruleset can be applied to. This module
owns four concerns, kept deliberately small:

  * the registry — a gitignored ``targets.json`` (label, absolute path, engine);
  * the apply-then-revert *preview* — runs the real pokeemerald applier on the
    fork, captures the Apply Report, then restores the fork to clean (D1);
  * the real *apply* — same applier path, but the changes are kept;
  * a per-fork-path in-process lock + per-Target snapshot cache (D2/D4).

Restore safety (D1) is load-bearing: preview gates on a clean tree, runs the
applier, then ``git checkout -- . && git clean -fd`` (no ``-x``) inside a
``try/finally`` and verifies the tree is clean again. A clean-tree gate
guarantees every untracked file after apply was applier-created, so ``clean -fd``
removes exactly those and nothing the user owns. A failed restore is a loud
500-class error carrying the exact recovery command — never a silent botch.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from ..appliers.pokeemerald.git_guard import DirtyWorkingTree, require_clean_git_status
from ..cli import _apply_pokeemerald
from ..model import Ruleset
from ..report import ApplyReport
from . import dex as dexmod
from . import snapshot as snapmod

# The marker the applier writes into a created DATA-ONLY ability's reason.
_DATA_ONLY_MARKER = "DATA ONLY"

_logger = logging.getLogger(__name__)


class TargetError(Exception):
    """A target operation failed in a way the route maps to an HTTP status.

    ``status`` is the HTTP status the route should surface; ``detail`` is the
    actionable message (or structured body) for the client.
    """

    def __init__(self, status: int, detail: Any) -> None:
        super().__init__(str(detail))
        self.status = status
        self.detail = detail


class RestoreError(TargetError):
    """A preview's post-apply restore failed — the fork may be left dirty.

    This is the worst case: the applier ran, but the fork could not be returned
    to clean. The detail carries the exact recovery command so a human can fix it
    by hand. Always a 500-class error.
    """


@dataclass(frozen=True)
class Target:
    """A registered fork: stable id, human label, absolute path, engine."""

    id: str
    label: str
    path: str
    engine: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


# --- Registry ------------------------------------------------------------- #


class TargetRegistry:
    """Load/save/add/list/remove Targets against a single ``targets.json`` file.

    The file is gitignored and lives at the project root by default (D4). Paths
    are resolved to absolute on add, so a registry entry is portable to any cwd.
    All writes go through ``_save`` so the on-disk file is always the source of
    truth — no in-memory cache to drift.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def list(self) -> List[Target]:
        return [Target(**row) for row in self._read()]

    def get(self, target_id: str) -> Target:
        for target in self.list():
            if target.id == target_id:
                return target
        raise TargetError(404, f"No target with id {target_id!r}.")

    def add(self, label: str, path: str, engine: str) -> Target:
        resolved = Path(path).expanduser().resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise TargetError(422, f"Target path does not exist: {resolved}")
        if not (resolved / ".git").exists():
            raise TargetError(422, f"Target path is not a git repo: {resolved}")
        if engine not in ("pokeemerald", "essentials"):
            raise TargetError(422, f"Unknown engine {engine!r}.")
        target = Target(
            id=uuid.uuid4().hex[:12],
            label=label,
            path=str(resolved),
            engine=engine,
        )
        rows = self._read()
        rows.append(target.as_dict())
        self._save(rows)
        return target

    def remove(self, target_id: str) -> None:
        rows = self._read()
        kept = [row for row in rows if row.get("id") != target_id]
        if len(kept) == len(rows):
            raise TargetError(404, f"No target with id {target_id!r}.")
        self._save(kept)

    def _read(self) -> List[Dict[str, str]]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            raise TargetError(
                500, f"Target registry at {self._path} is unreadable: {error}"
            ) from error
        if not isinstance(data, list):
            raise TargetError(
                500, f"Target registry at {self._path} must be a JSON array."
            )
        return data

    def _save(self, rows: List[Dict[str, str]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(rows, indent=2, sort_keys=True) + "\n"
        self._path.write_text(text, encoding="utf-8")


# --- Per-fork serialization + snapshot cache ------------------------------ #


class TargetState:
    """Per-app mutable state: a lock registry and a snapshot cache, keyed on path.

    Lives on ``app.state`` so each ``create_app`` instance is isolated (clean test
    isolation). Locks serialize preview/apply per fork so two runs can't interleave
    and corrupt each other's restore (D4). The snapshot cache makes the per-Target
    dex backdrop cheap on repeat reads (D2).
    """

    def __init__(self) -> None:
        self._registry_guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}
        self._snapshots: dict[str, dict[str, Any]] = {}

    def lock_for(self, fork_path: str) -> threading.Lock:
        with self._registry_guard:
            lock = self._locks.get(fork_path)
            if lock is None:
                lock = threading.Lock()
                self._locks[fork_path] = lock
            return lock

    def snapshot_for(self, fork_path: str) -> dict[str, Any]:
        """Return the fork's snapshot, building (and caching) it once per path.

        Serialized on the per-fork lock so two concurrent requests for the same
        fork can't both build (a TOCTOU race when the cache is checked outside any
        lock). The per-fork lock keeps other forks unblocked. After acquiring it we
        re-check the cache, build only on a miss, store, and return.
        """
        with self.lock_for(fork_path):
            cached = self._snapshots.get(fork_path)
            if cached is not None:
                return cached
            snapshot = snapmod.build_snapshot(Path(fork_path))
            self._snapshots[fork_path] = snapshot
            return snapshot

    def invalidate_snapshot(self, fork_path: str) -> None:
        with self._registry_guard:
            self._snapshots.pop(fork_path, None)


# --- git restore ---------------------------------------------------------- #


def _git_porcelain(target: Path) -> str:
    """Return ``git status --porcelain`` output, or '' if not a git repo."""
    result = subprocess.run(
        ["git", "-C", str(target), "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def restore_fork_to_clean(target: Path) -> None:
    """Restore a fork to a clean tree, then verify; raise loudly if it failed.

    Runs ``git checkout -- .`` (revert tracked edits) then ``git clean -fd`` (drop
    applier-created untracked files; no ``-x`` so the fork's gitignored build
    output survives), then re-reads ``git status --porcelain``. A non-zero return
    code from EITHER git step is a ``RestoreError`` even if the tree later reads
    clean — a silent checkout failure must never pass. A non-empty status after
    restore is also a ``RestoreError``. Every failure path carries the exact
    recovery command — a botched restore must be loud and hand-recoverable.
    """
    target = Path(target)
    recovery = f"git -C {target} checkout -- . && git -C {target} clean -fd"

    def _fail(step: str, stderr: str) -> RestoreError:
        return RestoreError(
            500,
            {
                "message": (
                    f"Restore of {target} failed at the git {step} step; the fork "
                    f"may be left dirty. Run this to recover by hand: {recovery}"
                ),
                "recovery": recovery,
                "failed_step": step,
                "stderr": stderr.strip(),
            },
        )

    checkout = subprocess.run(
        ["git", "-C", str(target), "checkout", "--", "."],
        capture_output=True,
        text=True,
    )
    if checkout.returncode != 0:
        raise _fail("checkout", checkout.stderr)

    clean = subprocess.run(
        ["git", "-C", str(target), "clean", "-fd"],
        capture_output=True,
        text=True,
    )
    if clean.returncode != 0:
        raise _fail("clean", clean.stderr)

    leftover = _git_porcelain(target)
    if leftover:
        raise RestoreError(
            500,
            {
                "message": (
                    f"Restore of {target} failed; the fork may be left dirty. "
                    f"Run this to recover by hand: {recovery}"
                ),
                "recovery": recovery,
                "git_status": leftover,
                "checkout_stderr": checkout.stderr.strip(),
                "clean_stderr": clean.stderr.strip(),
            },
        )


# --- Apply Report → API payload ------------------------------------------- #


def _report_payload(report: ApplyReport) -> dict[str, Any]:
    """Shape an ApplyReport into the API contract's report payload.

    ``created`` counts entries the applier created; ``data_only`` lists the
    created abilities whose mechanic is unimplemented, each carrying the packet
    link the UI surfaces so the silent-inert-ability trap stays visible.
    """
    counts = report.counts()
    created = sum(1 for e in report.entries if e.reason.startswith("created"))
    data_only = [
        {
            "chrooked_id": e.chrooked_id,
            "symbol": e.symbol,
            "packet_url": (f"/api/behaviors/{e.chrooked_id}/packet?engine=pokeemerald"),
        }
        for e in report.entries
        if _DATA_ONLY_MARKER in e.reason
    ]
    return {
        "applied": counts["applied"],
        "partial": counts["partial"],
        "blocked": counts["blocked"],
        "created": created,
        "data_only": data_only,
        "report_md": report.to_markdown(),
    }


def _run_applier(target: Path, engine: str, ruleset: Ruleset) -> ApplyReport:
    """Run the real applier for ``engine`` over ``target`` and return its report.

    Reuses ``cli._apply_pokeemerald`` — the same code path the CLI ``apply`` uses
    — so preview and apply are honest. Essentials is deferred (D3); the registry
    records engine so it slots in later, but the applier is pokeemerald-only here.
    """
    if engine != "pokeemerald":
        raise TargetError(
            422,
            f"Engine {engine!r} is not supported for preview/apply yet "
            "(pokeemerald only; essentials deferred).",
        )
    report = ApplyReport()
    _apply_pokeemerald(target, "all", ruleset, report)
    return report


# --- Orchestration -------------------------------------------------------- #


def preview_target(
    target: Target, ruleset: Ruleset, state: TargetState
) -> dict[str, Any]:
    """Apply-then-revert preview: real applier, then restore the fork to clean.

    409 if the tree is dirty (the fork is left untouched). Otherwise runs the
    applier, captures the report, then restores inside a ``try/finally`` and
    verifies clean — a failed restore raises ``RestoreError`` (500-class). No
    ``force`` here (D1: force is for real apply only).
    """
    fork = Path(target.path)
    lock = state.lock_for(target.path)
    with lock:
        try:
            require_clean_git_status(fork, force=False)
        except DirtyWorkingTree as error:
            raise TargetError(409, str(error)) from error

        applier_error: BaseException | None = None
        try:
            report = _run_applier(fork, target.engine, ruleset)
            return _report_payload(report)
        except BaseException as error:  # noqa: BLE001 — re-raised via finally
            applier_error = error
            raise
        finally:
            # Always restore — even if the applier raised mid-run. A RestoreError
            # raised here propagates (the route maps it to a loud 500); a normal
            # return still runs this first. If the applier ALSO raised, the restore
            # failure would otherwise mask it, so log the applier cause first.
            try:
                restore_fork_to_clean(fork)
            except RestoreError:
                if applier_error is not None:
                    _logger.error(
                        "Applier failed during preview of %s, and the post-apply "
                        "restore also failed; surfacing the RestoreError.",
                        fork,
                        exc_info=applier_error,
                    )
                raise


def apply_target(
    target: Target, ruleset: Ruleset, state: TargetState, force: bool
) -> dict[str, Any]:
    """Real apply: run the applier and KEEP the changes.

    409 if the tree is dirty and not ``force``; proceeds when ``force=True``.
    Invalidates the cached snapshot for this fork so a later dex backdrop reflects
    the freshly applied values.
    """
    fork = Path(target.path)
    lock = state.lock_for(target.path)
    with lock:
        try:
            require_clean_git_status(fork, force=force)
        except DirtyWorkingTree as error:
            raise TargetError(409, str(error)) from error
        report = _run_applier(fork, target.engine, ruleset)
        report.write(fork / "apply-report.md")
        state.invalidate_snapshot(target.path)
        return _report_payload(report)


def target_dex(
    target: Target, ruleset: Ruleset, state: TargetState
) -> list[dict[str, Any]]:
    """Per-Target dex backdrop: ``build_dex(build_snapshot(target), ruleset)``.

    The fork's own values come from re-running the M0 snapshot reader on it
    (cached per path, D2), then the existing M1 merge overlays the Ruleset — so
    the backdrop reuses M0 + M1 wholesale with no new merge path.
    """
    snapshot = state.snapshot_for(target.path)
    return dexmod.build_dex(snapshot, ruleset)


def target_abilities(
    target: Target, ruleset: Ruleset, state: TargetState
) -> list[dict[str, Any]]:
    """Per-Target abilities backdrop: ``build_abilities(build_snapshot(target), ruleset)``.

    The same shape as ``target_dex``: the fork's own base abilities come from the
    cached per-Target snapshot (D2), then the abilities merge overlays the Ruleset
    — so the backdrop reuses the snapshot population + merge wholesale.
    """
    snapshot = state.snapshot_for(target.path)
    return dexmod.build_abilities(snapshot, ruleset)


def target_moves(
    target: Target, ruleset: Ruleset, state: TargetState
) -> list[dict[str, Any]]:
    """Per-Target moves backdrop: ``build_moves(build_snapshot(target), ruleset)``.

    The same shape as ``target_dex`` / ``target_abilities``: the fork's own base
    moves come from the cached per-Target snapshot (D2, neutralized at build time),
    then the moves merge overlays the Ruleset — so the backdrop reuses the
    snapshot population + merge wholesale.
    """
    snapshot = state.snapshot_for(target.path)
    return dexmod.build_moves(snapshot, ruleset)
