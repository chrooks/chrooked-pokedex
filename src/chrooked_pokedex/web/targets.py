"""Targets: the registry of game forks, plus preview/apply orchestration.

A *Target* is a registered game fork the Ruleset can be applied to. This module
owns four concerns, kept deliberately small:

  * the registry — a gitignored ``targets.json`` (label, absolute path, engine);
  * the apply-then-revert *preview* — runs the real applier on the target,
    captures the Apply Report, then restores the target to its prior state (D1);
  * the real *apply* — same applier path, but the changes are kept;
  * a per-fork-path in-process lock + per-Target snapshot cache (D2/D4).

Restore safety (D1) is load-bearing for preview.  Two paths exist:

**Git target** (the ``.git`` directory is present): preview gates on a clean
tree, runs the applier, then ``git checkout -- . && git clean -fd`` (no
``-x``) inside a ``try/finally`` and verifies the tree is clean again.

**Non-git target** (plain directory, e.g. Essentials games that are not git
repos): preview snapshots the PBS ``*.txt`` files into a temp directory before
running the applier, then restores them byte-for-byte from the snapshot in the
``finally`` block.  On restore failure, a ``RestoreError`` is raised with an
honest, vcs-neutral recovery message (not a git command).

A failed restore is always a loud 500-class error — never a silent botch.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import threading
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..appliers.dispatch import route_apply as _route_apply
from ..appliers.essentials.data_backup import (
    DataBackupError,
    backup_essentials_data,
)
from ..appliers.essentials.dialect import detect_dialect as _detect_dialect
from ..appliers.pokeemerald.git_guard import DirtyWorkingTree, require_clean_git_status
from ..fingerprint import hash_files, hash_ruleset_dir
from .. import ledger as ledgermod
from ..model import Ruleset
from ..model.compose import compose_ruleset, overlay_touched_fields
from ..model.holds import HoldSet, load_holds
from ..model.target_edits import TargetEdits, load_target_edits
from ..report import ApplyReport
from . import dex as dexmod
from . import snapshot as snapmod
from . import snapshot_essentials as snapmod_essentials
from . import snapshot_rejuv as snapmod_rejuv

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


def _validate_target_path(resolved: Path, engine: str) -> None:
    """Assert a Target dir still looks like the engine it claims. Called at add AND
    at apply/preview: a registered dir can be wiped or moved after registration, and
    an unvalidated apply against an empty pokeemerald husk silently blocks every
    entry (resolution map empty → create-all → every insert fails) instead of
    failing fast. Re-check the same invariants `add` established, every run."""
    if not resolved.exists() or not resolved.is_dir():
        raise TargetError(422, f"Target path does not exist: {resolved}")
    if engine not in ("pokeemerald", "essentials", "polishedcrystal", "rejuv"):
        raise TargetError(422, f"Unknown engine {engine!r}.")
    if engine == "rejuv" and not (resolved / "Scripts" / "Rejuv" / "Definitions").is_dir():
        raise TargetError(
            422,
            f"Target path does not look like a Rejuvenation game "
            f"(no Scripts/Rejuv/Definitions): {resolved}",
        )
    # pokeemerald targets must be git repos (preview-restore is git-based).
    # essentials targets may be plain directories (non-git Essentials games).
    if engine == "pokeemerald" and not (resolved / ".git").exists():
        raise TargetError(422, f"Target path is not a git repo: {resolved}")


@dataclass(frozen=True)
class Target:
    """A registered fork: stable id, human label, absolute path, engine.

    ``namespace`` binds this Target to a committed Target Override set under
    ``ruleset/targets/<namespace>/``. None means the Target has no overrides and
    applies the base Ruleset unchanged. The binding is explicit (set by the user),
    never guessed from the label, because ``targets.json`` is machine-specific
    while the namespace slug is committed canon.
    """

    id: str
    label: str
    path: str
    engine: str
    namespace: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
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

    def add(
        self, label: str, path: str, engine: str, namespace: Optional[str] = None
    ) -> Target:
        resolved = Path(path).expanduser().resolve()
        _validate_target_path(resolved, engine)
        target = Target(
            id=uuid.uuid4().hex[:12],
            label=label,
            path=str(resolved),
            engine=engine,
            namespace=namespace or None,
        )
        rows = self._read()
        rows.append(target.as_dict())
        self._save(rows)
        return target

    def set_namespace(self, target_id: str, namespace: Optional[str]) -> Target:
        """Bind (or clear) a Target's override namespace, returning the updated row.

        ``namespace`` is the committed slug under ``ruleset/targets/<slug>/``. An
        empty/None value clears the binding (the Target reverts to base-only).
        """
        slug = (namespace or "").strip() or None
        rows = self._read()
        updated: Optional[Target] = None
        for row in rows:
            if row.get("id") == target_id:
                row["namespace"] = slug
                updated = Target(**row)
        if updated is None:
            raise TargetError(404, f"No target with id {target_id!r}.")
        self._save(rows)
        return updated

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
        # Preview report cache (#63): one slot per Target path holding
        # ((ruleset_fp, target_fp), payload). A changed Ruleset or Target yields a
        # new key, so the slot self-invalidates; a real apply drops it explicitly.
        self._previews: dict[str, tuple[tuple[str, str], dict[str, Any]]] = {}
        # Counters are shared across Targets but each preview holds only its own
        # per-fork lock, so guard the increments with their own lock to avoid a
        # lost-update race when two different Targets preview concurrently.
        self.preview_stats = {"hits": 0, "misses": 0}
        self._stats_lock = threading.Lock()

    def lock_for(self, fork_path: str) -> threading.Lock:
        with self._registry_guard:
            lock = self._locks.get(fork_path)
            if lock is None:
                lock = threading.Lock()
                self._locks[fork_path] = lock
            return lock

    def snapshot_for(self, target: Target) -> dict[str, Any]:
        """Return the Target's snapshot, building (and caching) it once per path.

        Routes on ``target.engine`` (D1): ``pokeemerald`` reads the C source tree
        with ``build_snapshot``; ``essentials`` reads the ``PBS/`` tree with the
        dialect-routed ``build_snapshot_essentials``. The cache key stays
        ``target.path``, so both engines share the per-path lock + cache.

        Serialized on the per-fork lock so two concurrent requests for the same
        fork can't both build (a TOCTOU race when the cache is checked outside any
        lock). The per-fork lock keeps other forks unblocked. After acquiring it we
        re-check the cache, build only on a miss, store, and return.
        """
        fork_path = target.path
        with self.lock_for(fork_path):
            cached = self._snapshots.get(fork_path)
            if cached is not None:
                return cached
            if target.engine == "essentials":
                snapshot = snapmod_essentials.build_snapshot_essentials(Path(fork_path))
            elif target.engine == "rejuv":
                try:
                    snapshot = snapmod_rejuv.build_snapshot_rejuv(Path(fork_path))
                except snapmod_rejuv.RejuvSnapshotError as error:
                    raise TargetError(500, str(error)) from error
            else:
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


# --- VCS-neutral restore helpers ------------------------------------------ #


def _is_git_repo(target: Path) -> bool:
    """Return True when ``target`` lives inside a git repository."""
    result = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "--git-dir"],
        capture_output=True,
    )
    return result.returncode == 0


def _snapshot_pbs_files(target: Path) -> str:
    """Copy all ``*.txt`` files from ``target/PBS/`` into a fresh temp dir.

    Returns the path to the temp dir as a string (caller owns cleanup).
    Raises ``TargetError(500, ...)`` when the PBS directory does not exist.
    """
    pbs_dir = target / "PBS"
    if not pbs_dir.is_dir():
        raise TargetError(
            500,
            f"Cannot snapshot {target}: PBS/ directory not found. "
            "The target may not be a valid Essentials game.",
        )
    tmp = tempfile.mkdtemp(prefix="chrooked_preview_")
    for txt_file in pbs_dir.glob("*.txt"):
        shutil.copy2(txt_file, Path(tmp) / txt_file.name)
    return tmp


def _restore_from_snapshot(target: Path, snapshot_dir: str) -> None:
    """Restore ``target/PBS/*.txt`` from a previously taken snapshot.

    Over-writes each snapshotted file in-place, then removes any ``*.txt``
    files the applier created that were NOT in the snapshot.  Raises
    ``RestoreError(500, ...)`` with a vcs-neutral recovery message if any
    file-system operation fails.
    """
    pbs_dir = target / "PBS"
    snap = Path(snapshot_dir)
    snapshotted = {f.name for f in snap.glob("*.txt")}
    recovery = (
        f"Manually copy the PBS/*.txt files from '{snapshot_dir}' back into "
        f"'{pbs_dir}'."
    )
    try:
        # Restore every snapshotted file.
        for name in snapshotted:
            shutil.copy2(snap / name, pbs_dir / name)
        # Remove any applier-created *.txt files not in the snapshot.
        for txt_file in pbs_dir.glob("*.txt"):
            if txt_file.name not in snapshotted:
                txt_file.unlink()
    except OSError as exc:
        raise RestoreError(
            500,
            {
                "message": (
                    f"Snapshot-restore of {target} failed: {exc}. "
                    f"The target may be left dirty. Recovery: {recovery}"
                ),
                "recovery": recovery,
            },
        ) from exc


def _preview_restore(target: Path, is_git: bool, snapshot_dir: str | None) -> None:
    """Route preview restore to the right strategy based on target type.

    *Git targets*: delegate to ``restore_fork_to_clean`` (proven path).
    *Non-git targets*: delegate to ``_restore_from_snapshot``.
    """
    if is_git:
        restore_fork_to_clean(target)
    else:
        assert snapshot_dir is not None  # set before applier runs for non-git
        _restore_from_snapshot(target, snapshot_dir)


# --- Apply Report → API payload ------------------------------------------- #


def _report_payload(report: ApplyReport) -> dict[str, Any]:
    """Shape an ApplyReport into the API contract's report payload.

    ``created`` counts entries the applier created; ``data_only`` lists the
    created abilities whose mechanic is unimplemented, each carrying the packet
    link the UI surfaces so the silent-inert-ability trap stays visible.

    ``held`` is the fourth status (target-pinned, deliberately not written);
    ``by_category`` is a per-category status breakdown (so the UI can say
    "moves 141 · 2 partial"); ``entries`` lists only the *actionable*
    (non-applied) entries with their reasons — the bulk applied entries stay as
    counts so the payload stays small.
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
    by_category: dict[str, dict[str, int]] = {}
    for entry in report.entries:
        bucket = by_category.setdefault(
            entry.category, {"applied": 0, "partial": 0, "blocked": 0, "held": 0}
        )
        bucket[entry.status] += 1
    entries = [
        {
            "status": e.status,
            "category": e.category,
            "chrooked_id": e.chrooked_id,
            "symbol": e.symbol,
            "reason": e.reason,
            "partial_fields": list(e.partial_fields),
        }
        for e in report.entries
        if e.status != "applied"
    ]
    return {
        "applied": counts["applied"],
        "partial": counts["partial"],
        "blocked": counts["blocked"],
        "held": counts["held"],
        "created": created,
        "by_category": by_category,
        "entries": entries,
        "data_only": data_only,
        "report_md": report.to_markdown(),
    }


def _backup_essentials_data(fork: Path) -> dict[str, Any]:
    """Web wrapper over the shared Data/ backup: map failure to a 500.

    The backup logic is engine-neutral (shared with the CLI ``apply``); the web
    path maps a failed copy to a 500 so the apply aborts with a usable message
    rather than proceeding without the recovery net.
    """
    try:
        return backup_essentials_data(fork)
    except DataBackupError as error:
        raise TargetError(
            500,
            (
                f"{error}. Apply aborted to protect the game; free space or back "
                "up Data/ by hand, then retry."
            ),
        ) from error


def _run_applier(
    target: Path, engine: str, ruleset: Ruleset,
    holds: "HoldSet | None" = None, target_edits: "TargetEdits | None" = None,
) -> ApplyReport:
    """Run the real applier for ``engine`` over ``target`` and return its report.

    Delegates to ``appliers/dispatch.py::route_apply`` so the web path and the
    CLI dispatch identically (D-DRY).  An unrecognized Essentials format writes
    nothing and records a ``blocked`` entry — the existing honest Error State.
    Preview's git revert (D1) is engine-agnostic and runs in the caller's
    ``finally`` block regardless of which applier ran.

    ``holds`` and ``target_edits`` carry the per-Target stand-downs and additive
    edits; both default to empty (the registry path may omit them), matching the
    CLI's no-slug behavior.
    """
    report = ApplyReport()
    _route_apply(
        target, engine, ruleset, report, holds=holds, target_edits=target_edits
    )
    return report


def _load_target_layers(
    ruleset_dir: Optional[Path], target: Target
) -> tuple["HoldSet", "TargetEdits"]:
    """Load this Target's holds + additive edits from ``ruleset/targets/<slug>/``.

    Keyed by ``target.namespace`` (the committed slug). Returns empty layers when
    no ``ruleset_dir`` or no namespace is set — the same as a CLI apply with no
    ``--as``, so an unregistered/base Target behaves exactly as before.
    """
    slug = target.namespace if ruleset_dir is not None else None
    base = Path(ruleset_dir) if ruleset_dir is not None else Path(".")
    return load_holds(base, slug), load_target_edits(base, slug)


# --- Orchestration -------------------------------------------------------- #


def _preview_cache_key(
    target: Target, ruleset_dir: Optional[Path]
) -> tuple[str, str] | None:
    """Key for the preview cache: (ruleset fingerprint, target fingerprint).

    Returns None when the inputs can't be fingerprinted cheaply, which disables
    caching for that call — correctness over a cache hit. Essentials targets
    fingerprint their ``PBS/*.txt`` inputs (exactly what the applier reads and
    ``_snapshot_pbs_files`` snapshots). ``# ponytail:`` pokeemerald preview stays
    uncached until it matters — enumerating its C inputs isn't worth it yet.
    """
    if ruleset_dir is None or target.engine != "essentials":
        return None
    pbs = Path(target.path) / "PBS"
    if not pbs.is_dir():
        return None
    txts = sorted(pbs.glob("*.txt"))
    if not txts:
        return None
    return (hash_ruleset_dir(Path(ruleset_dir)), hash_files(txts, pbs))


def preview_target(
    target: Target, ruleset: Ruleset, state: TargetState,
    ruleset_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Apply-then-revert preview: real applier, then restore the target to prior state.

    Two restore strategies, chosen by whether the target is a git repo:

    * **Git target**: gate on clean tree (409 if dirty), run applier, then
      ``git checkout -- . && git clean -fd`` in a ``try/finally``.
    * **Non-git target**: snapshot PBS ``*.txt`` files into a temp dir, run
      applier, then restore from snapshot in a ``try/finally``.  The temp dir
      is cleaned up in a ``finally`` regardless of outcome.

    A failed restore raises ``RestoreError`` (500-class).  No ``force`` option
    here — D1: force is for real apply only.
    """
    if target.engine == "rejuv":
        # ponytail: preview needs a restore strategy for patch/ deltas — real
        # apply is idempotent and honest for rejuv, so preview waits for demand.
        raise TargetError(422, "Preview is not supported for Rejuvenation targets yet; use Apply.")
    fork = Path(target.path)
    _validate_target_path(fork, target.engine)
    lock = state.lock_for(target.path)
    with lock:
        # Preview cache (#63): identical Ruleset + Target inputs → reuse the last
        # report and skip the applier + restore churn entirely.
        cache_key = _preview_cache_key(target, ruleset_dir)
        if cache_key is not None:
            cached = state._previews.get(target.path)
            if cached is not None and cached[0] == cache_key:
                with state._stats_lock:
                    state.preview_stats["hits"] += 1
                return cached[1]

        # The git gate + git restore are the pokeemerald (C source) path.
        # Essentials targets operate on PBS/*.txt and use the dirty-safe snapshot
        # restore even when the game folder happens to sit inside a git repo —
        # otherwise a dirty repo (e.g. IF2 with hundreds of uncommitted modding
        # edits) would 409 every Preview, which has no force.
        is_git = target.engine == "pokeemerald" and _is_git_repo(fork)

        if is_git:
            # Git path: gate on clean tree first.
            try:
                require_clean_git_status(fork, force=False)
            except DirtyWorkingTree as error:
                raise TargetError(409, str(error)) from error

        # Take snapshot BEFORE running the applier (non-git only).
        snapshot_dir: str | None = None
        if not is_git:
            snapshot_dir = _snapshot_pbs_files(fork)

        holds, target_edits = _load_target_layers(ruleset_dir, target)
        applier_error: BaseException | None = None
        try:
            report = _run_applier(
                fork, target.engine, ruleset, holds=holds, target_edits=target_edits
            )
            payload = _report_payload(report)
            if cache_key is not None:
                state._previews[target.path] = (cache_key, payload)
                with state._stats_lock:
                    state.preview_stats["misses"] += 1
            return payload
        except BaseException as error:  # noqa: BLE001 — re-raised via finally
            applier_error = error
            raise
        finally:
            # Always restore — even if the applier raised mid-run.
            try:
                _preview_restore(fork, is_git, snapshot_dir)
            except RestoreError:
                if applier_error is not None:
                    _logger.error(
                        "Applier failed during preview of %s, and the post-apply "
                        "restore also failed; surfacing the RestoreError.",
                        fork,
                        exc_info=applier_error,
                    )
                raise
            finally:
                # Clean up the temp snapshot dir regardless of restore outcome.
                if snapshot_dir is not None:
                    shutil.rmtree(snapshot_dir, ignore_errors=True)


def apply_target(
    target: Target,
    ruleset: Ruleset,
    state: TargetState,
    force: bool,
    ledger_dir: Optional[Path] = None,
    ruleset_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Real apply: run the applier and KEEP the changes.

    For git targets: 409 if the tree is dirty and not ``force``; proceeds when
    ``force=True``.  For non-git targets (e.g. a plain Essentials game
    directory): the clean-tree gate is skipped entirely — there is no git tree
    to protect, and apply always keeps changes.

    Invalidates the cached snapshot for this fork so a later dex backdrop
    reflects the freshly applied values.
    """
    fork = Path(target.path)
    _validate_target_path(fork, target.engine)
    lock = state.lock_for(target.path)
    with lock:
        # Clean-tree gate is pokeemerald-only (see preview_target): an Essentials
        # game writes PBS text and keeps it — there is no git restore to protect,
        # so a git repo it happens to live in must not gate the apply.
        if target.engine == "pokeemerald" and _is_git_repo(fork):
            try:
                require_clean_git_status(fork, force=force)
            except DirtyWorkingTree as error:
                raise TargetError(409, str(error)) from error
        # Essentials forks recompile PBS → Data/*.dat on boot; back Data/ up once
        # before writing so a bricking recompile is recoverable (raises if it
        # can't, aborting the apply).
        data_backup = (
            _backup_essentials_data(fork) if target.engine == "essentials" else None
        )
        holds, target_edits = _load_target_layers(ruleset_dir, target)
        report = _run_applier(
            fork, target.engine, ruleset, holds=holds, target_edits=target_edits
        )
        report.write(fork / "apply-report.md")
        state.invalidate_snapshot(target.path)
        # Apply changed the Target, so any cached preview for it is now stale.
        state._previews.pop(target.path, None)
        if ledger_dir is not None:
            scope = f"target:{target.namespace}" if target.namespace else "base"
            blocked = [
                {"chrooked_id": entry.chrooked_id, "reason": entry.reason}
                for entry in report.entries
                if entry.status == "blocked"
            ]
            ledgermod.append(
                ledger_dir,
                {
                    "scope": scope,
                    "kind": "apply",
                    "chrooked_id": None,
                    "source": "apply",
                    "report": report.counts(),
                    "blocked_entries": blocked,
                },
            )
        payload = _report_payload(report)
        payload["data_backup"] = data_backup
        return payload


def _prettify_internal_name(internal: str) -> str:
    """Turn an InternalName into a human-readable display label.

    Handles ALL_CAPS names (EARTHQUAKE → Earthquake) and simple CamelCase
    (FireSlash → Fire Slash) as a best-effort prettify. Used only when the
    canonical English name map has no entry for this chrooked_id.
    """
    import re

    # If the name is all-uppercase (or digits/underscores only), title-case it.
    name = internal.replace("_", " ").strip()
    if name == name.upper():
        return name.title()
    # CamelCase: insert a space before each uppercase letter that follows a
    # lowercase letter or digit.
    spaced = re.sub(r"(?<=[a-z0-9])([A-Z])", r" \1", name)
    return spaced.title()


def _english_moves_map(
    base_snapshot: dict[str, Any], ruleset: Ruleset
) -> dict[str, str]:
    """chrooked_id → English name, built from base snapshot ⊕ Ruleset moves."""
    merged = dexmod.build_moves(base_snapshot, ruleset)
    return {entry["chrooked_id"]: entry["name"] for entry in merged if entry.get("name")}


def _english_abilities_map(
    base_snapshot: dict[str, Any], ruleset: Ruleset
) -> dict[str, str]:
    """chrooked_id → English name, built from base snapshot ⊕ Ruleset abilities."""
    merged = dexmod.build_abilities(base_snapshot, ruleset)
    return {entry["chrooked_id"]: entry["name"] for entry in merged if entry.get("name")}


def _english_species_map(
    base_snapshot: dict[str, Any], ruleset: Ruleset
) -> dict[str, str]:
    """chrooked_id → English name, built from base snapshot ⊕ Ruleset species."""
    merged = dexmod.build_dex(base_snapshot, ruleset)
    return {entry["chrooked_id"]: entry["name"] for entry in merged if entry.get("name")}


def _english_ability_descriptions(
    base_snapshot: dict[str, Any], ruleset: Ruleset
) -> dict[str, str]:
    """chrooked_id → English description, from base snapshot ⊕ Ruleset abilities."""
    merged = dexmod.build_abilities(base_snapshot, ruleset)
    return {
        entry["chrooked_id"]: entry["description"]
        for entry in merged
        if entry.get("description")
    }


def _english_move_descriptions(
    base_snapshot: dict[str, Any], ruleset: Ruleset
) -> dict[str, str]:
    """chrooked_id → English description, from base snapshot ⊕ Ruleset moves."""
    merged = dexmod.build_moves(base_snapshot, ruleset)
    return {
        entry["chrooked_id"]: entry["description"]
        for entry in merged
        if entry.get("description")
    }


def _english_name_for(chrooked_id: str, english_map: dict[str, str]) -> str:
    """Canonical English name by chrooked_id, prettified InternalName as fallback."""
    english_name = english_map.get(chrooked_id)
    if english_name is None:
        english_name = _prettify_internal_name(chrooked_id)
    return english_name


def _relabel_descriptions(
    entries: list[dict[str, Any]],
    description_map: dict[str, str],
) -> list[dict[str, Any]]:
    """Return a new list overlaying the English ``description`` by chrooked_id.

    When the base has no English description for an entry (e.g. a custom/LLM-
    authored ability or move), the entry keeps its own (localized) description —
    honest, never blank. Only the ``description`` field changes.
    """
    result = []
    for entry in entries:
        chrooked_id = entry.get("chrooked_id", "")
        english_description = description_map.get(chrooked_id)
        if english_description is None:
            result.append(entry)
            continue
        result.append({**entry, "description": english_description})
    return result


def _relabel_species_learnsets(
    entries: list[dict[str, Any]],
    moves_map: dict[str, str],
) -> list[dict[str, Any]]:
    """Return a new list relabeling each species' ``learnset[].move`` to English.

    Each learnset entry's ``move`` is rewritten to the canonical English name
    keyed by its ``move_id`` (the language-neutral chrooked_id), falling back to
    a prettified InternalName when the base has no entry. New dicts/lists only.

    A learnset slot with no ``move_id`` came from a chrooked Ruleset override
    (``build_dex`` rebuilds those as ``{level, move}``), whose ``move`` is
    already an English display name — keep it as-is rather than blanking it.
    """
    result = []
    for entry in entries:
        learnset = entry.get("learnset")
        if not learnset:
            result.append(entry)
            continue
        relabeled = []
        for slot in learnset:
            move_id = slot.get("move_id")
            if move_id:
                relabeled.append(
                    {**slot, "move": _english_name_for(move_id, moves_map)}
                )
            else:
                relabeled.append(slot)
        result.append({**entry, "learnset": relabeled})
    return result


def _relabel_species_abilities(
    entries: list[dict[str, Any]],
    abilities_map: dict[str, str],
) -> list[dict[str, Any]]:
    """Return a new list relabeling each species' nested ``abilities`` slots.

    Each non-``None`` slot value (a raw internal token like ``OVERGROW``) is
    rewritten to its canonical English name keyed by ``nz.slug(<slot value>)``,
    with a prettified InternalName fallback. ``None`` slots stay ``None``. New
    dicts only.
    """
    from ..seed import neutralize as nz

    result = []
    for entry in entries:
        slots = entry.get("abilities")
        if not isinstance(slots, dict):
            result.append(entry)
            continue
        relabeled = {
            slot: (
                None
                if value is None
                else _english_name_for(nz.slug(value), abilities_map)
            )
            for slot, value in slots.items()
        }
        result.append({**entry, "abilities": relabeled})
    return result


def _relabel_names(
    entries: list[dict[str, Any]],
    english_map: dict[str, str],
    prefer_internal: bool = False,
) -> list[dict[str, Any]]:
    """Return a new list with each entry's 'name' replaced by its English canonical.

    Priority:
    1. Canonical English from base ⊕ Ruleset (by chrooked_id).
    2. The target's own PBS ``Name`` — a target-only fakemon (e.g. Harregg) has
       no canonical English, and its PBS name is the author's real display name,
       which beats a prettified code-name (InternalName ``AQUILATUS``).
    3. Prettified InternalName / chrooked_id, only if the entry has no name.

    ``prefer_internal=True`` skips step 2 and prettifies the InternalName directly
    when there is no canon. Used for moves: a target-only move's PBS ``Name`` is a
    LOCALIZED string (e.g. Spanish "Golpe Especial Africano"), so the language-
    neutral InternalName ("Africanvsoriginal") is the honest fallback — unlike a
    fakemon species whose PBS name is the author's intended display name.

    All other fields are left unchanged; only the display ``name`` changes.
    """
    result = []
    for entry in entries:
        chrooked_id = entry.get("chrooked_id", "")
        english_name = english_map.get(chrooked_id)
        if english_name is None:
            internal_label = _prettify_internal_name(
                entry.get("internal") or chrooked_id
            )
            if prefer_internal:
                english_name = internal_label
            else:
                # Keep the PBS Name; prettify only as a last resort with no name.
                english_name = entry.get("name") or internal_label
        result.append({**entry, "name": english_name})
    return result


def load_target_overlay(ruleset_dir: Path, target: Target) -> Optional[Ruleset]:
    """Load the Target's committed Override namespace, or None when unbound.

    The overlay lives at ``ruleset/targets/<namespace>/``. A Target with no
    ``namespace`` (or whose folder is absent) returns None — it applies the base
    Ruleset unchanged, exactly as before this feature existed.
    """
    if not target.namespace:
        return None
    return Ruleset.load_namespace(Path(ruleset_dir), target.namespace)


def effective_ruleset(base_ruleset: Ruleset, overlay: Optional[Ruleset]) -> Ruleset:
    """Compose the base Ruleset with a Target Override overlay (last wins per field)."""
    return compose_ruleset(base_ruleset, overlay)


def _annotate_target_fields(
    entries: list[dict[str, Any]], overlay: Optional[Ruleset]
) -> list[dict[str, Any]]:
    """Mark each species entry with the fields scoped to this Target (the badge data).

    ``target_overridden_fields`` is the set of fields the overlay authored for that
    ``chrooked_id`` — what the UI badges as "this target only". Empty list when the
    overlay does not touch that species (or there is no overlay).
    """
    if overlay is None:
        return entries
    return [
        {
            **entry,
            "target_overridden_fields": sorted(
                overlay_touched_fields(overlay.species[entry["chrooked_id"]])
            )
            if entry["chrooked_id"] in overlay.species
            else [],
        }
        for entry in entries
    ]


def rekey_ruleset_to_rejuv(ruleset: Ruleset, snapshot: dict[str, Any]) -> Ruleset:
    """Re-key the Ruleset's species Overrides onto a Rejuv snapshot's form ids.

    The two name forms differently. The Ruleset follows the base snapshot
    (`sawsbuckspring`, `ponytagalar`); Rejuv slugs a form `<base>--<label slug>`
    and leaves form 0 as the bare base (`sawsbuck`, `ponyta--galarianform`). The
    projection joins on `chrooked_id` alone, so 189 of ~1000 Overrides — every
    form species — silently failed to join and the dex showed unedited target
    truth. The Applier already resolves these (RejuvResolution._match_form); this
    is the same bridge for the read path.

    Match rule: a snapshot entry's base id plus its form label's core
    ("Galarian Form" -> "galarian"), against Ruleset ids that start with that
    base and whose remaining suffix PREFIXES the core — "ponytagalar" bridges to
    "galarian", "arcaninehisui" to "hisuian". Longest suffix wins; a tie is
    ambiguous and left unjoined. A snapshot id that already joins directly is
    never rewritten, so this can only add joins, never move existing ones.
    """
    from ..appliers.rejuv.resolution import _form_core

    # Pass 1: every (snapshot form -> Ruleset id) the match rule allows.
    claims: dict[str, list[tuple[str, str]]] = {}
    for cid, entry in snapshot.get("species", {}).items():
        if cid in ruleset.species:
            continue  # already joins directly — never override a real match
        base = cid.split("--")[0]
        core = _form_core(str(entry.get("form") or ""))
        if not core:
            continue
        matches = [
            rid
            for rid in ruleset.species
            if rid.startswith(base) and rid != base and core.startswith(rid[len(base):])
        ]
        if not matches:
            continue
        best = max(matches, key=len)
        if sum(1 for m in matches if len(m) == len(best)) > 1:
            continue  # ambiguous — leave unjoined rather than guess a form
        claims.setdefault(best, []).append((cid, core))

    # Pass 2: keep the join one-to-one. Rejuv carries original forms the Ruleset
    # never named (Absol's "Mega Form Z" alongside "Mega Form"), and both prefix-
    # match the one Override. The Applier resolves such an id to a single form, so
    # letting every near-match inherit it would preview edits Apply won't write.
    # Closest core wins: an exact suffix match first, then the shortest core.
    species = dict(ruleset.species)
    for rid, candidates in claims.items():
        suffix = rid[len(min(c for c, _ in candidates).split("--")[0]):]
        cid, _ = min(candidates, key=lambda c: (c[1] != suffix, len(c[1]), c[0]))
        species[cid] = ruleset.species[rid]
    return replace(ruleset, species=species)


def target_dex(
    target: Target,
    ruleset: Ruleset,
    state: TargetState,
    base_snapshot: dict[str, Any] | None = None,
    overlay: Optional[Ruleset] = None,
) -> list[dict[str, Any]]:
    """Per-Target dex backdrop: ``build_dex(build_snapshot(target), ruleset)``.

    ``ruleset`` is the effective Ruleset (base ⊕ Target Override) — compose it via
    ``effective_ruleset`` before calling. Pass ``overlay`` (the raw Target Override
    set) to annotate each species with ``target_overridden_fields`` for the UI badge.

    For Essentials targets, species display names are relabeled to canonical
    English using the base snapshot ⊕ Ruleset name map (keyed by chrooked_id).
    Pass ``base_snapshot`` to enable the relabeling; omitting it skips the
    relabel (pokeemerald targets and tests that don't inject the base).
    """
    snapshot = state.snapshot_for(target)
    if target.engine == "rejuv":
        ruleset = rekey_ruleset_to_rejuv(ruleset, snapshot)
    entries = dexmod.build_dex(snapshot, ruleset)
    if target.engine in ("essentials", "rejuv") and base_snapshot is not None:
        english_map = _english_species_map(base_snapshot, ruleset)
        entries = _relabel_names(entries, english_map)
        # #39: nested learnset moves render canonical English by move_id.
        moves_map = _english_moves_map(base_snapshot, ruleset)
        entries = _relabel_species_learnsets(entries, moves_map)
        # #43: nested ability slots render canonical English by chrooked_id.
        abilities_map = _english_abilities_map(base_snapshot, ruleset)
        entries = _relabel_species_abilities(entries, abilities_map)
    return _annotate_target_fields(entries, overlay)


def target_abilities(
    target: Target,
    ruleset: Ruleset,
    state: TargetState,
    base_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Per-Target abilities backdrop: ``build_abilities(build_snapshot(target), ruleset)``.

    For Essentials targets, ability display names are relabeled to canonical
    English using the base snapshot ⊕ Ruleset name map (keyed by chrooked_id).
    Pass ``base_snapshot`` to enable the relabeling.
    """
    snapshot = state.snapshot_for(target)
    entries = dexmod.build_abilities(snapshot, ruleset)
    if target.engine in ("essentials", "rejuv") and base_snapshot is not None:
        english_map = _english_abilities_map(base_snapshot, ruleset)
        entries = _relabel_names(entries, english_map)
        # #44: overlay the canonical English description by chrooked_id.
        description_map = _english_ability_descriptions(base_snapshot, ruleset)
        entries = _relabel_descriptions(entries, description_map)
    return entries


# Behavior fields the Essentials / Rejuv readers never parse — those games keep
# them in engine code (function codes, priority tables), not in the data the
# snapshot reads. Left unfilled they merge through as `null`, which the moves
# table then PUTs back verbatim: `int(None)` blows up on save, and a payload that
# did land would overwrite a real priority/effect with an empty one. Fall back to
# the canon base entry so the backdrop tells the truth and round-trips.
_UNPARSED_MOVE_FIELDS = (
    "effect", "argument", "additional_effects", "flags", "priority", "target",
)


def _fill_unparsed_moves(
    snapshot: dict[str, Any], base_snapshot: dict[str, Any]
) -> dict[str, Any]:
    """A copy of `snapshot` whose moves borrow unparsed fields from canon."""
    base_moves = base_snapshot.get("moves", {})
    moves = {}
    for chrooked_id, entry in snapshot.get("moves", {}).items():
        canon = base_moves.get(chrooked_id, {})
        borrowed = {
            field: canon[field]
            for field in _UNPARSED_MOVE_FIELDS
            if entry.get(field) is None and canon.get(field) is not None
        }
        moves[chrooked_id] = {**entry, **borrowed} if borrowed else entry
    return {**snapshot, "moves": moves}


def target_moves(
    target: Target,
    ruleset: Ruleset,
    state: TargetState,
    base_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Per-Target moves backdrop: ``build_moves(build_snapshot(target), ruleset)``.

    For Essentials targets, move display names are relabeled to canonical
    English using the base snapshot ⊕ Ruleset name map (keyed by chrooked_id),
    and behavior fields the reader cannot see fall back to canon.
    Pass ``base_snapshot`` to enable both.
    """
    snapshot = state.snapshot_for(target)
    if base_snapshot is not None:
        snapshot = _fill_unparsed_moves(snapshot, base_snapshot)
    entries = dexmod.build_moves(snapshot, ruleset)
    if target.engine in ("essentials", "rejuv") and base_snapshot is not None:
        english_map = _english_moves_map(base_snapshot, ruleset)
        entries = _relabel_names(entries, english_map, prefer_internal=True)
        # #44: overlay the canonical English description by chrooked_id.
        description_map = _english_move_descriptions(base_snapshot, ruleset)
        entries = _relabel_descriptions(entries, description_map)
    return entries


_DIALECT_LABELS: dict[str, str] = {
    "essentials16": "16.2",
    "essentials21": "v19+ (modern)",
}


def target_dialect(target: Target) -> dict[str, str | None]:
    """Detect the Essentials PBS dialect of a registered Target.

    Calls ``detect_dialect`` fresh on each request so the badge reflects the
    current on-disk state of the target (never stale). Only meaningful for
    engine='essentials'; pokeemerald targets return ``None`` for both fields.

    Returns a dict with keys:
      ``dialect`` — ``"essentials16"``, ``"essentials21"``, or ``None``
      ``label``   — display label ("16.2", "v19+ (modern)"), or ``None``
    """
    if target.engine != "essentials":
        return {"dialect": None, "label": None}
    dialect = _detect_dialect(Path(target.path))
    label = _DIALECT_LABELS.get(dialect) if dialect is not None else None
    return {"dialect": dialect, "label": label}


def target_type_chart(
    target: Target, ruleset: Ruleset, state: TargetState
) -> list[dict[str, Any]]:
    """Per-Target type-chart backdrop: ``build_type_chart(build_snapshot(target), ruleset)``.

    The same shape as ``target_dex`` / ``target_abilities`` / ``target_moves``:
    the fork's own base type matrix comes from the cached per-Target snapshot (D2),
    then the type-chart merge overlays the Ruleset per cell — so the backdrop
    reuses the snapshot population + merge wholesale.
    """
    snapshot = state.snapshot_for(target)
    return dexmod.build_type_chart(snapshot, ruleset)
