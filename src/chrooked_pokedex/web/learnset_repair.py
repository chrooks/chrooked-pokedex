"""Deterministic second-pass repair for a FULL-mode learnset draft.

The slot skeleton (``learnset_skeleton.py``) fixes placement up front, but a
model-filled draft can still ship violations the per-slot validator does not
catch on its own (a weak row seated late, a status row as the capstone, a
descending ladder). This module audits a draft's finished rows against the
same pacing/floor rules the skeleton enforces at build time, plus the
ladder-ascent, level-gap, and capstone rules chat-side auditors
(``scripts/learnset_ladder.py``, ``scripts/stab_pacing.py``) apply to the
Ruleset. One implementation serves both: the web layer imports it for every
FULL-mode draft, the scripts import its level-placement primitive instead of
keeping a private copy.

Repairs never drop a row — a violating row is re-seated at the nearest legal
free level, minimally, everything else held stable. A user anchor (a move the
author demanded by name) is additionally guaranteed to never be dropped, but
may still be re-seated like any other row.

House rules (``learnset_rubric.json`` → ``house_rules``) split two ways:

* ``scrub_draft`` REMOVES rows — the one pass allowed to drop anything. It
  drops banned moves (Glaive Rush, Precipice Blades, Dark Void), protected
  signatures (Excalibur) that were not demanded by name, and the later copy
  of a move that also sits at L0. A user anchor is never scrubbed, only noted.
  Notes start ``"scrub: "``.
* ``audit_draft`` / ``repair_draft`` never drop. The house-rule audits are
  ``late_floor`` (Dragon Dance not before L60), ``status_clump`` (no more
  than 3 status rows in any 10-level span), ``stab_hole`` (consecutive STAB
  rungs no more than 20 levels apart; needs ``stab_types``), ``early_rung``
  (a damaging row by L16), and ``l0_outranks`` (the L0 reward does not
  out-power both of the next two rungs). Only the first two have a legal
  re-seat and are repaired; the other three need a new move — the model's or
  Chris's call — so they stay audit-only and surface as warnings.
"""
from __future__ import annotations

import json
from typing import Any

from .learnset_skeleton import (
    _BAND_PATH,
    _LATE_BP_FLOORS,
    _pacing_bands,
    effective_power,
)

MIN_LEVEL_GAP = 2
# L0 (evolution reward) and L1 (starting kit) are fixed anchors — exempt from
# ascent, gap, and capstone rules, same scope learnset_ladder.py uses.
ANCHOR_MAX = 1
_LEVEL_LO, _LEVEL_HI = 2, 75


