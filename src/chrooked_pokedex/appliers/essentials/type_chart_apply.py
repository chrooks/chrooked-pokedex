"""Apply type-chart Overrides into `types.txt`'s effectiveness buckets.

pokeemerald stores effectiveness as a numeric matrix of arbitrary multipliers;
Essentials stores it per type, on the DEFENDER, as three buckets — `Weaknesses` (2x),
`Resistances` (0.5x), and `Immunities` (0x) — each a comma-list of attacking type
internals. So an attacker->defender Override edits the *defender's* section: the
attacker is placed in the matching bucket and cleared from the other two, so the chart
can never say a matchup is both a weakness and a resistance. A neutral Override (1.0)
clears the attacker from all three.

Essentials can express only those four outcomes. A multiplier it cannot represent
(4x, 0.25x, 3x — which in Essentials only arise from dual-type stacking, never a single
pairing) is reported blocked, never forced into the nearest bucket — an Honest Signifier.
A type absent from the target chart is likewise reported, not invented.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ...model import Ruleset
from ...report import ApplyReport, ReportEntry
from . import pbs_edit
from .resolution import ResolutionMap

# Multiplier -> the defender bucket an attacker belongs in. 1.0 (neutral) is handled
# separately as "clear from all buckets"; anything else is unportable.
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

    text = path.read_text(encoding="utf-8")
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
        if pbs_edit.find_section(text, defender) is None:
            report.add(ReportEntry(
                status="blocked", category="type-chart", chrooked_id=chrooked_id,
                reason="defender type section not found",
            ))
            continue

        text, changed = _set_effectiveness(text, defender, attacker, target_bucket)
        # Report only a real edit. A matchup already in the desired state writes
        # nothing and gets no report line, so "applied" always means a modification.
        if changed:
            report.add(ReportEntry(
                status="applied", category="type-chart", chrooked_id=chrooked_id,
                symbol=defender,
            ))

    if text != original:
        path.write_text(text, encoding="utf-8")
        return {path}
    return set()


def _classify(multiplier: float) -> tuple[Optional[str], bool]:
    """Map a multiplier to `(target_bucket, portable)`. Neutral (1.0) returns
    `(None, True)` — clear the attacker from every bucket. An unrepresentable value
    returns `(None, False)` so the caller reports it blocked."""
    if multiplier == 1.0:
        return None, True
    bucket = _BUCKET.get(multiplier)
    return bucket, bucket is not None


def _set_effectiveness(
    text: str, defender: str, attacker: str, target_bucket: Optional[str]
) -> tuple[str, bool]:
    """Put `attacker` in `target_bucket` of `defender` and clear it from the others.

    `target_bucket` is None for a neutral Override (clear from all three). A bucket
    that empties out has its line removed rather than left as a dangling `Key = `.
    Returns `(new_text, changed)`; `changed` is False when every bucket was already in
    the desired state, so the caller can withhold a misleading "applied" report line.
    """
    changed = False
    for bucket in _ALL_BUCKETS:
        span = pbs_edit.find_section(text, defender)
        if span is None:
            # The outer caller already confirmed the section exists; reaching here
            # would mean an edit deleted it, which set_section_field/remove never do.
            raise RuntimeError(f"defender section {defender!r} vanished mid-edit")
        current = pbs_edit.get_field(text[span[0]:span[1]], bucket)
        items = [x for x in current.split(",") if x] if current else []
        wanted = bucket == target_bucket
        present = attacker in items

        if wanted and not present:
            items.append(attacker)
        elif not wanted and present:
            items = [x for x in items if x != attacker]
        else:
            continue  # already in the desired state for this bucket

        if items:
            text = pbs_edit.set_section_field(text, defender, bucket, ",".join(items))
        else:
            text, _ = pbs_edit.remove_section_field(text, defender, bucket)
        changed = True
    return text, changed
