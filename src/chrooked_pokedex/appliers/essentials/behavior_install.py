"""Install ported Essentials 21 mechanics into a target game (mjolnir NV-5).

The v21 counterpart of `essentials162/behavior_install.py`. A ported mechanic is
a standalone Ruby file `chrooked_<id>.rb` that adds one entry to an Essentials 21
handler registry (e.g. `Battle::AbilityEffects::DamageCalcFromUser`). The
canonical copies live in the repo at `references/essentials21-harness/`.

Essentials 21 loads every `.rb` under `Data/Scripts/` in name order, files before
folders, so the install home is `Data/Scripts/998_ChrookedMods/`: after the
game's own battle code defines the registries, before `999_Main` starts the game.
No loader asset is needed, unlike 16.2, where a preload shim loaded the plugins.

The dex owns that folder. Installs are idempotent (an unchanged file is not
rewritten and gets no report line), and a `chrooked_*.rb` there with no valid
port behind it is removed and reported, so a deploy that mirrors the folder never
ships a stale mechanic. Nothing else under `Data/Scripts/` is touched: a game's
own `998_*` folders (thor's controls shim, the lab's scripts) stay as they are.

The honesty Invariant is the same as 16.2's: a created ability's `DATA ONLY`
line disappears only when its mechanic is genuinely installed. A port that is
empty or lacks its `# chrooked:<id>` tag is reported `blocked` and never copied.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry

# The repo's canonical port home: src/chrooked_pokedex/appliers/essentials/ -> repo root.
_DEFAULT_SOURCE_DIR = Path(__file__).resolve().parents[4] / "references" / "essentials21-harness"

# Where ports land in the target, relative to the game root.
MODS_DIR = Path("Data") / "Scripts" / "998_ChrookedMods"


def install_behaviors(
    target: Path,
    ruleset: Ruleset,
    report: ApplyReport,
    *,
    source_dir: Path | None = None,
) -> set[Path]:
    """Install every ported mechanic that has a valid port; remove stale ones.

    Returns the set of target paths written or removed.
    """
    source_dir = source_dir or _DEFAULT_SOURCE_DIR
    mods_dir = target / MODS_DIR
    changed: set[Path] = set()
    wanted: set[str] = set()

    for chrooked_id in sorted(ruleset.behaviors):
        port = source_dir / f"chrooked_{chrooked_id}.rb"
        if not port.exists():
            continue  # not ported - the ability-create path keeps its honest DATA ONLY line
        try:
            contents = port.read_text(encoding="utf-8")
        except OSError as exc:
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id,
                reason=f"port source unreadable: {port}: {exc}",
            ))
            continue
        if not _is_valid_port(contents, chrooked_id):
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id,
                reason=f"port source invalid (empty or missing '# chrooked:{chrooked_id}' tag): {port}",
            ))
            continue
        dest = mods_dir / port.name
        wanted.add(dest.name)
        if _already_installed(dest, contents):
            continue  # no churn, no report line
        try:
            mods_dir.mkdir(parents=True, exist_ok=True)
            dest.write_text(contents, encoding="utf-8")
        except OSError as exc:
            wanted.discard(dest.name)
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id,
                reason=f"port copy failed: {dest}: {exc}",
            ))
            continue
        changed.add(dest)
        report.add(ReportEntry(
            status="applied", category="behavior", chrooked_id=chrooked_id,
            reason=f"mechanic installed ({MODS_DIR.as_posix()}/{dest.name})",
        ))

    changed |= _remove_stale(mods_dir, wanted, report)
    return changed


def _remove_stale(mods_dir: Path, wanted: set[str], report: ApplyReport) -> set[Path]:
    """Delete `chrooked_*.rb` files in the dex-owned folder that no valid port backs."""
    removed: set[Path] = set()
    if not mods_dir.is_dir():
        return removed
    for path in sorted(mods_dir.glob("chrooked_*.rb")):
        if path.name in wanted:
            continue
        chrooked_id = path.stem.removeprefix("chrooked_")
        try:
            path.unlink()
        except OSError as exc:
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id,
                reason=f"stale port could not be removed: {path}: {exc}",
            ))
            continue
        removed.add(path)
        report.add(ReportEntry(
            status="applied", category="behavior", chrooked_id=chrooked_id,
            reason=f"mechanic uninstalled — no valid port or no behavior spec ({MODS_DIR.as_posix()}/{path.name})",
        ))
    return removed


def _already_installed(dest: Path, contents: str) -> bool:
    """True if the target already holds byte-identical contents (skip the write)."""
    if not dest.exists():
        return False
    try:
        return dest.read_text(encoding="utf-8") == contents
    except OSError:
        return False


def _is_valid_port(contents: str, chrooked_id: str) -> bool:
    """A valid port is non-empty and self-identifies with its `# chrooked:<id>` tag."""
    return bool(contents.strip()) and f"# chrooked:{chrooked_id}" in contents


def has_plugin(chrooked_id: str, source_dir: Path | None = None) -> bool:
    """True if a VALID captured port exists for this mechanic.

    Validity is part of the marker so the create path never promises "installed"
    for a port the installer would reject as blocked.
    """
    source_dir = source_dir or _DEFAULT_SOURCE_DIR
    port = source_dir / f"chrooked_{chrooked_id}.rb"
    if not port.exists():
        return False
    try:
        return _is_valid_port(port.read_text(encoding="utf-8"), chrooked_id)
    except OSError:
        return False
