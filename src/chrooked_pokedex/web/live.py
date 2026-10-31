"""Live game state for the companion screen.

The ``chrooked_zz_companion`` mod inside a running Target posts one JSON blob
per event (battle turn, battle end, map change). This keeps the newest blob per
engine in memory and hands it to the bottom-screen view, which polls it.

Keyed by engine, not Target id: a Target id is minted per machine
(``targets.json`` is gitignored), so a mod shipped to the handheld cannot know
it, while the engine name is the same everywhere. One live game per engine is
the real case (one Rejuv, one Nova).

Each mon gets a ``chrooked_id`` here, so the view joins it to the backdrop dex
without knowing engine symbols: base form = ``slug(SPECIES)``, any other form =
``slug(SPECIES)--slug(form name)``, the same rule ``snapshot_rejuv`` and
``rejuv_save`` use. ``base_id`` rides along so a form the dex does not list
still renders as its base species.

ponytail: in-memory, lost on restart; persist to disk if a restart mid-session
ever matters.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from ..seed.neutralize import slug

ENGINES = ("rejuv", "essentials")
MAX_BYTES = 64_000
_MON_LISTS = ("party", "foes")


def mon_ids(species: Any, form: Any, form_index: Any) -> tuple[str, str]:
    """``(chrooked_id, base_id)`` for one mon.

    The base form (index 0) and a blank form name both collapse to the base
    id, because Rejuv names the base form "Normal Form" only when the species
    has no forms at all, and Essentials leaves it blank.
    """
    base = slug(str(species or ""))
    try:
        index = int(form_index or 0)
    except (TypeError, ValueError):
        index = 0
    name = slug(str(form or ""))
    if index > 0 and name and name != "normalform":
        return f"{base}--{name}", base
    return base, base


def normalize(payload: dict[str, Any]) -> dict[str, Any]:
    """A copy of the mod's blob with ids minted on every mon."""
    out = dict(payload)
    for key in _MON_LISTS:
        mons = payload.get(key)
        if not isinstance(mons, list):
            out[key] = []
            continue
        rows = []
        for mon in mons:
            if not isinstance(mon, dict):
                continue
            cid, base = mon_ids(mon.get("species"), mon.get("form"), mon.get("form_index"))
            rows.append({**mon, "id": cid, "base_id": base})
        out[key] = rows
    return out


class LiveStore:
    """Newest blob per engine, with the time it arrived."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, dict[str, Any]] = {}
        self._seq = 0

    def put(self, engine: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._seq += 1
            entry = {
                "available": True,
                "engine": engine,
                "seq": self._seq,
                "received_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                **normalize(payload),
            }
            self._state[engine] = entry
            return entry

    def get(self, engine: str) -> dict[str, Any]:
        with self._lock:
            entry = self._state.get(engine)
        if entry is None:
            return {"available": False, "engine": engine}
        received = datetime.fromisoformat(entry["received_at"])
        age = (datetime.now(timezone.utc) - received).total_seconds()
        return {**entry, "age_s": int(age)}
