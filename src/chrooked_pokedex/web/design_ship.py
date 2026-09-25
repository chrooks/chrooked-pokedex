"""Design pipeline routes: ship — registered onto the /api/design router (#103, M5).

Ship is the one synchronous step: write every confirmed line into the Ruleset
through the CRUD write path, apply to the Target ONCE, read every stage back,
append the design log, and drop the shipped rows from `ruleset/QUEUE.md`.
A failing record never blocks the others; it lands in `error` with the bad
apply-report rows or the read-back diff, and the rest ship.

Line rules (CLAUDE.md "Evolution-line default", ported from the retired
`line_write.py`): the final gets every row; megas/forms of the final mirror it
with L0 kept; pre-evos not in `skip_pre` get the rows minus L0; abilities go to
every non-form stage; typing (when decided) to every stage; stats per stage
when the preview carries them.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from . import crud as crudmod
from . import design_log, design_queue
from . import dex as dexmod
from . import targets as targetsmod
from .design_store import DesignError, DesignRecord

_BAD_ROW = re.compile(r"\|\s*(partial|blocked)\s*\|")


def line_plan(
    record: DesignRecord, decisions: dict[str, Any], preview: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """Learnset rows per stage: final and forms whole, pre-evos minus L0."""
    rows = [
        {"level": int(r["level"]), "move": r["move"]}
        for r in preview["learnset"]["rows"]
    ]
    skip = set(decisions.get("skip_pre") or [])
    pre = [cid for cid in record.line if cid != record.id and cid not in skip]
    plan = {record.id: rows}
    plan.update({cid: rows for cid in record.forms})
    plan.update({cid: [r for r in rows if r["level"] != 0] for cid in pre})
    return plan


def _ability_slots(names: list[str]) -> dict[str, str | None]:
    padded = list(names[:3]) + [None] * (3 - min(len(names), 3))
    return {"primary": padded[0], "secondary": padded[1], "hidden": padded[2]}


def write_line(
    record: DesignRecord, ctx: Any, snapshot: dict[str, Any], ruleset: Any
) -> list[str]:
    """Write every stage of the plan through the CRUD write gate; returns the ids."""
    decisions = record.decisions or {}
    preview = record.preview or {}
    plan = line_plan(record, decisions, preview)
    stats_by_stage = preview.get("stats") or {}
    pools = dict(
        type_names={t.casefold() for t in dexmod.build_type_pool(snapshot, ruleset)},
        move_names={row["move"].casefold() for row in dexmod.build_move_pool(snapshot, ruleset)},
        ability_names={
            e["name"].casefold() for e in dexmod.build_abilities(snapshot, ruleset) if e.get("name")
        },
    )
    for cid, rows in plan.items():
        payload: dict[str, Any] = {
            "name": snapshot["species"][cid]["name"],
            "chrooked_id": cid,
            "learnset": rows,
        }
        if decisions.get("abilities") and cid not in record.forms:
            payload["abilities"] = _ability_slots(decisions["abilities"])
        if decisions.get("typing"):
            payload["types"] = list(decisions["typing"])
        if stats_by_stage.get(cid):
            payload["stats"] = dict(stats_by_stage[cid])
        crudmod.validate_species_references(payload, **pools)
        crudmod.upsert_species(ctx.ruleset_dir, cid, payload, ledger_dir=ctx.ruleset_dir)
    return list(plan)


# A design writes learnsets, abilities, typing and stats, never evolutions, so a
# blocked evolution row (Galarian Mr. Mime's EVO_MOVE Mimic has no Rejuv form)
# is standing apply debt, not this ship's failure.
_NOT_WRITTEN_BY_DESIGN = {"evolution"}


def _bad_rows(report_md: str, stages: list[str]) -> list[str]:
    out = []
    for line in report_md.splitlines():
        if _BAD_ROW.search(line):
            cells = [c.strip() for c in line.split("|")]
            if len(cells) > 2 and cells[2] in _NOT_WRITTEN_BY_DESIGN:
                continue
            if any(cid in cells for cid in stages):
                out.append(line.strip())
    return out


def _direction(record: DesignRecord) -> str:
    notes = (record.decisions or {}).get("notes") or ""
    axis = (record.packet or {}).get("axis") or ""
    return "; ".join(p for p in (notes.strip(), axis.strip()) if p)


def _new_mechanics(record: DesignRecord) -> str | None:
    custom = (record.decisions or {}).get("custom")
    if not custom:
        return None
    return f"{custom.get('name')} ({custom.get('kind')}): {custom.get('mechanic', '')}".strip()


# --- read-back without Ruby -------------------------------------------------- #
# hestia has no Ruby, so the snapshot-based read-back 500s there. The retired
# line_write.py read the applied montext.rb by regex instead; this is that path,
# kept as the fallback so a green apply still gets its proof.

def _sym(name: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (name or "").upper()).replace("HIGHJUMPKICK", "HIJUMPKICK")


_BLOCK = re.compile(r'if MONHASH\.dig\(:([A-Z0-9]+), "([^"]+)"\)(.*?)\nelse', re.S)


def montext_readback(
    target_path: str | Path, expectations: list[dict[str, Any]]
) -> dict[str, Any]:
    """Diff applied montext.rb blocks against per-stage expectations.

    Each expectation: ``{"id", "name", "rows", "abilities", "types"}``. A stage
    matches when some block for its base symbol carries the same moveset; the
    ability and type lines are then checked on that block. Same result shape as
    ``readback.read_back``.
    """
    src = (Path(target_path) / "patch" / "Definitions" / "montext.rb").read_text(encoding="utf-8")
    blocks: dict[str, list[str]] = {}
    for base, _form, body in _BLOCK.findall(src):
        blocks.setdefault(base, []).append(body)
    species: list[dict[str, Any]] = []
    for exp in expectations:
        # Longest name prefix that has a block: "Kommo O" is :KOMMOO and
        # "Mr Rime" is :MRRIME, while "Rotom Heat" and "Mr Mime Galar" are forms
        # under :ROTOM and :MRMIME. The first word alone missed the first two.
        words = str(exp["name"]).split()
        base = next((b for n in range(len(words), 0, -1)
                     if (b := _sym("".join(words[:n]))) in blocks), _sym(words[0] if words else ""))
        want_rows = sorted((int(l), _sym(m)) for l, m in exp["rows"])
        checks: list[dict[str, Any]] = []
        hit_body = None
        for body in blocks.get(base, []):
            m = re.search(r"\[:Moveset\] = (.*)", body)
            got = sorted((int(l), x) for l, x in re.findall(r"\[(\d+), :(\w+)\]", m.group(1) if m else ""))
            if got == want_rows:
                hit_body = body
                break
        checks.append({"field": "learnset", "ok": hit_body is not None,
                       "expected": len(want_rows), "actual": "MATCH" if hit_body else "no block matched"})
        if hit_body is not None:
            for i, slot in enumerate(("primary", "secondary")):
                want = exp.get("abilities", {}).get(slot)
                if want:
                    got = re.search(r"\[:Abilities\]\[%d\] = :(\w+)" % i, hit_body)
                    checks.append({"field": f"ability.{slot}", "ok": bool(got) and got.group(1) == _sym(want),
                                   "expected": _sym(want), "actual": got.group(1) if got else None})
            want_h = exp.get("abilities", {}).get("hidden")
            if want_h:
                got = re.search(r"\[:HiddenAbility\] = :(\w+)", hit_body)
                checks.append({"field": "ability.hidden", "ok": bool(got) and got.group(1) == _sym(want_h),
                               "expected": _sym(want_h), "actual": got.group(1) if got else None})
            for i, t in enumerate(exp.get("types") or []):
                got = re.search(r"\[:Type%d\] = :(\w+)" % (i + 1), hit_body)
                if got:
                    checks.append({"field": f"type{i+1}", "ok": got.group(1) == _sym(t),
                                   "expected": _sym(t), "actual": got.group(1)})
        ok_count = sum(1 for c in checks if c["ok"])
        species.append({"chrooked_id": exp["id"], "ok": ok_count == len(checks),
                        "ok_count": ok_count, "total": len(checks), "checks": checks})
    ok_count = sum(s["ok_count"] for s in species)
    total = sum(s["total"] for s in species)
    return {"species": species, "ok_count": ok_count, "total": total, "ok": all(s["ok"] for s in species)}


def _expectations(record: DesignRecord, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    decisions = record.decisions or {}
    preview = record.preview or {}
    plan = line_plan(record, decisions, preview)
    abilities = _ability_slots(list(decisions.get("abilities") or []))
    out = []
    for cid, rows in plan.items():
        entry = snapshot["species"].get(cid) or {}
        is_form = cid in record.forms
        out.append({
            "id": cid, "name": entry.get("name", cid),
            "rows": [(r["level"], r["move"]) for r in rows],
            "abilities": {} if is_form else abilities,
            "types": [] if is_form else list(preview.get("typing") or []),
        })
    return out


def ship(
    records: list[DesignRecord], target: Any, ctx: Any, snapshot: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Write all → apply once → read back each → log each. Per-record results."""
    app = ctx.app
    ruleset = ctx.load_ruleset()
    results: dict[str, dict[str, Any]] = {}
    stages_of: dict[str, list[str]] = {}

    def fail(record: DesignRecord, message: str, **ship_info: Any) -> None:
        results[record.id] = {"state": "error", "error": message, **ship_info}
        ctx.store.transition(record.id, "error", error=message, ship=ship_info or None)

    for record in records:
        try:
            stages_of[record.id] = write_line(record, ctx, snapshot, ruleset)
        except Exception as error:  # a rejected write must not block the others
            fail(record, f"write failed: {error}")
    written = [r for r in records if r.id in stages_of]
    if not written:
        return results

    try:
        effective = app.state.apply_target_effective(target)
        apply = targetsmod.apply_target(
            target, effective, app.state.targets_state, force=False,
            ledger_dir=ctx.ruleset_dir, ruleset_dir=ctx.ruleset_dir,
        )
    except Exception as error:
        for record in written:
            fail(record, f"apply failed: {error}")
        return results
    counts = {k: apply.get(k, 0) for k in ("applied", "partial", "blocked")}
    report_md = apply.get("report_md")
    if report_md is None:
        report_path = Path(target.path) / "apply-report.md"
        report_md = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""

    for record in written:
        stages = stages_of[record.id]
        bad = _bad_rows(report_md, stages)
        try:
            readback = app.state.read_back_ids(target, stages)
        except Exception as error:
            if "ruby" not in str(error).lower():
                fail(record, f"read-back failed: {error}", apply=counts, bad_rows=bad)
                continue
            try:
                readback = montext_readback(target.path, _expectations(record, snapshot))
            except Exception as error2:  # noqa: BLE001
                fail(record, f"read-back failed: {error2}", apply=counts, bad_rows=bad)
                continue
        summary = {k: readback.get(k) for k in ("ok", "ok_count", "total")}
        if bad or not readback.get("ok"):
            diff = [s for s in readback.get("species", []) if not s.get("ok")]
            fail(
                record, "apply reported partial/blocked rows" if bad else "read-back mismatch",
                apply=counts, readback={**summary, "diff": diff}, bad_rows=bad,
            )
            continue
        section = design_log.append_entry(
            ctx.ruleset_dir / "DESIGN-LOG.md",
            line=snapshot["species"][record.id]["name"],
            direction=_direction(record),
            new_mechanics=_new_mechanics(record),
            corrections="; ".join(record.corrections) or None,
        )
        info = {"apply": counts, "readback": summary, "log_section": section, "bad_rows": []}
        ctx.store.transition(record.id, "shipped", ship=info, activity="idle")
        results[record.id] = {"state": "shipped", **info}
    return results


