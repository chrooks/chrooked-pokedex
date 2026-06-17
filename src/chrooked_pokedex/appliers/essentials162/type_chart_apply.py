"""Apply type-chart Overrides into a 16.2 `types.txt`'s effectiveness buckets.

The 16.2 analogue of `appliers/essentials/type_chart_apply.py`. Effectiveness is
stored per type, on the DEFENDER, as three comma-list buckets — `Weaknesses` (2x),
`Resistances` (0.5x), `Immunities` (0x) — of attacking type internals. An
attacker->defender Override edits the *defender's* `[N]` section: the attacker goes in
the matching bucket and is cleared from the other two, so a matchup can never read as
both weak and resistant. A neutral (1.0) Override clears the attacker from all three.

16.2 sections are `[N]` numeric with identity in `InternalName=`, so the buckets are
edited via `section_edit` keyed by the defender's INTERNAL name. Essentials can express
only those four outcomes; a multiplier it cannot represent (4x, 0.25x, 3x) is reported
blocked, not forced — an Honest Signifier. A type absent from the chart is reported too.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry
from . import pbs_io, section_edit
from .resolution import ResolutionMap

_BUCKET = {2.0: "Weaknesses", 0.5: "Resistances", 0.0: "Immunities"}
_ALL_BUCKETS = ("Weaknesses", "Resistances", "Immunities")


def apply_type_chart(
    target: Path, ruleset: Ruleset, resmap: ResolutionMap, report: ApplyReport
) -> set[Path]:
    if not ruleset.type_chart:
        return set()
    path = target / "PBS" / "types.txt"
    if not path.exists():
        for override in ruleset.type_chart:
            report.add(ReportEntry(
                status="blocked", category="type-chart",
                chrooked_id=f"{override.attacker}->{override.defender}",
                reason="types.txt not found",
            ))
        return set()

    text, had_bom = pbs_io.read(path)
    original = text

    for override in ruleset.type_chart:
        chrooked_id = f"{override.attacker}->{override.defender}"
        target_bucket, portable = _classify(override.multiplier)
        if not portable:
            report.add(ReportEntry(
                status="blocked", category="type-chart", chrooked_id=chrooked_id,
                reason=f"multiplier {override.multiplier} not expressible in Essentials",
            ))
            continue

        defender = resmap.type(override.defender)
        attacker = resmap.type(override.attacker)
        if defender is None or attacker is None:
            report.add(ReportEntry(
                status="blocked", category="type-chart", chrooked_id=chrooked_id,
                reason="type not present in target chart",
            ))
            continue
        if section_edit.find_section_by_internalname(text, defender) is None:
            report.add(ReportEntry(
                status="blocked", category="type-chart", chrooked_id=chrooked_id,
                reason="defender type section not found",
            ))
            continue

        text, changed = _set_effectiveness(text, defender, attacker, target_bucket)
        # Always report — an already-correct chart entry is "applied" (the desired
        # state is in effect), so a no-op is visible rather than silently dropped.
        report.add(ReportEntry(
            status="applied", category="type-chart", chrooked_id=chrooked_id,
            symbol=defender,
            reason="retuned" if changed else "already in desired state",
        ))

    if text != original:
        pbs_io.write(path, text, had_bom)
        return {path}
    return set()


def _classify(multiplier: float) -> tuple[Optional[str], bool]:
    """Map a multiplier to `(target_bucket, portable)`. Neutral (1.0) -> `(None, True)`
    (clear from all). An unrepresentable value -> `(None, False)` (caller blocks it)."""
    if multiplier == 1.0:
        return None, True
    bucket = _BUCKET.get(multiplier)
    return bucket, bucket is not None


def _set_effectiveness(
    text: str, defender: str, attacker: str, target_bucket: Optional[str]
) -> tuple[str, bool]:
    """Put `attacker` in `target_bucket` of `defender`, clear it from the others.

    `target_bucket` is None for a neutral Override (clear from all three). A bucket that
    empties out has its line removed, never left as a dangling `Key=`. Returns
    `(new_text, changed)`; False when every bucket was already in the desired state.
    """
    changed = False
    for bucket in _ALL_BUCKETS:
        span = section_edit.find_section_by_internalname(text, defender)
        if span is None:
            raise RuntimeError(f"defender section {defender!r} vanished mid-edit")
        current = section_edit.get_field(text[span[0]:span[1]], bucket)
        items = [x.strip() for x in current.split(",") if x.strip()] if current else []
        wanted = bucket == target_bucket
        present = attacker in items

        if wanted and not present:
            items.append(attacker)
        elif not wanted and present:
            items = [x for x in items if x != attacker]
        else:
            continue

        if items:
            text, _ = section_edit.set_section_field(text, defender, bucket, ",".join(items))
        else:
            text, _ = section_edit.remove_section_field(text, defender, bucket)
        changed = True
    return text, changed
