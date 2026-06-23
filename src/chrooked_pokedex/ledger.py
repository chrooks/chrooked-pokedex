"""The Change Ledger: an append-only record of every Ruleset mutation.

One JSON object per line in ``ruleset/ledger.ndjson`` (always the BASE ruleset
directory, never a Target namespace). Each entry carries a ``scope`` (``base`` or
``target:<slug>``), a ``source`` (``web-edit``, ``harvest``, ``apply``, ``seed``),
a ``kind``, and a timestamp. Authoring edits and harvest record a field-level
``from -> to`` diff; an apply records its Apply Report counts; a bulk seed records
one summary line.

Unlike the deterministic snapshot writer, the ledger is inherently time-ordered,
so stamping ``ts`` with the wall clock here is intentional, not a reproducibility
hazard — the file is a history, never regenerated.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

LEDGER_FILE = "ledger.ndjson"


def now_iso() -> str:
    """Current UTC time as an ISO-8601 string (the ledger's ``ts``)."""
    return datetime.now(timezone.utc).isoformat()


def append(ruleset_dir: Path, entry: dict[str, Any]) -> None:
    """Append one entry to ``<ruleset_dir>/ledger.ndjson``, stamping ``ts`` if absent."""
    path = Path(ruleset_dir) / LEDGER_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    stamped = {**entry}
    stamped.setdefault("ts", now_iso())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(stamped, sort_keys=True) + "\n")


def read(
    ruleset_dir: Path,
    *,
    scope: Optional[str] = None,
    kind: Optional[str] = None,
    chrooked_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Return ledger entries newest-first, filtered by scope/kind/chrooked_id.

    A missing or empty ledger returns ``[]``. Unparseable lines are skipped so a
    hand-edit cannot break the read path.
    """
    path = Path(ruleset_dir) / LEDGER_FILE
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if scope is not None and obj.get("scope") != scope:
            continue
        if kind is not None and obj.get("kind") != kind:
            continue
        if chrooked_id is not None and obj.get("chrooked_id") != chrooked_id:
            continue
        entries.append(obj)
    entries.reverse()  # file is oldest-first; callers want newest-first
    if limit is not None:
        entries = entries[: max(0, limit)]
    return entries


def diff_fields(
    before: Optional[dict[str, Any]], after: Optional[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Compute ``{field: {"from": old, "to": new}}`` for fields that changed.

    A None ``before`` means a create (every field is new); a None ``after`` means
    a delete (every field goes to None). Unchanged fields are omitted.
    """
    before = before or {}
    after = after or {}
    fields: dict[str, dict[str, Any]] = {}
    for key in set(before) | set(after):
        old = before.get(key)
        new = after.get(key)
        if old != new:
            fields[key] = {"from": old, "to": new}
    return fields