def remove_queue_rows(queue_path: Path, shipped_ids: set[str], snapshot: dict[str, Any]) -> list[str]:
    """Drop every queue row whose subjects all shipped; returns the removed rows."""
    if not queue_path.is_file():
        return []
    text = queue_path.read_text(encoding="utf-8")
    names = design_queue.display_names(snapshot)
    gone: dict[int, str] = {}
    for row in design_queue.parse_rows(text, names):
        resolved = design_queue.resolve_row(row, snapshot, names)
        if isinstance(resolved, list) and all(r.id in shipped_ids for r in resolved):
            gone[row.line_no] = row.raw
    if not gone:
        return []
    kept = [ln for i, ln in enumerate(text.splitlines(keepends=True), start=1) if i not in gone]
    tmp = queue_path.with_suffix(".md.tmp")
    tmp.write_text("".join(kept), encoding="utf-8")
    os.replace(tmp, queue_path)
    return list(gone.values())


def register(router: APIRouter, ctx: Any) -> None:
    @router.post("/ship")
    async def ship_records(request: Request) -> dict[str, Any]:
        body = await request.json() if await request.body() else {}
        target_id = body.get("target_id")
        if not isinstance(target_id, str) or not target_id:
            raise HTTPException(status_code=422, detail="ship needs a `target_id`.")
        ids = body.get("ids")
        try:
            if ids is None:
                records = [r for r in ctx.store.list() if r.state == "confirmed"]
            else:
                records = [ctx.store.get(i) for i in ids]
            target = ctx.app.state.targets_registry.get(target_id)
        except DesignError as error:
            raise HTTPException(status_code=error.status, detail=error.message) from error
        except targetsmod.TargetError as error:
            raise HTTPException(status_code=error.status, detail=error.detail) from error
        unready = [r.id for r in records if r.state != "confirmed"]
        if unready:
            raise HTTPException(
                status_code=409, detail=f"Not confirmed, cannot ship: {unready}."
            )
        if not records:
            return {}
        snapshot = ctx.load_snapshot()
        results = ship(records, target, ctx, snapshot)
        shipped = {i for i, r in results.items() if r["state"] == "shipped"}
        if shipped:
            remove_queue_rows(ctx.queue_path, shipped, snapshot)
        return results

    @router.post("/{record_id}/proof")
    async def proof(record_id: str, request: Request) -> dict[str, Any]:
        body = await request.json()
        result = body.get("result")
        note = body.get("note") or ""
        if result not in ("proven", "problem"):
            raise HTTPException(status_code=422, detail="proof.result must be 'proven' or 'problem'.")
        try:
            record = ctx.store.get(record_id)
            proof_info = {"result": result, "note": note}
            if result == "proven":
                return ctx.store.transition(record_id, "proven", proof=proof_info).as_dict()
            steer = "; ".join(p for p in (record.steer, note) if p)
            return ctx.store.transition(
                record_id, "queued", proof=proof_info, steer=steer, activity="idle"
            ).as_dict()
        except DesignError as error:
            raise HTTPException(status_code=error.status, detail=error.message) from error
