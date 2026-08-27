"""Save-state sync health for the Rejuvenation saves folder (#88).

Reads two things and merges them into one small payload the drawer renders as a
single calm line:

* **Syncthing REST** on the local box — ``/rest/db/completion`` per device (how
  far each device has caught up with the folder) and ``/rest/stats/device``
  (when each device was last seen). API key from ``SYNCTHING_API_KEY``.
* **The saves directory itself** — a glob for ``*.sync-conflict-*`` files, which
  is how Syncthing parks a save that two devices edited apart. That file is the
  only state here that genuinely needs a human, so it is the loud one.

Everything degrades to ``{"available": false}``. A missing key, a stopped
Syncthing, a DNS hiccup, a saves dir that is not mounted — none of those are an
error the user must act on, they just mean this row has nothing to say. The
route must never 500 over sync telemetry.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

DEFAULT_URL = "http://127.0.0.1:8384"
DEFAULT_FOLDER = "rejuv-saves"
DEFAULT_SAVES_DIR = "/data/rejuv-saves"

# Device IDs are machine-specific, so this is a default, not canon: override the
# whole map with SYNCTHING_DEVICES="name=ID,name=ID". hestia is intentionally
# absent — its full ID was never recorded here, and a truncated ID queries as a
# stranger rather than failing loudly.
DEFAULT_DEVICES = {
    "thor": "UMA523D-RCOYQHE-SDKYPK2-5CLFSMH-2T6O6O5-S2UQGSY-Y3V555Q-Y4DBWAY",
    "macbook": "MFJ6AQQ-TNQDT4Y-YLGJWWF-X3W5CGU-WFPBNP3-4AUJIYW-XN3ZXDD-QXMMTA6",
}

# A device that has not synced for this long while another one has is stale —
# the "you played on the couch and the desk never caught up" case.
STALE_AFTER_S = 60 * 60 * 6

_TIMEOUT_S = 2.0

# Syncthing names a parked copy "<stem>.sync-conflict-20260827-101500-<DEVICEID>.rxdata",
# where the trailing chunk is the FIRST 7 characters of the origin device id.
_CONFLICT_RE = re.compile(r"\.sync-conflict-\d{8}-\d{6}-([A-Z0-9]{7})")


def _devices() -> dict[str, str]:
    raw = os.environ.get("SYNCTHING_DEVICES", "").strip()
    if not raw:
        return dict(DEFAULT_DEVICES)
    pairs = (chunk.split("=", 1) for chunk in raw.split(",") if "=" in chunk)
    return {name.strip(): device_id.strip() for name, device_id in pairs}


def _parse_time(value: Any) -> datetime | None:
    """Syncthing timestamps are RFC3339 with nanoseconds, which `fromisoformat`
    rejects before 3.11 and still rejects beyond 6 fractional digits."""
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    text = re.sub(r"(\.\d{6})\d+", r"\1", text)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _conflicts(saves_dir: Path, devices: dict[str, str]) -> list[dict[str, str | None]]:
    """Every parked conflict copy, newest first, named back to its origin device.

    The device id is matched by its 7-character prefix because that is all
    Syncthing writes into the filename."""
    by_prefix = {device_id[:7]: name for name, device_id in devices.items()}
    found: list[tuple[float, dict[str, str | None]]] = []
    for path in saves_dir.glob("*.sync-conflict-*"):
        match = _CONFLICT_RE.search(path.name)
        prefix = match.group(1) if match else None
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        found.append(
            (
                mtime,
                {
                    "file": path.name,
                    "device": by_prefix.get(prefix or "", prefix),
                },
            )
        )
    return [entry for _, entry in sorted(found, key=lambda pair: -pair[0])]


def save_status() -> dict[str, Any]:
    """One payload for the drawer's save row. Never raises."""
    devices = _devices()
    saves_dir = Path(os.environ.get("SAVES_DIR", DEFAULT_SAVES_DIR))
    folder = os.environ.get("SYNCTHING_FOLDER_ID", DEFAULT_FOLDER)

    # The conflict glob is independent of Syncthing being up: the parked files
    # are on disk either way, and they are the part that needs a human.
    try:
        conflicts = _conflicts(saves_dir, devices) if saves_dir.is_dir() else []
    except OSError as error:
        _logger.debug("saves dir unreadable: %s", error)
        conflicts = []

    rows = _poll_syncthing(folder, devices)
    if rows is None:
        return {"available": False, "folder": folder, "conflicts": conflicts}

    synced = [row for row in rows if row["seconds_ago"] is not None]
    newest = min(synced, key=lambda row: row["seconds_ago"]) if synced else None
    # Stale only counts as a signal when SOMETHING else did sync — every device
    # quiet just means nobody has played, which is not a problem.
    stale = (
        [row["name"] for row in rows if _is_stale(row)] if newest is not None else []
    )

    return {
        "available": True,
        "folder": folder,
        "devices": rows,
        "newest": newest["name"] if newest else None,
        "newest_seconds_ago": newest["seconds_ago"] if newest else None,
        "stale": stale,
        "conflicts": conflicts,
    }


def _is_stale(row: dict[str, Any]) -> bool:
    seconds = row["seconds_ago"]
    return seconds is None or seconds > STALE_AFTER_S


def _poll_syncthing(folder: str, devices: dict[str, str]) -> list[dict[str, Any]] | None:
    """Per-device completion + last-seen, or ``None`` when Syncthing is not
    reachable/authorized. Any failure is a `None`, never an exception."""
    key = os.environ.get("SYNCTHING_API_KEY", "").strip()
    if not key:
        return None
    base = os.environ.get("SYNCTHING_URL", DEFAULT_URL).rstrip("/")

    try:
        import httpx
    except ImportError:  # pragma: no cover - the web extra always ships httpx
        return None

    now = datetime.now(timezone.utc)
    try:
        with httpx.Client(timeout=_TIMEOUT_S, headers={"X-API-Key": key}) as client:
            stats = client.get(f"{base}/rest/stats/device")
            stats.raise_for_status()
            seen_by_id = stats.json()

            rows = []
            for name, device_id in devices.items():
                completion = client.get(
                    f"{base}/rest/db/completion",
                    params={"folder": folder, "device": device_id},
                )
                completion.raise_for_status()
                last_seen = _parse_time(
                    (seen_by_id.get(device_id) or {}).get("lastSeen")
                )
                rows.append(
                    {
                        "name": name,
                        "id": device_id,
                        "completion": completion.json().get("completion"),
                        "last_seen": last_seen.isoformat() if last_seen else None,
                        "seconds_ago": (
                            int((now - last_seen).total_seconds())
                            if last_seen
                            else None
                        ),
                    }
                )
            return rows
    except Exception as error:  # noqa: BLE001 - telemetry never breaks the route
        _logger.debug("syncthing unreachable: %s", error)
        return None
