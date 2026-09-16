"""`/api/design` — the batch blind-design pipeline's human-side routes (#103, M1).

Ingest turns `ruleset/QUEUE.md` rows into design records; decisions and
confirm are Chris's two writes. Propose (M2), realize (M4) and ship (M5) live
in their own modules and register onto this router so each milestone edits
only its own file.

`build_router(ctx)` takes a `DesignContext` rather than importing `app.py`:
the loaders (`load_snapshot`, `load_ruleset`) and the Ports (`llm_provider`,
`lore_provider`) are closures over app state in `create_app`, and taking them
as callables keeps this module hermetic and free of a circular import.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from . import design_propose, design_queue, design_realize, design_ship
from . import dex as dexmod
from .design_store import DesignError, DesignRecord, DesignStore

DECISION_KEYS = {
    "typing", "abilities", "anchors", "drop", "custom", "stats", "skip_pre", "notes"
}
STAT_KEYS = {"hp", "atk", "def", "spa", "spd", "spe"}


@dataclass(frozen=True)
class DesignContext:
    """Everything the design routes need, handed in by `create_app`."""

    store: DesignStore
    load_snapshot: Callable[[], dict[str, Any]]
    load_ruleset: Callable[[], Any]
    llm_provider: Callable[[], Any]
    lore_provider: Callable[[dict[str, Any], str], Any]
    ruleset_dir: Path
    queue_path: Path
    app: Any  # the FastAPI app, for target tools (registry/state) at ship time


def raise_http(error: DesignError) -> HTTPException:
    return HTTPException(status_code=error.status, detail=error.message)


def _names(entries: list[dict[str, Any]]) -> set[str]:
    return {e["name"] for e in entries}


def _str_list(body: dict[str, Any], key: str) -> list[str]:
    value = body.get(key) or []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise HTTPException(status_code=422, detail=f"decisions.{key} must be a list of strings.")
    return value


def validate_decisions(
    body: dict[str, Any], snapshot: dict[str, Any], ruleset: Any
) -> dict[str, Any]:
    """Check a decisions body against the pools; 422 names the first offender.

    Abilities and anchors/drops must exist in the merged pools so a typo never
    reaches Realize; a custom's name must not clash with anything that exists.
    """
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="decisions must be an object.")
    unknown = set(body) - DECISION_KEYS
    if unknown:
        raise HTTPException(
            status_code=422, detail=f"Unknown decisions keys: {sorted(unknown)}."
        )
    ability_names = _names(dexmod.build_abilities(snapshot, ruleset))
    move_names = {row["move"] for row in dexmod.build_move_pool(snapshot, ruleset)}

    custom = body.get("custom")
    if custom is not None:
        if not isinstance(custom, dict) or custom.get("kind") not in ("ability", "move"):
            raise HTTPException(status_code=422, detail="custom.kind must be 'ability' or 'move'.")
        name = custom.get("name")
        if not isinstance(name, str) or not name.strip():
            raise HTTPException(status_code=422, detail="custom.name is required.")
        written = bool(custom.get("written", False))
        exists = name in ability_names or name in move_names
        # Pending: the name must be free (it is about to be created) and it may
        # already appear in anchors/abilities. Written: the entry must now exist —
        # that is the proof the custom lane finished (seen on Falinks / Volley).
        if not written and exists:
            raise HTTPException(
                status_code=422, detail=f"custom name {name!r} clashes with an existing entry."
            )
        if written and not exists:
            raise HTTPException(
                status_code=422,
                detail=f"custom {name!r} is marked written but is not in the pool yet.",
            )
        if custom["kind"] == "move":
            move_names = move_names | {name}
        else:
            ability_names = ability_names | {name}
        custom = {**custom, "written": written}

    abilities = _str_list(body, "abilities")
    for name in abilities:
        if name not in ability_names:
            raise HTTPException(status_code=422, detail=f"Ability {name!r} is not in the pool.")
    for key in ("anchors", "drop"):
        for name in _str_list(body, key):
            if name not in move_names:
                raise HTTPException(
                    status_code=422, detail=f"Move {name!r} ({key}) is not in the pool."
                )
    _str_list(body, "skip_pre")

    typing = body.get("typing")
    if typing is not None:
        if not isinstance(typing, list) or not 1 <= len(typing) <= 2:
            raise HTTPException(status_code=422, detail="typing must be null or 1-2 type names.")
        known_types = {
            c["attacker"] for c in snapshot.get("type_chart", [])
        } | {c["defender"] for c in snapshot.get("type_chart", [])}
        for t in typing:
            if known_types and t not in known_types:
                raise HTTPException(status_code=422, detail=f"Unknown type {t!r}.")

    stats = body.get("stats")
    if stats is not None:
        if not isinstance(stats, dict):
            raise HTTPException(status_code=422, detail="stats must be null or an object.")
        spread = stats.get("delta", stats)
        if not isinstance(spread, dict) or not set(spread) <= STAT_KEYS or not all(
            isinstance(v, int) for v in spread.values()
        ):
            raise HTTPException(
                status_code=422, detail=f"stats keys must be a subset of {sorted(STAT_KEYS)} with int values."
            )
        if "delta" not in stats and set(spread) != STAT_KEYS:
            raise HTTPException(status_code=422, detail="a full stats spread needs all six stats.")

    notes = body.get("notes", "")
    if notes is not None and not isinstance(notes, str):
        raise HTTPException(status_code=422, detail="notes must be a string.")

    return {
        "typing": typing,
        "abilities": abilities,
        "anchors": _str_list(body, "anchors"),
        "drop": _str_list(body, "drop"),
        "custom": custom,
        "stats": stats,
        "skip_pre": _str_list(body, "skip_pre"),
        "notes": notes or "",
    }


def ingest_queue(ctx: DesignContext) -> dict[str, Any]:
    """Create a record for every resolved queue subject that has none. Idempotent."""
    text = ctx.queue_path.read_text(encoding="utf-8") if ctx.queue_path.is_file() else ""
    snapshot = ctx.load_snapshot()
    names = design_queue.display_names(snapshot)
    created: list[str] = []
    existing: list[str] = []
    unresolved: list[dict[str, str]] = []
    for row in design_queue.parse_rows(text, names):
        resolved = design_queue.resolve_row(row, snapshot, names)
        if isinstance(resolved, design_queue.Unresolved):
            unresolved.append({"row": resolved.row, "reason": resolved.reason})
            continue
        for r in resolved:
            if ctx.store.exists(r.id) or r.id in created:
                if r.id not in existing:
                    existing.append(r.id)
                continue
            ctx.store.save(
                DesignRecord(
                    id=r.id, line=r.line, forms=r.forms, group=r.group,
                    steer=r.steer, references=r.references,
                )
            )
            created.append(r.id)
    return {"created": created, "existing": existing, "unresolved": unresolved}


def build_router(ctx: DesignContext) -> APIRouter:
    router = APIRouter(prefix="/api/design")

    @router.post("/ingest")
    def ingest() -> dict[str, Any]:
        try:
            return ingest_queue(ctx)
        except DesignError as error:
            raise raise_http(error) from error

    @router.get("")
    def list_records() -> list[dict[str, Any]]:
        return [r.as_dict() for r in ctx.store.list()]

    @router.get("/{record_id}")
    def get_record(record_id: str) -> dict[str, Any]:
        try:
            return ctx.store.get(record_id).as_dict()
        except DesignError as error:
            raise raise_http(error) from error

    @router.put("/{record_id}/decisions")
    async def put_decisions(
        record_id: str, request: Request, background_tasks: BackgroundTasks, realize: bool = True
    ) -> dict[str, Any]:
        # `realize=true` (default) enqueues Realize unless a custom is pending —
        # the custom lane finishes with its own PUT setting `custom.written`.
        body = await request.json()
        decisions = validate_decisions(body, ctx.load_snapshot(), ctx.load_ruleset())
        try:
            record = ctx.store.transition(record_id, "decided", decisions=decisions)
            if realize and not design_realize.pending_custom(record):
                record = design_realize.enqueue_realize(background_tasks, ctx, record_id)
            return record.as_dict()
        except DesignError as error:
            raise raise_http(error) from error

    @router.post("/{record_id}/confirm")
    def confirm(record_id: str) -> dict[str, Any]:
        try:
            return ctx.store.transition(record_id, "confirmed").as_dict()
        except DesignError as error:
            raise raise_http(error) from error

    @router.delete("/{record_id}")
    def delete_record(record_id: str) -> dict[str, str]:
        try:
            ctx.store.delete(record_id)
        except DesignError as error:
            raise raise_http(error) from error
        return {"deleted": record_id}

    design_propose.register(router, ctx)
    design_realize.register(router, ctx)
    design_ship.register(router, ctx)
    return router
