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
    # The suggest endpoint honours eight anchors; Chris names fifteen to
    # twenty-five. Every anchor past the eighth is folded in deterministically
    # (first real batch: 5–7 anchors dropped per line before this existed).
    pool = inputs["move_pool"]
    all_anchors = _canonical_anchors(decisions.get("anchors") or [], pool)
    rows, fold_notes = fold_anchors(rows, all_anchors, pool, proposed=_proposed_moves(record))
    anchors = all_anchors
    # A drop can open a ladder hole or a gap, so the repair chain runs again
    # over the trimmed rows (the endpoint already ran it once before the drop).
    rows, notes = learnset_repair.scrub_draft(rows, pool, anchors=anchors)
    notes = fold_notes + notes
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


def _canonical_anchors(names: list[str], pool: list[dict[str, Any]]) -> list[str]:
    """Anchor names in the pool's own casing, order kept, unknowns dropped."""
    by_key = {str(r["move"]).casefold(): str(r["move"]) for r in pool}
    out: list[str] = []
    for n in names:
        canon = by_key.get(str(n).casefold())
        if canon and canon not in out:
            out.append(canon)
    return out


def _proposed_moves(record: DesignRecord) -> set[str]:
    packet = record.packet or {}
    return {str(m.get("move", "")).casefold() for m in packet.get("moves") or []}


def fold_anchors(
    rows: list[dict[str, Any]],
    anchors: list[str],
    pool: list[dict[str, Any]],
    *,
    proposed: set[str] | None = None,
    size_max: int = suggestmod.LEARNSET_SIZE_MAX,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Seat every missing anchor at the nearest legal free level.

    Pure. When the learnset is at its cap, a filler row gives way first: a
    non-anchor row above L1 that neither the user nor the packet ever named,
    lowest power first; failing that, the weakest non-anchor row above L1.
    Notes start ``"fold: "``. The caller runs scrub/repair/audit afterwards.
    """
    from .learnset_skeleton import _pacing_bands

    idx = learnset_repair._index(pool)
    pacing = _pacing_bands()
    proposed = proposed or set()
    anchor_keys = {a.casefold() for a in anchors}
    work = [dict(r) for r in rows]
    notes: list[str] = []
    present = {str(r["move"]).casefold() for r in work}
    early_cap = int(learnset_repair.house_rules().get("early_rung_by_level", 16))
    status_seat = 20  # folded status moves spread across the mid-game, not one block
    for name in anchors:
        if name.casefold() in present:
            continue
        row = {"level": 0, "move": name}
        power = learnset_repair._power(row, idx)
        status = learnset_repair._is_status(row, idx)
        if len(work) >= size_max:
            # The opening rungs (≤ early_rung_by_level) are the game's first
            # hours; they never give way (first rebuild evicted Falinks' L5/L9).
            fillers = [
                r for r in work
                if int(r["level"]) > early_cap
                and str(r["move"]).casefold() not in anchor_keys
            ]
            unnamed = [r for r in fillers if str(r["move"]).casefold() not in proposed]
            victims = sorted(unnamed or fillers, key=lambda r: learnset_repair._power(r, idx) or 0)
            if not victims:
                notes.append(f"fold: no room for {name} — every row is an anchor or kit")
                continue
            victim = victims[0]
            work.remove(victim)
            notes.append(f"fold: dropped {victim['move']} @{victim['level']} to make room for {name}")
        if status:
            preferred = status_seat
            status_seat = 20 + (status_seat - 20 + 9) % 45  # 20, 29, 38, 47, 56, 20…
        else:
            band = next((b for b in pacing if (b.get("bp_min", 0) <= (power or 0) <= b.get("bp_max", 10**6))), None)
            preferred = (band["level_min"] + band["level_max"]) // 2 if band else 40
        used = {int(r["level"]) for r in work}
        level = learnset_repair.nearest_free_level(
            preferred, used, legal=lambda L, p=power: learnset_repair._pacing_ok(L, p, pacing)
        )
        work.append({"level": level, "move": name})
        present.add(name.casefold())
        notes.append(f"fold: seated {name} at L{level}")
    work.sort(key=lambda r: (int(r["level"]), r["move"]))
    return work, notes


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
