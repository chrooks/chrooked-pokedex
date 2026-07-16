"""Sort the Ruleset's behaviors into implementation-cost buckets for Rejuv.

Behavior battle *code* is out of scope for the data applier — this module only
classifies the 64 behaviors so a follow-up plan can be sized. The signal is
cheap and honest: whether Rejuv already implements the ability under its own
symbol.

  bucket 1 (data-only)      an ability Rejuv ALREADY implements natively — we
                            only assign it to mon and patch its text. Zero
                            battle code.
  bucket 2 (function-code)  a move mechanic — a candidate to map onto one of
                            Rejuv's existing ``:function`` hex codes (data tweak,
                            no new code). Needs a per-move lookup, deferred.
  bucket 3 (custom-code)    a NEW ability Rejuv does not have — needs a
                            ``patch/Mods`` battle-method override. The real cost.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...model import Ruleset
from .resolution import RejuvResolution

BUCKET_DATA_ONLY = "data-only"
BUCKET_FUNCTION_CODE = "function-code"
BUCKET_CUSTOM_CODE = "custom-code"


@dataclass(frozen=True)
class TriageRow:
    chrooked_id: str
    name: str
    applies_to: str
    bucket: str
    note: str


def triage(ruleset: Ruleset, resolution: RejuvResolution) -> list[TriageRow]:
    rows: list[TriageRow] = []
    for behavior in ruleset.behaviors.values():
        if behavior.applies_to == "move":
            rows.append(TriageRow(
                behavior.chrooked_id, behavior.name, "move", BUCKET_FUNCTION_CODE,
                "move mechanic — map to an existing Rejuv :function code (deferred)",
            ))
            continue
        # applies_to == "ability"
        if resolution.ability(behavior.name) is not None:
            rows.append(TriageRow(
                behavior.chrooked_id, behavior.name, "ability", BUCKET_DATA_ONLY,
                "Rejuv implements this ability natively; only text/assignment needed",
            ))
        else:
            rows.append(TriageRow(
                behavior.chrooked_id, behavior.name, "ability", BUCKET_CUSTOM_CODE,
                "new ability — needs a patch/Mods battle-method override",
            ))
    return rows


def render_markdown(rows: list[TriageRow]) -> str:
    order = (BUCKET_DATA_ONLY, BUCKET_FUNCTION_CODE, BUCKET_CUSTOM_CODE)
    counts = {b: sum(1 for r in rows if r.bucket == b) for b in order}
    lines = [
        "# Rejuvenation Behavior Triage",
        "",
        f"Total behaviors: {len(rows)}",
        "",
        f"- data-only (no code): {counts[BUCKET_DATA_ONLY]}",
        f"- function-code fit (deferred): {counts[BUCKET_FUNCTION_CODE]}",
        f"- custom code (patch/Mods): {counts[BUCKET_CUSTOM_CODE]}",
        "",
        "| bucket | chrooked_id | name | applies_to | note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for bucket in order:
        for row in sorted((r for r in rows if r.bucket == bucket), key=lambda r: r.chrooked_id):
            lines.append(
                f"| {row.bucket} | {row.chrooked_id} | {row.name} "
                f"| {row.applies_to} | {row.note} |"
            )
    return "\n".join(lines) + "\n"
