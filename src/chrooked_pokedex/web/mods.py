"""The Mods API: the static-mod catalog and each Target's on/off switches.

The catalog is read on every request: Rejuv's from its harness (the mod files
are their own metadata), Essentials 21's generated (Redux Mode) — see
appliers/static_mods.py. A chosen Target gets its own engine's catalog. A Target's switches
live in its committed namespace (``ruleset/targets/<slug>/mods.yaml``), so a
Target must be bound to a namespace before a switch can be saved.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException

from .. import ledger as ledgermod
from ..appliers import static_mods
from ..model.mods import load_mods_off, write_mods_off
from . import targets as targetsmod

# The catalog shown when no Target is chosen.
MOD_ENGINE = "rejuv"


def build_router(
    *,
    ruleset_dir: Path,
    source_dir: Path,
    get_target: Callable[[str], "targetsmod.Target"],
) -> APIRouter:
    router = APIRouter(prefix="/api")

    def _target(target_id: str) -> "targetsmod.Target":
        try:
            return get_target(target_id)
        except targetsmod.TargetError as error:
            raise HTTPException(status_code=error.status, detail=error.detail) from error

    def _target_payload(target: "targetsmod.Target") -> dict[str, Any]:
        return {
            "id": target.id,
            "label": target.label,
            "engine": target.engine,
            "namespace": target.namespace,
            "supported": static_mods.catalog_for(target.engine, source_dir) is not None,
            "off": sorted(load_mods_off(ruleset_dir, target.namespace)),
        }

    @router.get("/mods")
    def list_mods(target: Optional[str] = None) -> dict[str, Any]:
        """Every static mod, plus the chosen Target's switches when ``?target=`` is set."""
        chosen = _target(target) if target else None
        engine = MOD_ENGINE
        if chosen is not None and static_mods.catalog_for(chosen.engine, source_dir) is not None:
            engine = chosen.engine
        return {
            "engine": engine,
            "mods": [asdict(m) for m in static_mods.catalog_for(engine, source_dir) or []],
            "target": _target_payload(chosen) if chosen else None,
        }

    @router.put("/targets/{target_id}/mods")
    def set_mods(target_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Save the Target's off list. Body: ``{"off": ["kirinprobe"]}``."""
        target = _target(target_id)
        if not target.namespace:
            raise HTTPException(
                status_code=409,
                detail=f"{target.label} has no namespace. Bind one in Targets first; "
                "mod switches are saved under ruleset/targets/<namespace>/.",
            )
        off = (payload or {}).get("off")
        if not isinstance(off, list) or not all(isinstance(i, str) for i in off):
            raise HTTPException(status_code=422, detail="'off' must be a list of mod ids.")
        mods = static_mods.catalog_for(target.engine, source_dir)
        if mods is None:
            raise HTTPException(status_code=409, detail=f"{target.engine} has no static mods.")
        by_id = {m.id: m for m in mods}
        unknown = sorted(set(off) - by_id.keys())
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unknown mod ids: {', '.join(unknown)}.")
        locked = sorted(i for i in off if by_id[i].locked)
        if locked:
            raise HTTPException(
                status_code=422, detail=f"Cannot turn off locked mods: {', '.join(locked)}."
            )
        before = sorted(load_mods_off(ruleset_dir, target.namespace))
        after = sorted(set(off))
        if before != after:
            write_mods_off(ruleset_dir, target.namespace, after)
            ledgermod.append(ruleset_dir, {
                "kind": "mods",
                "scope": f"target:{target.namespace}",
                "source": "web-edit",
                "chrooked_id": None,
                "from": before,
                "to": after,
            })
        return _target_payload(target)

    return router
