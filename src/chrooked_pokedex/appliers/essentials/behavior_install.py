"""Install ported Essentials 21 mechanics into a target game (mjolnir NV-5, NV-8).

The v21 counterpart of `essentials162/behavior_install.py`. A ported mechanic is
a standalone Ruby file `chrooked_<id>.rb` that adds one entry to an Essentials 21
handler registry (e.g. `Battle::AbilityEffects::DamageCalcFromUser`). It comes
from one of two places:

  * generated: the behavior spec has a `template:` block, and
    `behavior.templates.render_essentials21` writes the port against this target's
    own names (its PBS, through the ResolutionMap);
  * hand-written: a mechanic that fits no template keeps a captured port in the
    repo at `references/essentials21-harness/`.

A spec with both is ambiguous and is `blocked` rather than guessed at. A composed
ability (`behaviors: [carnivore, strongjaw]`, NV-15) gets a file of its own,
`chrooked_<ability>.rb`, that gives it its parts' handlers (`behavior.compose`).

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
line disappears only when its mechanic is genuinely installed (`has_port`). A
hand port that is empty or lacks its `# chrooked:<id>` tag, or a template that
names something this target lacks, is reported `blocked` and never written.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Callable, Optional

from ...behavior import compose, templates
from ...model import Ruleset
from ...model.behavior_spec import BehaviorSpec
from ...model.schema import AbilityDef, is_composed
from ...report import ApplyReport, ReportEntry
from .resolution import ResolutionMap, build_resolution_map

# The repo's canonical port home: src/chrooked_pokedex/appliers/essentials/ -> repo root.
_DEFAULT_SOURCE_DIR = Path(__file__).resolve().parents[4] / "references" / "essentials21-harness"

# Where ports land in the target, relative to the game root.
MODS_DIR = Path("Data") / "Scripts" / "998_ChrookedMods"


def install_behaviors(
    target: Path,
    ruleset: Ruleset,
    report: ApplyReport,
    *,
    resmap: ResolutionMap | None = None,
    source_dir: Path | None = None,
) -> set[Path]:
    """Install every mechanic that has a valid port; remove stale ones.

    `resmap` resolves a template's names against this target; the apply passes the
    one it already built (holding the abilities it just created). Without it, one
    is built from the target's PBS the first time a template needs it.
    Returns the set of target paths written or removed.
    """
    source_dir = source_dir or _DEFAULT_SOURCE_DIR
    mods_dir = target / MODS_DIR
    changed: set[Path] = set()
    wanted: set[str] = set()

    @functools.cache
    def names() -> ResolutionMap:
        return resmap if resmap is not None else build_resolution_map(target, ruleset)

    def install(chrooked_id: str, contents: Optional[str]) -> None:
        if contents is None:
            return  # not ported - the ability-create path keeps its honest DATA ONLY line
        dest = mods_dir / f"chrooked_{chrooked_id}.rb"
        wanted.add(dest.name)
        if _already_installed(dest, contents):
            return  # no churn, no report line
        try:
            mods_dir.mkdir(parents=True, exist_ok=True)
            dest.write_text(contents, encoding="utf-8")
        except OSError as exc:
            wanted.discard(dest.name)
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id,
                reason=f"port copy failed: {dest}: {exc}",
            ))
            return
        changed.add(dest)
        report.add(ReportEntry(
            status="applied", category="behavior", chrooked_id=chrooked_id,
            reason=f"mechanic installed ({MODS_DIR.as_posix()}/{dest.name})",
        ))

    for chrooked_id in sorted(ruleset.behaviors):
        try:
            install(chrooked_id, _port_text(ruleset.behaviors[chrooked_id], source_dir, names))
        except _Blocked as exc:
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id, reason=str(exc),
            ))

    # A composed ability (NV-15) gets its own file, which wires its parts' handlers.
    abilities = getattr(ruleset, "abilities", {})
    for chrooked_id in sorted(abilities):
        ability = abilities[chrooked_id]
        if not is_composed(ability):
            continue
        if f"chrooked_{chrooked_id}.rb" in wanted:
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id,
                reason=f"composition not installed: a behavior port already uses chrooked_{chrooked_id}.rb",
            ))
            continue
        try:
            install(chrooked_id, compose.render_essentials21(ability, ruleset, names()))
        except compose.CompositionError as exc:
            report.add(ReportEntry(
                status="blocked", category="behavior", chrooked_id=chrooked_id,
                reason=f"composition not generated: {exc}",
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


def has_port(spec: BehaviorSpec, resmap: ResolutionMap, source_dir: Path | None = None) -> bool:
    """True if `install_behaviors` would install this mechanic on the target `resmap`
    describes: its template renders there, or it has a valid hand-written port (and
    not both).

    The create path asks this before it drops DATA ONLY, so it never promises
    "installed" for a port the installer would block, e.g. a template whose probe
    names a move this game lacks.
    """
    try:
        return _port_text(spec, source_dir or _DEFAULT_SOURCE_DIR, lambda: resmap) is not None
    except _Blocked:
        return False


def has_composition(ability: AbilityDef, ruleset: Ruleset, resmap: ResolutionMap) -> bool:
    """True if `install_behaviors` would install this composed ability's file on the
    target `resmap` describes (NV-15): every part can be composed and proven there."""
    if not is_composed(ability):
        return False
    own = ruleset.behaviors.get(ability.chrooked_id)
    if own is not None and has_port(own, resmap):
        return False  # its own port holds chrooked_<id>.rb, as the installer finds
    try:
        return compose.render_essentials21(ability, ruleset, resmap) is not None
    except compose.CompositionError:
        return False


class _Blocked(Exception):
    """A mechanic that has a port source the installer must refuse; the message is the reason."""


def _port_text(spec: BehaviorSpec, source_dir: Path, names: Callable[[], ResolutionMap]) -> Optional[str]:
    """The port this mechanic installs: rendered from its template, or its captured
    hand-written file. None when it has neither (not ported). Raises _Blocked."""
    chrooked_id = spec.chrooked_id
    port = source_dir / f"chrooked_{chrooked_id}.rb"
    if getattr(spec, "template", None) is not None:
        if port.exists():
            raise _Blocked(
                f"ambiguous port: ruleset/behaviors/{chrooked_id}.yaml has a template AND "
                f"{port} is a hand-written port; keep one")
        try:
            return templates.render_essentials21(spec, names())
        except templates.TemplateError as exc:
            raise _Blocked(f"port not generated: {exc}") from exc
    if not port.exists():
        return None
    try:
        contents = port.read_text(encoding="utf-8")
    except OSError as exc:
        raise _Blocked(f"port source unreadable: {port}: {exc}") from exc
    if not _is_valid_port(contents, chrooked_id):
        raise _Blocked(f"port source invalid (empty or missing '# chrooked:{chrooked_id}' tag): {port}")
    return contents