def _index(move_pool: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {(r.get("move") or "").casefold(): r for r in move_pool}


def _pool_row(row: dict[str, Any], idx: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    return idx.get((row.get("move") or "").casefold())


def _power(row: dict[str, Any], idx: dict[str, dict[str, Any]]) -> int | None:
    pr = _pool_row(row, idx)
    return effective_power(pr) if pr else None


def _category(row: dict[str, Any], idx: dict[str, dict[str, Any]]) -> str:
    pr = _pool_row(row, idx)
    return (pr.get("category") or "").casefold() if pr else ""


def _type(row: dict[str, Any], idx: dict[str, dict[str, Any]]) -> str:
    pr = _pool_row(row, idx)
    return (pr.get("type") or "") if pr else ""


def _is_status(row: dict[str, Any], idx: dict[str, dict[str, Any]]) -> bool:
    return _category(row, idx) == "status"


def _pacing_ok(level: int, power: int | None, pacing: list[dict[str, Any]]) -> bool:
    """Mirrors ``learnset_skeleton._cap_and_floor_legal`` for a single row."""
    if not isinstance(power, int) or power <= 1:
        return True
    band = next(
        (b for b in pacing if b["level_min"] <= level <= b["level_max"]), None
    )
    cap = band.get("bp_max") if band else None
    if cap is not None and power > cap:
        return False
    floor = next((bp for lvl, bp in _LATE_BP_FLOORS if level >= lvl), 0)
    return power >= floor


def nearest_free_level(
    preferred: int,
    used: set[int],
    lo: int = _LEVEL_LO,
    hi: int = _LEVEL_HI,
    legal: "callable[[int], bool] | None" = None,
) -> int:
    """Closest level to ``preferred`` that is free (and, if given, ``legal``).

    Shared level-placement primitive: ``scripts/stab_pacing.py`` used to keep
    its own ``_nearest_free`` (free-only, no legality check); this is that
    same walk-outward search generalized with an optional legality predicate
    for the pacing/floor-aware repairs here. Falls back to ``preferred`` when
    nothing in range qualifies — a repair never drops a row for want of a
    legal seat.
    """
    for step in range(0, hi - lo + 1):
        for cand in (preferred + step, preferred - step):
            if lo <= cand <= hi and cand not in used and (legal is None or legal(cand)):
                return cand
    return preferred


def house_rules() -> dict[str, Any]:
    """The ``house_rules`` block of ``learnset_rubric.json`` — tune there."""
    return json.loads(_BAND_PATH.read_text("utf-8"))["house_rules"]


def _name(row: dict[str, Any]) -> str:
    return (row.get("move") or "").casefold()


def scrub_draft(
    rows: list[dict[str, Any]],
    move_pool: list[dict[str, Any]],
    anchors: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Drop banned moves, un-anchored protected moves, and L0 duplicates.

    The only pass that removes rows. An anchor is never removed: a banned
    anchor stays with a note, and when a duplicated move is anchored the L0
    copy goes instead of the later one. Returns ``(rows, notes)``; every note
    starts with ``"scrub: "``. Inputs are not mutated.
    """
    del move_pool  # ponytail: rules are by name; the pool is here for signature parity
    rules = house_rules()
    anchor_set = {a.casefold() for a in (anchors or ())}
    banned = {m.casefold() for m in rules.get("banned_moves", ())}
    protected = {m.casefold() for m in rules.get("protected_moves", ())}
    notes: list[str] = []

    kept: list[dict[str, Any]] = []
    for row in rows:
        name, level = _name(row), int(row.get("level", -1))
        if name in banned:
            if name in anchor_set:
                notes.append(
                    f"scrub: kept banned {row['move']} at L{level} — anchor overrides ban"
                )
            else:
                notes.append(f"scrub: removed {row['move']} at L{level} — banned move")
                continue
        elif name in protected and name not in anchor_set:
            notes.append(
                f"scrub: removed {row['move']} at L{level} — protected signature, "
                "not anchored"
            )
            continue
        kept.append(row)

    l0_names = {_name(r) for r in kept if int(r.get("level", -1)) == 0}
    out: list[dict[str, Any]] = []
    for row in kept:
        name, level = _name(row), int(row.get("level", -1))
        if name in l0_names and level != 0 and name not in anchor_set:
            notes.append(
                f"scrub: removed {row['move']} at L{level} — already the L0 reward"
            )
            continue
        if name in l0_names and level == 0 and name in anchor_set and any(
            _name(r) == name and int(r.get("level", -1)) != 0 for r in kept
        ):
            notes.append(
                f"scrub: removed the L0 copy of {row['move']} — the anchored "
                "later copy stays"
            )
            continue
        out.append(dict(row))
    return out, notes


def _damaging(rows: list[dict[str, Any]], idx: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Rows whose move deals damage, in ascending level order."""
    return sorted(
        (r for r in rows if isinstance(_power(r, idx), int) and (_power(r, idx) or 0) > 1),
        key=lambda r: int(r["level"]),
    )


def _status_clumps(
    rows: list[dict[str, Any]], idx: dict[str, dict[str, Any]], rules: dict[str, Any]
) -> list[tuple[int, int, int]]:
    """``(first_level, last_level, count)`` for every over-full status window."""
    window, cap = rules["status_clump"]["window"], rules["status_clump"]["max"]
    levels = sorted(
        int(r["level"]) for r in rows if _is_status(r, idx) and int(r["level"]) > ANCHOR_MAX
    )
    clumps = []
    for i, start in enumerate(levels):
        inside = [lv for lv in levels[i:] if lv - start < window]
        if len(inside) > cap:
            clumps.append((start, inside[-1], len(inside)))
    return clumps


def _house_rule_audits(
    rows: list[dict[str, Any]],
    idx: dict[str, dict[str, Any]],
    stab_types: list[str] | None,
) -> list[str]:
    rules = house_rules()
    problems: list[str] = []

    floors = {m.casefold(): lv for m, lv in rules.get("late_floor", {}).items()}
    for row in rows:
        floor = floors.get(_name(row))
        if floor is not None and int(row["level"]) < floor:
            problems.append(
                f"L{row['level']} {row['move']}: house rule seats it no earlier than L{floor}"
            )

    for first, last, count in _status_clumps(rows, idx, rules):
        problems.append(
            f"status clump: {count} status rows between L{first} and L{last} "
            f"(max {rules['status_clump']['max']} per {rules['status_clump']['window']} levels)"
        )

    damaging = [r for r in _damaging(rows, idx) if int(r["level"]) > 0]
    max_gap = rules["stab_hole_max_levels"]
    for typ in stab_types or ():
        rungs = [r for r in damaging if _type(r, idx).casefold() == typ.casefold()]
        for a, b in zip(rungs, rungs[1:]):
            gap = int(b["level"]) - int(a["level"])
            if gap > max_gap:
                problems.append(
                    f"{typ} STAB hole: L{a['level']} {a['move']} → L{b['level']} "
                    f"{b['move']} is {gap} levels apart (max {max_gap})"
                )

    by = rules["early_rung_by_level"]
    # ponytail: an all-status draft is already flagged by the capstone rule;
    # only a draft that attacks at all is asked to attack early.
    if damaging and not any(_LEVEL_LO <= int(r["level"]) <= by for r in damaging):
        problems.append(f"early rung: no damaging move between L{_LEVEL_LO} and L{by}")

    next_two = damaging[:2]
    if len(next_two) == 2:
        for row in rows:
            if int(row["level"]) != 0:
                continue
            p0 = _power(row, idx) or 0
            if all(p0 > (_power(r, idx) or 0) for r in next_two):
                problems.append(
                    f"L0 {row['move']} ({p0}BP) outranks the next two rungs "
                    + " and ".join(
                        f"L{r['level']} {r['move']} ({_power(r, idx)}BP)" for r in next_two
                    )
                )
    return problems


def _ladder_groups(
    rows: list[dict[str, Any]], idx: dict[str, dict[str, Any]]
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Earned (level > ANCHOR_MAX) attacking rows grouped by (type, category)."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        level = int(row.get("level", -1))
        if level <= ANCHOR_MAX:
            continue
        power = _power(row, idx)
        if not isinstance(power, int) or power <= 1:
            continue
        key = (_type(row, idx), _category(row, idx))
        groups.setdefault(key, []).append(row)
    return groups


def audit_draft(
    rows: list[dict[str, Any]],
    move_pool: list[dict[str, Any]],
    anchors: list[str] | None = None,
    size_bounds: tuple[int, int] | None = None,
    stab_types: list[str] | None = None,
) -> list[str]:
    """Violation strings for a draft; empty means audit-clean.

    Checks: pacing cap + late-game BP floor, per (type, category) ladder
    ascent, minimum level gap, row-count bounds (informational — never
    repaired by re-seating), capstone sanity (status never final unless a
    user anchor; the top two non-status rows are the highest-power rows),
    and the house rules (module docstring); ``stab_hole`` runs only when
    ``stab_types`` is given.
    """
    idx = _index(move_pool)
    pacing = _pacing_bands()
    anchor_set = {a.casefold() for a in (anchors or ())}
    problems: list[str] = []

    if size_bounds is not None:
        lo, hi = size_bounds
        if not (lo <= len(rows) <= hi):
            problems.append(f"row count {len(rows)} outside [{lo}, {hi}]")

    for row in rows:
        level = int(row.get("level", -1))
        power = _power(row, idx)
        if not _pacing_ok(level, power, pacing):
            problems.append(
                f"L{level} {row.get('move')}: fails the pacing cap/late floor "
                f"({power}BP)"
            )

    for (typ, cat), members in _ladder_groups(rows, idx).items():
        ordered = sorted(members, key=lambda r: int(r["level"]))
        peak = -1
        for row in ordered:
            power = _power(row, idx) or 0
            if power < peak:
                problems.append(
                    f"{typ} {cat} ladder: L{row['level']} {row.get('move')} "
                    f"({power}BP) breaks ascending order"
                )
            peak = max(peak, power)

    levels = sorted({int(r["level"]) for r in rows if int(r["level"]) > ANCHOR_MAX})
    for a, b in zip(levels, levels[1:]):
        if b - a < MIN_LEVEL_GAP:
            problems.append(f"levels {a} and {b} sit closer than {MIN_LEVEL_GAP} apart")

    earned = [r for r in rows if int(r.get("level", -1)) > ANCHOR_MAX]
    non_status = [r for r in earned if not _is_status(r, idx)]
    if len(non_status) >= 2:
        by_level = sorted(non_status, key=lambda r: int(r["level"]))
        cap_names = {r["move"] for r in by_level[-2:]}
        by_power = sorted(non_status, key=lambda r: _power(r, idx) or 0, reverse=True)
        top_names = {r["move"] for r in by_power[:2]}
        if cap_names != top_names:
            problems.append(
                "capstone: the final two non-status rows are not the "
                "highest-power rows"
            )
    if earned:
        final = max(earned, key=lambda r: int(r["level"]))
        if _is_status(final, idx) and (final.get("move") or "").casefold() not in anchor_set:
            problems.append(
                f"L{final['level']} {final.get('move')}: a status move holds "
                "the final learnset row"
            )
    problems += _house_rule_audits(rows, idx, stab_types)
    return problems


def assign_to_slots(levels: list[int], items: list[Any], key: Any) -> list[tuple[int, Any]]:
    """Reuse ``levels`` as slots, assigning ``items`` in ascending ``key`` order.

    Shared ladder-ascent primitive: ``scripts/learnset_ladder.py`` (per-species
    Ruleset ladders, ranked by coverage-band label) and ``_reorder_ascent``
    below (a live draft's rows, ranked by effective power) both reseat a
    ladder's rungs within its OWN existing level slots — no new levels
    invented, just the pairing of "which slot gets which rung" resorted.
    ``levels`` and ``items`` must be the same length.
    """
    return list(zip(sorted(levels), sorted(items, key=key)))


def _reorder_ascent(
    work: list[dict[str, Any]], idx: dict[str, dict[str, Any]]
) -> list[str]:
    """Reseat ladder rungs within their OWN existing level slots, ascending by
    power — mirrors scripts/learnset_ladder.py's ``transform``."""
    notes: list[str] = []
    for (typ, cat), members in _ladder_groups(work, idx).items():
        if len(members) < 2:
            continue
        levels = [int(r["level"]) for r in members]
        for slot, row in assign_to_slots(
            levels, members, key=lambda r: (_power(r, idx) or 0, r["move"])
        ):
            old = int(row["level"])
            if old != slot:
                notes.append(
                    f"repair: reseated {row['move']} from L{old} to L{slot} to "
                    f"fix {typ} {cat} ladder ascent order"
                )
                row["level"] = slot
    return notes


def _fix_pacing(work: list[dict[str, Any]], idx: dict[str, dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    pacing = _pacing_bands()
    for row in work:
        level = int(row["level"])
        if level <= ANCHOR_MAX:
            continue
        power = _power(row, idx)
        if _pacing_ok(level, power, pacing):
            continue
        used = {int(r["level"]) for r in work if r is not row and int(r["level"]) > ANCHOR_MAX}
        new_level = nearest_free_level(
            level, used, _LEVEL_LO, _LEVEL_HI,
            legal=lambda cand: _pacing_ok(cand, power, pacing),
        )
        if new_level != level:
            notes.append(
                f"repair: reseated {row['move']} from L{level} to L{new_level} "
                f"— {power}BP fails the pacing cap/late floor at L{level}"
            )
            row["level"] = new_level
    return notes


def _fix_min_gap(work: list[dict[str, Any]], idx: dict[str, dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    pacing = _pacing_bands()
    earned = sorted(
        (r for r in work if int(r["level"]) > ANCHOR_MAX), key=lambda r: int(r["level"])
    )
    used = {int(r["level"]) for r in earned}
    prev = ANCHOR_MAX
    for row in earned:
        level = int(row["level"])
        if level - prev < MIN_LEVEL_GAP:
            used.discard(level)
            power = _power(row, idx)
            target = max(prev + MIN_LEVEL_GAP, level)
            new_level = nearest_free_level(
                target, used, _LEVEL_LO, _LEVEL_HI,
                legal=lambda cand: _pacing_ok(cand, power, pacing),
            )
            if new_level != level:
                notes.append(
                    f"repair: reseated {row['move']} from L{level} to L{new_level} "
                    f"— kept a {MIN_LEVEL_GAP}-level gap from the previous row"
                )
                row["level"] = new_level
            used.add(new_level)
            prev = new_level
        else:
            prev = level
    return notes


def _fix_capstone(
    work: list[dict[str, Any]], idx: dict[str, dict[str, Any]], anchor_set: set[str]
) -> list[str]:
    notes: list[str] = []
    earned = [r for r in work if int(r["level"]) > ANCHOR_MAX]
    if not earned:
        return notes

    final = max(earned, key=lambda r: int(r["level"]))
    if _is_status(final, idx) and (final.get("move") or "").casefold() not in anchor_set:
        candidates = [r for r in earned if not _is_status(r, idx) and r is not final]
        if candidates:
            best = max(candidates, key=lambda r: _power(r, idx) or 0)
            final["level"], best["level"] = best["level"], final["level"]
            notes.append(
                f"repair: swapped {final['move']} and {best['move']} levels — a "
                "status move cannot hold the final learnset row"
            )

    non_status = sorted(
        (r for r in earned if not _is_status(r, idx)), key=lambda r: int(r["level"])
    )
    if len(non_status) >= 2:
        cap_slots = non_status[-2:]
        by_power = sorted(non_status, key=lambda r: _power(r, idx) or 0, reverse=True)
        top_power = by_power[:2]
        cap_names = {r["move"] for r in cap_slots}
        top_names = {r["move"] for r in top_power}
        if cap_names != top_names:
            missing = [r for r in top_power if r["move"] not in cap_names]
            weak_slots = [r for r in cap_slots if r["move"] not in top_names]
            for weak, strong in zip(weak_slots, missing):
                weak["level"], strong["level"] = strong["level"], weak["level"]
                notes.append(
                    f"repair: swapped {weak['move']} and {strong['move']} levels "
                    "— the capstone rows must carry the highest-power moves"
                )
    return notes


def _fix_late_floor(work: list[dict[str, Any]], idx: dict[str, dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    floors = {m.casefold(): lv for m, lv in house_rules().get("late_floor", {}).items()}
    pacing = _pacing_bands()
    for row in work:
        floor = floors.get(_name(row))
        level = int(row["level"])
        if floor is None or level >= floor:
            continue
        used = {int(r["level"]) for r in work if r is not row and int(r["level"]) > ANCHOR_MAX}
        power = _power(row, idx)
        new_level = nearest_free_level(
            floor, used, _LEVEL_LO, _LEVEL_HI,
            legal=lambda cand: cand >= floor and _pacing_ok(cand, power, pacing),
        )
        notes.append(
            f"repair: reseated {row['move']} from L{level} to L{new_level} — "
            f"house rule seats it no earlier than L{floor}"
        )
        row["level"] = new_level
    return notes


def _fix_status_clump(work: list[dict[str, Any]], idx: dict[str, dict[str, Any]]) -> list[str]:
    """Push the surplus status rows of an over-full window to the nearest free
    level past the window, walking upward so a row never lands in a clump."""
    notes: list[str] = []
    rules = house_rules()["status_clump"]
    window, cap = rules["window"], rules["max"]
    status_rows = sorted(
        (r for r in work if _is_status(r, idx) and int(r["level"]) > ANCHOR_MAX),
        key=lambda r: int(r["level"]),
    )
    placed: list[int] = []
    for row in status_rows:
        level = int(row["level"])
        inside = [lv for lv in placed if level - lv < window]
        if len(inside) >= cap:
            target = inside[-cap] + window
            used = {int(r["level"]) for r in work if r is not row and int(r["level"]) > ANCHOR_MAX}
            new_level = nearest_free_level(
                target, used, _LEVEL_LO, _LEVEL_HI, legal=lambda cand: cand >= target
            )
            if new_level != level:
                notes.append(
                    f"repair: reseated {row['move']} from L{level} to L{new_level} — "
                    f"more than {cap} status rows within {window} levels"
                )
                row["level"] = new_level
                level = new_level
        placed.append(level)
        placed.sort()
    return notes


def repair_draft(
    rows: list[dict[str, Any]],
    move_pool: list[dict[str, Any]],
    anchors: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Minimally re-seat rows to fix every re-seatable rule ``audit_draft`` checks.

    The house rules ``stab_hole``, ``early_rung``, and ``l0_outranks`` need a
    new move, not a new level, and are left to the audit. Never drops a row (anchors doubly so — they are only ever re-seated).
    Returns ``(rows, notes)``; each note starts with ``"repair: "``. The
    row-count bound is audit-only and cannot be fixed by re-seating, so it is
    not addressed here.
    """
    idx = _index(move_pool)
    anchor_set = {a.casefold() for a in (anchors or ())}
    work = [dict(r) for r in rows]

    notes: list[str] = []
    notes += _reorder_ascent(work, idx)
    notes += _fix_pacing(work, idx)
    notes += _fix_late_floor(work, idx)
    notes += _fix_status_clump(work, idx)
    notes += _fix_min_gap(work, idx)
    notes += _fix_capstone(work, idx, anchor_set)

    work.sort(key=lambda r: (int(r["level"]), r["move"]))
    return work, notes
