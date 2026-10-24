"""The static-mod catalogs and their per-Target switches.

Static mods are self-contained Ruby that is not a Ruleset behavior. On Rejuv they
are ``references/rejuv-harness/chrooked_zz_<id>.rb`` (QoL hotkeys, form
switchers, Kirin shims). On Essentials 21 (Nova) the one static mod is generated,
Redux Mode (``behavior/redux.py``), and the behavior installer writes it.
Each file describes itself in structured header lines right under its
``# chrooked:`` tag — the file is the one home for its own metadata:

    # mod-group: convenience | form | battle | shim | diagnostic
    # mod-summary: one line, what the player sees
    # mod-needs: debug            (optional; comma-separated mod ids)
    # mod-locked: <why>           (optional; the mod cannot be turned off)

Install honors the Target's off list (``model/mods.py``). A turned-off mod's
file is REMOVED from the mods folder — otherwise the switch would lie, since
Rejuv's apply never prunes anything else. Nothing is dropped silently: every off,
dependency block, or bad id becomes an Apply Report entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..behavior import redux
from ..report import ApplyReport, ReportEntry

PREFIX = "chrooked_zz_"
GROUPS = ("convenience", "form", "battle", "shim", "diagnostic")


@dataclass(frozen=True)
class StaticMod:
    id: str
    file: str
    group: str
    summary: str
    needs: tuple[str, ...]
    locked: str | None
    header: str  # the full leading comment block, '# ' stripped


def _parse(name: str, text: str) -> StaticMod:
    mod_id = Path(name).stem.removeprefix(PREFIX)
    header: list[str] = []
    for line in text.splitlines():
        if not line.startswith("#"):
            if header:
                break
            continue
        header.append(line[1:].removeprefix(" "))
    fields: dict[str, str] = {}
    for line in header:
        key, sep, value = line.partition(":")
        if sep and key.startswith("mod-"):
            fields[key] = value.strip()
    group = fields.get("mod-group", "")
    if group not in GROUPS or not fields.get("mod-summary"):
        raise ValueError(
            f"{name}: needs '# mod-group: <{'|'.join(GROUPS)}>' and "
            "'# mod-summary: ...' header lines"
        )
    needs = tuple(n.strip() for n in fields.get("mod-needs", "").split(",") if n.strip())
    return StaticMod(
        id=mod_id, file=name, group=group, summary=fields["mod-summary"],
        needs=needs, locked=fields.get("mod-locked") or None,
        header="\n".join(header),
    )


def catalog(source_dir: Path) -> list[StaticMod]:
    """Every Rejuv static mod in ``source_dir``, sorted by file name (= load order)."""
    return [_parse(p.name, p.read_text(encoding="utf-8"))
            for p in sorted(Path(source_dir).glob(f"{PREFIX}*.rb"))]


# Essentials 21's static mods: file name -> its generated text.
_ESSENTIALS21 = {redux.FILE: redux.render_essentials21}


def essentials21_catalog() -> list[StaticMod]:
    """Every Essentials 21 static mod (Redux Mode)."""
    return [_parse(name, render()) for name, render in sorted(_ESSENTIALS21.items())]


def essentials21_text(mod: StaticMod) -> str:
    return _ESSENTIALS21[mod.file]()


def catalog_for(engine: str, source_dir: Path) -> list[StaticMod] | None:
    """The engine's static mods; None for an engine with none.
    ponytail: "essentials" means v21; a 16.x Target lists Redux but never installs it."""
    if engine == "rejuv":
        return catalog(source_dir)
    if engine == "essentials":
        return essentials21_catalog()
    return None


def select(
    mods: list[StaticMod],
    target: Path,
    mods_dir: Path,
    report: ApplyReport,
    off: frozenset[str] = frozenset(),
) -> list[StaticMod]:
    """The mods to install into ``target / mods_dir``. Reports each unknown id,
    locked or blocked mod, and removes the file of each mod that is off or blocked."""
    by_id = {m.id: m for m in mods}

    for unknown in sorted(off - by_id.keys()):
        report.add(ReportEntry(
            status="blocked", category="mods", chrooked_id=unknown,
            reason="mods.yaml turns off a mod that does not exist; fix the id",
        ))

    def is_on(mod: StaticMod) -> bool:
        return mod.locked is not None or mod.id not in off

    chosen: list[StaticMod] = []
    for mod in mods:
        dest = target / mods_dir / mod.file
        missing = [n for n in mod.needs if n not in by_id or not is_on(by_id[n])]
        if mod.id in off and mod.locked:
            report.add(ReportEntry(
                status="blocked", category="mods", chrooked_id=mod.id, symbol=mod.file,
                reason=f"cannot turn off ({mod.locked}); installed anyway",
            ))
        if not is_on(mod) or missing:
            removed = dest.exists()
            dest.unlink(missing_ok=True)
            note = f"; removed {(mods_dir / mod.file).as_posix()}" if removed else ""
            if missing:
                report.add(ReportEntry(
                    status="blocked", category="mods", chrooked_id=mod.id, symbol=mod.file,
                    reason=f"needs {', '.join(missing)}, which is off{note}",
                ))
            else:
                report.add(ReportEntry(
                    status="held", category="mods", chrooked_id=mod.id, symbol=mod.file,
                    reason=f"turned off for this Target{note}",
                ))
            continue
        chosen.append(mod)
    return chosen


def install(
    target: Path,
    source_dir: Path,
    report: ApplyReport,
    off: frozenset[str] = frozenset(),
) -> set[Path]:
    """Copy each Rejuv mod that is on into ``patch/Mods/``; remove each mod that is off."""
    mods_dir = target / "patch" / "Mods"
    written: set[Path] = set()
    for mod in select(catalog(source_dir), target, Path("patch") / "Mods", report, off):
        dest = mods_dir / mod.file
        mods_dir.mkdir(parents=True, exist_ok=True)
        dest.write_text((Path(source_dir) / mod.file).read_text(encoding="utf-8"), encoding="utf-8")
        written.add(dest)
    return written
