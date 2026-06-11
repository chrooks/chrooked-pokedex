"""The Apply Report: the human-readable record of an apply run.

Every entry the applier touches is classified as one of three statuses, and
nothing is ever silently dropped:

  applied  the entry landed fully.
  partial  the entry landed, but at least one referenced field could not (e.g. a
           move the target lacks); the unresolved references are listed.
  blocked  the whole entry could not land (e.g. a macro-form species entry that
           cannot be field-edited, or an unresolved species symbol).

The report renders as Markdown (for reading) with a JSON sidecar (for tooling).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Status = Literal["applied", "partial", "blocked"]


@dataclass(frozen=True)
class ReportEntry:
    status: Status
    category: str            # "species", "learnset", "move", ...
    chrooked_id: str
    symbol: str | None = None   # resolved target symbol, when known
    reason: str = ""            # why blocked/partial, or what landed
    partial_fields: tuple[str, ...] = ()


@dataclass
class ApplyReport:
    entries: list[ReportEntry] = field(default_factory=list)

    def add(self, entry: ReportEntry) -> None:
        self.entries.append(entry)

    def counts(self) -> dict[str, int]:
        result = {"applied": 0, "partial": 0, "blocked": 0}
        for entry in self.entries:
            result[entry.status] += 1
        return result

    def to_markdown(self) -> str:
        counts = self.counts()
        lines = [
            "# Apply Report",
            "",
            f"- applied: {counts['applied']}",
            f"- partial: {counts['partial']}",
            f"- blocked: {counts['blocked']}",
            "",
            "| status | category | chrooked_id | symbol | reason |",
            "| --- | --- | --- | --- | --- |",
        ]
        for entry in self.entries:
            reason = entry.reason
            if entry.partial_fields:
                reason = (reason + " " if reason else "") + (
                    "unresolved: " + ", ".join(entry.partial_fields)
                )
            lines.append(
                f"| {entry.status} | {entry.category} | {entry.chrooked_id} "
                f"| {entry.symbol or ''} | {reason} |"
            )
        return "\n".join(lines) + "\n"

    def to_json(self) -> str:
        payload = {
            "counts": self.counts(),
            "entries": [asdict(entry) for entry in self.entries],
        }
        return json.dumps(payload, indent=2) + "\n"

    def write(self, markdown_path: Path) -> Path:
        """Write the Markdown report and a JSON sidecar; return the JSON path."""
        markdown_path = Path(markdown_path)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(self.to_markdown(), encoding="utf-8")
        json_path = markdown_path.with_suffix(".json")
        json_path.write_text(self.to_json(), encoding="utf-8")
        return json_path
