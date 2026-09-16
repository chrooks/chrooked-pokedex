"""Design records — the batch blind-design pipeline's state, one JSON file per line.

`ruleset/QUEUE.md` holds Chris's *intent* (hand-written rows); this store holds
only *pipeline state* for those rows (`.chrooked/design/<id>.json`, gitignored,
app-owned — same precedent as `targets.json`). The record id is the
`chrooked_id` of the line's final stage: the pipeline designs the final first
and copies down, so the final is the natural key.

The state machine is the Contract every later milestone (propose, realize,
ship) relies on; `transition` is the only way a record changes state so an
illegal move is a 409, never a silently wrong record.
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATES = (
    "queued",
    "proposing",
    "proposed",
    "decided",
    "realizing",
    "previewed",
    "confirmed",
    "shipped",
    "proven",
    "error",
)

# Legal edges. `error` is reachable from every state and may go back anywhere
# (the retry call re-enters the state it left), so it is not listed here.
TRANSITIONS: dict[str, set[str]] = {
    "queued": {"proposing"},
    "proposing": {"proposed"},
    "proposed": {"proposing", "decided"},
    "decided": {"decided", "realizing"},
    "realizing": {"previewed"},
    "previewed": {"decided", "realizing", "confirmed"},
    "confirmed": {"shipped"},
    "shipped": {"proven", "queued"},
    "proven": {"queued"},
    "error": set(STATES) - {"error"},
}


class DesignError(Exception):
    """A pipeline refusal with the HTTP status the router should answer with."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class DesignRecord:
    """One line's pipeline state. Shape mirrors the plan's JSON exactly."""

    id: str
    line: list[str]
    forms: list[str] = field(default_factory=list)
    group: str | None = None
    steer: str = ""
    references: list[str] = field(default_factory=list)
    state: str = "queued"
    activity: str = "idle"
    created: str = field(default_factory=_now)
    updated: str = field(default_factory=_now)
    packet: dict[str, Any] | None = None
    decisions: dict[str, Any] | None = None
    preview: dict[str, Any] | None = None
    ship: dict[str, Any] | None = None
    corrections: list[str] = field(default_factory=list)
    proof: dict[str, Any] | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DesignRecord":
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


class DesignStore:
    """JSON-file store under one directory; every write is atomic (tmp + rename)."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def _path(self, record_id: str) -> Path:
        if not record_id or "/" in record_id or record_id.startswith("."):
            raise DesignError(400, f"Bad design record id {record_id!r}.")
        return self.directory / f"{record_id}.json"

    def list(self) -> list[DesignRecord]:
        """Every record, newest first."""
        if not self.directory.is_dir():
            return []
        records = [
            DesignRecord.from_dict(json.loads(p.read_text(encoding="utf-8")))
            for p in sorted(self.directory.glob("*.json"))
        ]
        return sorted(records, key=lambda r: r.created, reverse=True)

    def exists(self, record_id: str) -> bool:
        return self._path(record_id).is_file()

    def get(self, record_id: str) -> DesignRecord:
        path = self._path(record_id)
        if not path.is_file():
            raise DesignError(404, f"No design record {record_id!r}.")
        return DesignRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, record: DesignRecord) -> DesignRecord:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(record.id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record.as_dict(), indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        return record

    def delete(self, record_id: str) -> None:
        path = self._path(record_id)
        if not path.is_file():
            raise DesignError(404, f"No design record {record_id!r}.")
        path.unlink()

    def transition(self, record_id: str, to: str, **patch: Any) -> DesignRecord:
        """Move a record to `to`, applying `patch`; 409 on an illegal edge.

        Any state may enter `error`; `error` may leave to any state. `updated`
        is stamped here so no caller forgets it.
        """
        record = self.get(record_id)
        if to not in STATES:
            raise DesignError(400, f"Unknown design state {to!r}.")
        if to != "error" and to not in TRANSITIONS[record.state]:
            raise DesignError(
                409, f"Design record {record_id!r} is {record.state!r}; cannot go to {to!r}."
            )
        if to != "error" and "error" not in patch:
            patch["error"] = None
        updated = dataclasses.replace(record, state=to, updated=_now(), **patch)
        return self.save(updated)
