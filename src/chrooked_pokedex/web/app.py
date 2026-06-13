"""The FastAPI application factory.

`create_app` wires the API routers over a Ruleset folder and a base snapshot
file. It loads both *per request* so an edit to `ruleset/` shows up on the next
call without a server restart — the same fail-fast loader gates every read.

In production the built React assets under `frontend/dist` are mounted at the
root; in dev that directory is absent and only the API is served (the Vite dev
server hosts the SPA separately).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from ..model import Ruleset
from . import collections as colmod
from . import dex as dexmod
from . import snapshot as snapmod


def create_app(
    *,
    ruleset_dir: Path,
    snapshot_path: Path = snapmod.DEFAULT_SNAPSHOT_PATH,
    dist_dir: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="chrooked-pokedex", version="0.1.0")
    ruleset_dir = Path(ruleset_dir)
    snapshot_path = Path(snapshot_path)

    def _load_snapshot_or_503() -> dict[str, Any]:
        """Load the base snapshot, or 503 with an actionable message.

        The realistic failure is that the snapshot was never generated, is
        corrupt, or is valid JSON of the wrong shape. Only the dex routes merge
        onto the base, so only they call this; the Ruleset-owned collection
        routes never touch the snapshot.
        """
        try:
            snapshot = snapmod.load_snapshot(snapshot_path)
            if "species" not in snapshot:
                raise ValueError("missing top-level 'species' key")
            return snapshot
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Base snapshot unreadable at {snapshot_path}: {error}. "
                    "Generate it with `chrooked-pokedex snapshot --base <path>`."
                ),
            ) from error

    def _load_ruleset_or_503() -> Ruleset:
        """Load the Ruleset, or 503 — never a raw 500 with a traceback.

        Every route reloads the Ruleset per request (so edits to `ruleset/` show
        on reload). A malformed YAML or a failed validation there must surface as
        an actionable 503, not an unhandled parser/validation error. The broad
        catch is deliberate: the loader can raise yaml/Key/Value errors and all
        of them mean "the Ruleset on disk is unreadable", which is a 503.
        """
        try:
            return Ruleset.load(ruleset_dir)
        except Exception as error:  # noqa: BLE001 — see docstring
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Ruleset at {ruleset_dir} could not be loaded: "
                    f"{type(error).__name__}: {error}."
                ),
            ) from error

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/dex")
    def get_dex() -> list[dict[str, Any]]:
        snapshot = _load_snapshot_or_503()
        return dexmod.build_dex(snapshot, _load_ruleset_or_503())

    @app.get("/api/dex/{chrooked_id}")
    def get_dex_entry(chrooked_id: str) -> dict[str, Any]:
        snapshot = _load_snapshot_or_503()
        entry = dexmod.build_dex_entry(snapshot, _load_ruleset_or_503(), chrooked_id)
        if entry is None:
            raise HTTPException(
                status_code=404, detail=f"No species with chrooked_id {chrooked_id!r}."
            )
        return entry

    @app.get("/api/moves")
    def get_moves() -> list[dict[str, Any]]:
        return colmod.build_moves(_load_ruleset_or_503())

    @app.get("/api/abilities")
    def get_abilities() -> list[dict[str, Any]]:
        return colmod.build_abilities(_load_ruleset_or_503())

    @app.get("/api/type-chart")
    def get_type_chart() -> list[dict[str, Any]]:
        return colmod.build_type_chart(_load_ruleset_or_503())

    @app.get("/api/behaviors")
    def get_behaviors() -> list[dict[str, Any]]:
        return colmod.build_behaviors(_load_ruleset_or_503())

    if dist_dir is not None and Path(dist_dir).exists():
        app.mount(
            "/", StaticFiles(directory=str(dist_dir), html=True), name="frontend"
        )

    return app
