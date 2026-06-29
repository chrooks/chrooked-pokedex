"""Back up an Essentials game's ``Data/`` once before a destructive apply.

An IF2-class Essentials fork recompiles its edited PBS into ``Data/*.dat`` on
the next boot — Essentials ``File.delete``s the old ``.dat`` first, so an
incomplete PBS bricks mid-compile with the ``.dat`` already gone (and not in the
Recycle Bin). A one-time ``Data.bak`` is the only recovery net.

Web-free (plain stdlib) so both the web apply path and the CLI ``apply`` can
share it without dragging in the web extra. Each caller maps
:class:`DataBackupError` to its own surface (HTTP 500 / non-zero exit).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


class DataBackupError(RuntimeError):
    """Backing up ``Data/`` failed; the apply must not proceed without the net."""


def backup_essentials_data(fork: Path) -> dict[str, Any]:
    """Copy ``Data/`` → ``Data.bak`` once, returning a status dict.

    Copies only when ``Data.bak`` does NOT already exist, so a later apply can't
    clobber a good backup with an already-bricked ``Data/``. A failed copy drops
    the partial and raises :class:`DataBackupError` (the apply should abort —
    the net is the whole point).

    ``status`` is one of: ``created`` (fresh backup), ``kept`` (left an existing
    backup untouched), ``skipped`` (no ``Data/`` to back up).
    """
    fork = Path(fork)
    data = fork / "Data"
    if not data.is_dir():
        return {"status": "skipped", "reason": "no Data/ directory", "path": None}
    backup = fork / "Data.bak"
    if backup.exists():
        return {
            "status": "kept",
            "reason": "Data.bak already exists — left untouched",
            "path": str(backup),
        }
    try:
        shutil.copytree(data, backup)
    except OSError as error:
        shutil.rmtree(backup, ignore_errors=True)  # drop any partial copy
        raise DataBackupError(f"Could not back up {data} → {backup}: {error}") from error
    return {"status": "created", "reason": "", "path": str(backup)}
