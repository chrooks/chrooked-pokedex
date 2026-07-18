"""Install behavior battle code into a Rejuv target's ``patch/Mods/``.

Canonical implementations live in the repo at ``references/rejuv-harness/``:
``chrooked_00_core.rb`` (the prepend wrappers + registry tables) plus one
``chrooked_<id>.rb`` per behavior, each appending one table entry. The game
loads ``patch/Mods/*.rb`` after all base scripts, so the core's
``Module#prepend`` wrappers take effect without touching base files.

Honesty Invariant (mirrors essentials162's ``behavior_install.py``): the
``DATA ONLY`` warning may only disappear when the mechanic is genuinely
installed —

  * source present + tagged ``# chrooked:<id>``  -> copy, report ``applied``;
  * source absent                                -> nothing (abiltext keeps its
    honest DATA-ONLY line);
  * source present but empty/untagged            -> ``blocked``, copy nothing.

The core is copied whenever at least one behavior installs — a behavior file
without the core's tables would NameError at boot.
"""

from __future__ import annotations

from pathlib import Path

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry

# src/chrooked_pokedex/appliers/rejuv/ -> repo root.
_DEFAULT_SOURCE_DIR = Path(__file__).resolve().parents[4] / "references" / "rejuv-harness"
_CORE_NAME = "chrooked_00_core.rb"


def install_behaviors(
    target: Path,
    ruleset: Ruleset,
    report: ApplyReport,
    *,
    source_dir: Path | None = None,
) -> set[Path]:
    """Copy the core + every valid behavior implementation; report honestly."""
    source_dir = source_dir or _DEFAULT_SOURCE_DIR
    mods_dir = target / "patch" / "Mods"
    written: set[Path] = set()

    any_installed = False
    for chrooked_id in sorted(ruleset.behaviors):
        src = source_dir / f"chrooked_{chrooked_id}.rb"
        if not src.exists():
            continue  # not implemented — abiltext keeps the honest DATA-ONLY line
        try:
            contents = src.read_text(encoding="utf-8")
        except OSError as exc:
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id,
                reason=f"implementation unreadable: {src}: {exc}",
            ))
            continue
        if not _is_valid(contents, chrooked_id):
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id,
                reason=f"implementation invalid (empty or missing '# chrooked:{chrooked_id}' tag): {src}",
            ))
            continue
        dest = mods_dir / f"chrooked_{chrooked_id}.rb"
        try:
            mods_dir.mkdir(parents=True, exist_ok=True)
            dest.write_text(contents, encoding="utf-8")
        except OSError as exc:
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id,
                reason=f"implementation copy failed: {dest}: {exc}",
            ))
            continue
        any_installed = True
        written.add(dest)
        report.add(ReportEntry(
            status="applied", category="behavior", chrooked_id=chrooked_id,
            reason=f"mechanic installed (patch/Mods/chrooked_{chrooked_id}.rb)",
        ))

    if any_installed:
        core_src = source_dir / _CORE_NAME
        core_dest = mods_dir / _CORE_NAME
        try:
            core_dest.write_text(core_src.read_text(encoding="utf-8"), encoding="utf-8")
            written.add(core_dest)
        except OSError as exc:
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id="(core)",
                reason=f"core copy failed: {core_src}: {exc} — installed behaviors will not run",
            ))
    return written


def _is_valid(contents: str, chrooked_id: str) -> bool:
    return bool(contents.strip()) and f"# chrooked:{chrooked_id}" in contents


def has_implementation(chrooked_id: str, source_dir: Path | None = None) -> bool:
    """True if a VALID implementation exists — the 'will install' marker.

    Validity is part of the marker so abiltext never drops DATA ONLY for a file
    the installer would block.
    """
    source_dir = source_dir or _DEFAULT_SOURCE_DIR
    src = source_dir / f"chrooked_{chrooked_id}.rb"
    if not src.exists():
        return False
    try:
        return _is_valid(src.read_text(encoding="utf-8"), chrooked_id)
    except OSError:
        return False
