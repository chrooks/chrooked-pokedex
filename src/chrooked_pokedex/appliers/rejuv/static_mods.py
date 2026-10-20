"""The Rejuv static-mod catalog and its per-Target installer.

Static mods are ``references/rejuv-harness/chrooked_zz_<id>.rb``: self-contained
Ruby that is not a Ruleset behavior (QoL hotkeys, form switchers, Kirin shims).
Each file describes itself in structured header lines right under its
``# chrooked:`` tag — the file is the one home for its own metadata:

    # mod-group: convenience | form | battle | shim | diagnostic
    # mod-summary: one line, what the player sees
    # mod-needs: debug            (optional; comma-separated mod ids)
    # mod-locked: <why>           (optional; the mod cannot be turned off)

Install honors the Target's off list (``model/mods.py``). A turned-off mod's
file is REMOVED from ``patch/Mods/`` — otherwise the switch would lie, since
apply never prunes anything else. Nothing is dropped silently: every off,
dependency block, or bad id becomes an Apply Report entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...report import ApplyReport, ReportEntry

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


def _parse(path: Path) -> StaticMod:
    mod_id = path.stem.removeprefix(PREFIX)
    header: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
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
            f"{path.name}: needs '# mod-group: <{'|'.join(GROUPS)}>' and "
            "'# mod-summary: ...' header lines"
        )
    needs = tuple(n.strip() for n in fields.get("mod-needs", "").split(",") if n.strip())
    return StaticMod(
        id=mod_id, file=path.name, group=group, summary=fields["mod-summary"],
        needs=needs, locked=fields.get("mod-locked") or None,
        header="\n".join(header),
    )


def catalog(source_dir: Path) -> list[StaticMod]:
    """Every static mod in ``source_dir``, sorted by file name (= load order)."""
    return [_parse(p) for p in sorted(Path(source_dir).glob(f"{PREFIX}*.rb"))]


def install(
    target: Path,
    source_dir: Path,
    report: ApplyReport,
    off: frozenset[str] = frozenset(),
) -> set[Path]:
    """Copy each mod that is on into ``patch/Mods/``; remove each mod that is off."""
    mods = catalog(source_dir)
    by_id = {m.id: m for m in mods}
    mods_dir = target / "patch" / "Mods"

    for unknown in sorted(off - by_id.keys()):
        report.add(ReportEntry(
            status="blocked", category="mods", chrooked_id=unknown,
            reason="mods.yaml turns off a mod that does not exist; fix the id",
        ))

    def is_on(mod: StaticMod) -> bool:
        return mod.locked is not None or mod.id not in off

    written: set[Path] = set()
    for mod in mods:
        dest = mods_dir / mod.file
        missing = [n for n in mod.needs if n not in by_id or not is_on(by_id[n])]
        if mod.id in off and mod.locked:
            report.add(ReportEntry(
                status="blocked", category="mods", chrooked_id=mod.id, symbol=mod.file,
                reason=f"cannot turn off ({mod.locked}); installed anyway",
            ))
        if not is_on(mod) or missing:
            removed = dest.exists()
            dest.unlink(missing_ok=True)
            note = f"; removed patch/Mods/{mod.file}" if removed else ""
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
        mods_dir.mkdir(parents=True, exist_ok=True)
        dest.write_text((Path(source_dir) / mod.file).read_text(encoding="utf-8"), encoding="utf-8")
        written.add(dest)
    return written
