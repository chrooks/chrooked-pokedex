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
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from ..appliers.dispatch import route_apply as _route_apply
from ..appliers.essentials.dialect import detect_dialect as _detect_dialect
from ..appliers.pokeemerald.git_guard import DirtyWorkingTree, require_clean_git_status
from ..model import Ruleset
from ..report import ApplyReport
from . import dex as dexmod
from . import snapshot as snapmod
from . import snapshot_essentials as snapmod_essentials

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
        if engine not in ("pokeemerald", "essentials"):
            raise TargetError(422, f"Unknown engine {engine!r}.")
        # pokeemerald targets must be git repos (preview-restore is git-based).
        # essentials targets may be plain directories (non-git Essentials games).
        if engine == "pokeemerald" and not (resolved / ".git").exists():
            raise TargetError(422, f"Target path is not a git repo: {resolved}")
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

    Delegates to ``appliers/dispatch.py::route_apply`` so the web path and the
    CLI dispatch identically (D-DRY).  An unrecognized Essentials format writes
    nothing and records a ``blocked`` entry — the existing honest Error State.
    Preview's git revert (D1) is engine-agnostic and runs in the caller's
    ``finally`` block regardless of which applier ran.
    """
    report = ApplyReport()
    _route_apply(target, engine, ruleset, report)
    return report


# --- Orchestration -------------------------------------------------------- #


def preview_target(
    target: Target, ruleset: Ruleset, state: TargetState
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
    fork = Path(target.path)
    lock = state.lock_for(target.path)
    with lock:
        is_git = _is_git_repo(fork)

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

        applier_error: BaseException | None = None
        try:
            report = _run_applier(fork, target.engine, ruleset)
            return _report_payload(report)
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
    target: Target, ruleset: Ruleset, state: TargetState, force: bool
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
    lock = state.lock_for(target.path)
    with lock:
        if _is_git_repo(fork):
            try:
                require_clean_git_status(fork, force=force)
            except DirtyWorkingTree as error:
                raise TargetError(409, str(error)) from error
        report = _run_applier(fork, target.engine, ruleset)
        report.write(fork / "apply-report.md")
        state.invalidate_snapshot(target.path)
        return _report_payload(report)


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


def _relabel_names(
    entries: list[dict[str, Any]],
    english_map: dict[str, str],
) -> list[dict[str, Any]]:
    """Return a new list with each entry's 'name' replaced by its English canonical.

    Priority:
    1. Canonical English from base ⊕ Ruleset (by chrooked_id).
    2. Prettified InternalName — the entry's existing ``internal`` field if
       present, else derived from the chrooked_id as a best-effort fallback.

    All other fields are left unchanged; only the display ``name`` changes.
    """
    result = []
    for entry in entries:
        chrooked_id = entry.get("chrooked_id", "")
        english_name = english_map.get(chrooked_id)
        if english_name is None:
            # Fallback: prettify the InternalName (or derive from chrooked_id).
            raw_internal = entry.get("internal") or chrooked_id
            english_name = _prettify_internal_name(raw_internal)
        result.append({**entry, "name": english_name})
    return result


def target_dex(
    target: Target,
    ruleset: Ruleset,
    state: TargetState,
    base_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Per-Target dex backdrop: ``build_dex(build_snapshot(target), ruleset)``.

    For Essentials targets, species display names are relabeled to canonical
    English using the base snapshot ⊕ Ruleset name map (keyed by chrooked_id).
    Pass ``base_snapshot`` to enable the relabeling; omitting it skips the
    relabel (pokeemerald targets and tests that don't inject the base).
    """
    snapshot = state.snapshot_for(target)
    entries = dexmod.build_dex(snapshot, ruleset)
    if target.engine == "essentials" and base_snapshot is not None:
        english_map = _english_species_map(base_snapshot, ruleset)
        entries = _relabel_names(entries, english_map)
    return entries


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
    if target.engine == "essentials" and base_snapshot is not None:
        english_map = _english_abilities_map(base_snapshot, ruleset)
        entries = _relabel_names(entries, english_map)
    return entries


def target_moves(
    target: Target,
    ruleset: Ruleset,
    state: TargetState,
    base_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Per-Target moves backdrop: ``build_moves(build_snapshot(target), ruleset)``.

    For Essentials targets, move display names are relabeled to canonical
    English using the base snapshot ⊕ Ruleset name map (keyed by chrooked_id).
    Pass ``base_snapshot`` to enable the relabeling.
    """
    snapshot = state.snapshot_for(target)
    entries = dexmod.build_moves(snapshot, ruleset)
    if target.engine == "essentials" and base_snapshot is not None:
        english_map = _english_moves_map(base_snapshot, ruleset)
        entries = _relabel_names(entries, english_map)
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
