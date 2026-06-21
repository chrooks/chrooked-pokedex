"""Install ported Essentials 16.2 mechanics into a target game (issue #16).

A ported mechanic is a standalone Ruby plugin `Scripts/chrooked_<id>.rb`. The
canonical copies live in the repo at `references/essentials-harness/`. This
installer copies them into the target so `apply --engine essentials` does not
just write ability *data* and warn `DATA ONLY`, but actually puts the working
mechanic in the game.

The honesty Invariant (issue #16): the `DATA ONLY` warning may only disappear
when the mechanic is genuinely installed. So:

  * plugin source present + valid -> copy it in, report `applied` ("installed");
  * plugin source absent        -> do nothing (the ability-create path keeps its
    honest DATA-ONLY line);
  * plugin source present but invalid (empty / not tagged `# chrooked:<id>`)
    -> report `blocked` and copy nothing — never silently quiet the warning.

A plugin does nothing without the loader (`mkxp.json` + `Scripts/load_order_shim.rb`),
so the installer also ensures those assets exist in the target — otherwise an
"installed" plugin would never execute, which would itself break the Invariant.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry

# The repo's canonical plugin/loader home: src/chrooked_pokedex/appliers/essentials162/ -> repo root.
_DEFAULT_SOURCE_DIR = Path(__file__).resolve().parents[4] / "references" / "essentials-harness"

# Loader assets and where they land in the target (relative to target root).
_LOADER_ASSETS = (
    ("mkxp.json", Path("mkxp.json")),
    ("load_order_shim.rb", Path("Scripts") / "load_order_shim.rb"),
)


def install_behaviors(
    target: Path,
    ruleset: Ruleset,
    report: ApplyReport,
    *,
    source_dir: Path | None = None,
) -> set[Path]:
    """Install every ported mechanic that has a captured plugin; report honestly.

    Returns the set of target paths written (plugins + any loader assets copied).
    """
    source_dir = source_dir or _DEFAULT_SOURCE_DIR
    scripts_dir = target / "Scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    written: set[Path] = set()

    any_present = False
    for chrooked_id in sorted(ruleset.behaviors):
        plugin = source_dir / f"chrooked_{chrooked_id}.rb"
        if not plugin.exists():
            continue  # not ported — the ability-create path keeps the honest DATA-ONLY line
        try:
            contents = plugin.read_text(encoding="utf-8")
        except OSError as exc:
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id,
                reason=f"plugin source unreadable: {plugin}: {exc}",
            ))
            continue
        if not _is_valid_plugin(contents, chrooked_id):
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id,
                reason=f"plugin source invalid (empty or missing '# chrooked:{chrooked_id}' tag): {plugin}",
            ))
            continue
        dest = scripts_dir / f"chrooked_{chrooked_id}.rb"
        any_present = True  # a valid port exists -> ensure the loader regardless of churn
        if _already_installed(dest, contents):
            continue  # no churn, no report line (mirrors the ability-edit no-churn pattern)
        try:
            dest.write_text(contents, encoding="utf-8")
        except OSError as exc:
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id,
                reason=f"plugin copy failed: {dest}: {exc}",
            ))
            continue
        written.add(dest)
        report.add(ReportEntry(
            status="applied", category="behavior", chrooked_id=chrooked_id,
            reason=f"mechanic installed (Scripts/chrooked_{chrooked_id}.rb)",
        ))

    # A plugin without the loader never runs — ensure the loader assets whenever a
    # valid port is present (idempotent; only copies if absent). A copy failure is
    # reported, never silent: an installed plugin with no loader would not fire.
    if any_present:
        written |= _ensure_loader_assets(target, source_dir, report)
    return written


def _already_installed(dest: Path, contents: str) -> bool:
    """True if the target already holds byte-identical contents (skip the write)."""
    if not dest.exists():
        return False
    try:
        return dest.read_text(encoding="utf-8") == contents
    except OSError:
        return False


def _is_valid_plugin(contents: str, chrooked_id: str) -> bool:
    """A valid plugin is non-empty and self-identifies with its `# chrooked:<id>` tag."""
    return bool(contents.strip()) and f"# chrooked:{chrooked_id}" in contents


def _ensure_loader_assets(target: Path, source_dir: Path, report: ApplyReport) -> set[Path]:
    """Copy mkxp.json + load_order_shim.rb into the target if missing. Idempotent.

    A copy failure is reported as blocked, never silent — a plugin with no loader
    never executes, which would break the honesty Invariant.
    """
    written: set[Path] = set()
    for source_name, rel_dest in _LOADER_ASSETS:
        src = source_dir / source_name
        dest = target / rel_dest
        if dest.exists() or not src.exists():
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
        except OSError as exc:
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id="(loader)",
                reason=f"loader asset copy failed: {dest}: {exc} — installed plugins will not run",
            ))
            continue
        written.add(dest)
    return written


def has_plugin(chrooked_id: str, source_dir: Path | None = None) -> bool:
    """True if a VALID captured plugin exists for this mechanic — the 'ported' marker (Q6).

    Validity (non-empty + correct `# chrooked:<id>` tag) is part of the marker so the
    ability-create path never promises "installed" for a plugin the installer would
    reject as blocked — that would break the honesty Invariant.
    """
    source_dir = source_dir or _DEFAULT_SOURCE_DIR
    plugin = source_dir / f"chrooked_{chrooked_id}.rb"
    if not plugin.exists():
        return False
    try:
        return _is_valid_plugin(plugin.read_text(encoding="utf-8"), chrooked_id)
    except OSError:
        return False
