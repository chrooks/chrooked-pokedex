"""Design pipeline routes: realize — decisions → linted learnset + stats preview (#103, M4).

A written decisions record becomes a preview in the background so the next
packet can be decided while this one builds. Nothing here touches the
Ruleset; `preview` is the last stop before `confirm`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from . import dex as dexmod
from . import learnset_repair
from . import suggest as suggestmod
from .design_store import DesignError, DesignRecord

STAT_ORDER = ("hp", "atk", "def", "spa", "spd", "spe")
ABILITY_SLOTS = ("primary", "secondary", "hidden")
PENDING_CUSTOM_MESSAGE = (
    "Custom {kind} {name!r} is not written yet. Engineer it first, then PUT "
    "decisions with custom.written=true; Realize runs after that."
)


def _decisions(record: DesignRecord) -> dict[str, Any]:
    if record.decisions is None:
        raise DesignError(409, f"Design record {record.id!r} has no decisions to realize.")
    return record.decisions


def pending_custom(record: DesignRecord) -> dict[str, Any] | None:
    custom = (record.decisions or {}).get("custom")
    return custom if custom and not custom.get("written") else None


def build_direction(record: DesignRecord) -> str:
    """The free-text steer for suggest_learnset: axis, abilities, typing, notes, extra anchors."""
    decisions = record.decisions or {}
    packet = record.packet or {}
    parts: list[str] = []
    if packet.get("axis"):
        parts.append(f"Design axis: {packet['axis']}")
    if decisions.get("abilities"):
        parts.append("Abilities: " + ", ".join(decisions["abilities"]))
    if decisions.get("typing"):
        parts.append("Typing: " + "/".join(decisions["typing"]))
    if decisions.get("notes"):
        parts.append(f"Notes: {decisions['notes']}")
    extra = list(decisions.get("anchors") or [])[suggestmod.LEARNSET_ANCHOR_MAX :]
    if extra:
        parts.append("Must also appear: " + ", ".join(extra))
    if record.corrections:
        parts.append("Corrections: " + " | ".join(record.corrections))
    return "\n".join(parts)


def learnset_inputs(
    record: DesignRecord, snapshot: dict[str, Any], ruleset: Any
) -> dict[str, Any]:
    """Everything suggest_learnset is called with; the test fake mirrors this
    so its canned draft fills the exact skeleton the server builds."""
    decisions = _decisions(record)
    current = dexmod.build_dex_entry(snapshot, ruleset, record.id)
    if current is None:
        raise DesignError(404, f"No species {record.id!r} in the snapshot.")
    chosen = list(decisions.get("abilities") or [])
    abilities = current.get("abilities") or {}
    if chosen:
        abilities = {slot: (chosen[i] if i < len(chosen) else None)
                     for i, slot in enumerate(ABILITY_SLOTS)}
    entry = {
        **current,
        "types": list(decisions.get("typing") or current.get("types") or []),
        "abilities": abilities,
    }
    return {
        "entry": entry,
        "move_pool": dexmod.build_move_pool(snapshot, ruleset),
        "abilities": dexmod.build_abilities(snapshot, ruleset),
        "direction": build_direction(record),
        "anchors": list(decisions.get("anchors") or [])[: suggestmod.LEARNSET_ANCHOR_MAX],
    }


def stats_for_line(
    record: DesignRecord, snapshot: dict[str, Any], ruleset: Any
) -> dict[str, dict[str, int]]:
    """Per-stage spreads: final from decisions, pre-evos scaled to the final's
    new shape at (canon BST + the final's delta), forms shifted by the same delta."""
    decisions = _decisions(record)

    def current(cid: str) -> dict[str, int]:
        entry = dexmod.build_dex_entry(snapshot, ruleset, cid)
        if entry is None:
            raise DesignError(404, f"No species {cid!r} in the snapshot.")
        return {k: int(entry["stats"][k]) for k in STAT_ORDER}

    stages = [*record.line, *record.forms]
    spreads = {cid: current(cid) for cid in stages}
    stats = decisions.get("stats")
    if not stats:
        return spreads

    old_final = spreads[record.id]
    if "delta" in stats:
        new_final = {k: old_final[k] + int(stats["delta"].get(k, 0)) for k in STAT_ORDER}
    else:
        new_final = {k: int(stats[k]) for k in STAT_ORDER}
    per_stat_delta = {k: new_final[k] - old_final[k] for k in STAT_ORDER}
    bst_delta = sum(per_stat_delta.values())
    final_total = sum(new_final.values()) or 1
    skip = set(decisions.get("skip_pre") or [])

    out = dict(spreads)
    out[record.id] = new_final
    for cid in record.line:
        if cid == record.id or cid in skip:
            continue
        target = sum(spreads[cid].values()) + bst_delta
        scaled = {k: round(new_final[k] * target / final_total) for k in STAT_ORDER}
        scaled["hp"] += target - sum(scaled.values())  # rounding lands on HP
        out[cid] = scaled
    for cid in record.forms:
        out[cid] = {k: spreads[cid][k] + per_stat_delta[k] for k in STAT_ORDER}
    return out


def realize(
    record: DesignRecord,
    snapshot: dict[str, Any],
    ruleset: Any,
    provider: Any,
    lore_provider: Any,
) -> dict[str, Any]:
    """Decisions → preview dict. Pure: writes nothing."""
    decisions = _decisions(record)
    inputs = learnset_inputs(record, snapshot, ruleset)
    result = suggestmod.suggest_learnset(
        provider=provider,
        lore_mode="blind",
        lore_provider=lore_provider,
        **inputs,
    )
    warnings = list(result.get("warnings") or [])
    drop = {m.casefold() for m in decisions.get("drop") or []}
    rows = [
        {"level": r["level"], "move": r["move"]}
        for r in result["draft"]["learnset"]
        if r["move"].casefold() not in drop
    ]
    # A drop can open a ladder hole or a gap, so the repair chain runs again
    # over the trimmed rows (the endpoint already ran it once before the drop).
    pool, anchors = inputs["move_pool"], inputs["anchors"]
    rows, notes = learnset_repair.scrub_draft(rows, pool, anchors=anchors)
    rows, repair_notes = learnset_repair.repair_draft(rows, pool, anchors=anchors)
    lint = learnset_repair.audit_draft(
        rows, pool, anchors=anchors, stab_types=inputs["entry"]["types"]
    )
    return {
        "learnset": {"rows": rows, "warnings": warnings + notes + repair_notes, "lint": lint},
        "stats": stats_for_line(record, snapshot, ruleset),
        "abilities": list(decisions.get("abilities") or []),
        "typing": inputs["entry"]["types"],
    }


def _run_realize(ctx: Any, record_id: str) -> None:
    """The background job: realizing → previewed/ready, or → error."""
    try:
        snapshot = ctx.load_snapshot()
        preview = realize(
            ctx.store.get(record_id), snapshot, ctx.load_ruleset(),
            ctx.llm_provider(), ctx.lore_provider(snapshot, "blind"),
        )
        ctx.store.transition(record_id, "previewed", preview=preview, activity="ready")
    except Exception as error:  # noqa: BLE001 — the record carries the failure
        ctx.store.transition(record_id, "error", error=str(error), activity="error")


def enqueue_realize(background_tasks: BackgroundTasks, ctx: Any, record_id: str) -> DesignRecord:
    """Flip to realizing now; build the preview after the response is sent."""
    record = ctx.store.transition(record_id, "realizing", activity="proposing")
    background_tasks.add_task(_run_realize, ctx, record_id)
    return record


def register(router: APIRouter, ctx: Any) -> None:
    @router.post("/{record_id}/realize")
    async def realize_record(
        record_id: str, request: Request, background_tasks: BackgroundTasks
    ) -> dict[str, Any]:
        body = await request.json() if int(request.headers.get("content-length") or 0) else {}
        correction = (body or {}).get("correction")
        try:
            record = ctx.store.get(record_id)
            _decisions(record)
            custom = pending_custom(record)
            if custom:
                raise DesignError(
                    409, PENDING_CUSTOM_MESSAGE.format(kind=custom["kind"], name=custom["name"])
                )
            if correction:
                ctx.store.save(
                    DesignRecord.from_dict(
                        {**record.as_dict(), "corrections": [*record.corrections, str(correction)]}
                    )
                )
            return enqueue_realize(background_tasks, ctx, record_id).as_dict()
        except DesignError as error:
            raise HTTPException(status_code=error.status, detail=error.message) from error
