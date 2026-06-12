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

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/dex")
    def get_dex() -> list[dict[str, Any]]:
        try:
            snapshot = snapmod.load_snapshot(snapshot_path)
        except (FileNotFoundError, json.JSONDecodeError) as error:
            # The realistic failure: the snapshot was never generated, or is
            # corrupt. Surface an actionable message instead of a bare 500.
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Base snapshot unreadable at {snapshot_path}: {error}. "
                    "Generate it with `chrooked-pokedex snapshot --base <path>`."
                ),
            ) from error
        ruleset = Ruleset.load(ruleset_dir)
        return dexmod.build_dex(snapshot, ruleset)

    if dist_dir is not None and Path(dist_dir).exists():
        app.mount(
            "/", StaticFiles(directory=str(dist_dir), html=True), name="frontend"
        )

    return app
