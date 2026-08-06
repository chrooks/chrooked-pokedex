"""Deterministic learnset slot skeleton — code owns placement, the model owns picks.

The learnset suggestor used to hand the model a pool and prose rules, then warn
when the draft drifted (an 85BP move in a ≤60BP band shipped as a warning). This
module inverts that: it builds the slot list — levels, roles, band windows, and
the exact candidate moves per slot — from the species' types, stats, abilities
(via the ability-fuel table), and flavor types. The model only picks one move
per slot and writes the reasoning; ``validate_against_skeleton`` makes a
band/fuel violation impossible rather than warned-about.

Slot roles:
- ``kit``    — the L1 starting rows.
- ``reward`` — the L0 on-evolution reward (evolved forms only).
- ``fuel``   — moves a HARD ability-fuel entry demands (ability_fuel.json).
- ``stab``   — one rung of a STAB ladder (own types, plus ability-granted types:
  stab_grant boosters ARE STAB per Chris's ruling; an -ate grant draws its rungs
  from Normal moves via the entry's filter).
- ``flavor`` — coverage from the species' ``flavor_types`` (what the creature IS
  — a slug gets Water/Poison — never weakness-patching).
- ``status`` — utility rows at fixed levels.
- ``named``  — an exact move a fuel entry names (Moonlight, Toxic, Dream Eater).

Data sources: ``ability_fuel.json`` (the fuel table) and the ``coverage_bands``
table in ``learnset_rubric.json`` (band edges + level windows — shared with
scripts/move_coverage.py and scripts/stab_pacing.py so the three cannot drift).
Both are read fresh per call so edits apply without a restart.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_FUEL_PATH = _HERE / "ability_fuel.json"
_BAND_PATH = _HERE / "learnset_rubric.json"

# The closed set of filter fields a fuel entry may use — validated by
# validate_fuel_table so a typo'd field fails loudly, not silently matches nothing.
FILTER_KEYS = frozenset({
    "move_type", "flags_any", "category", "attacking", "on_stat",
    "has_secondary", "effect_any", "power_max", "accuracy_max", "moves",
})
_SHAPES = frozenset({
    "ate", "flag_boost", "stab_grant", "secondary", "recoil", "multi_hit",
    "status_reward", "healing", "drain", "sleep_payoff", "low_bp",
    "inaccurate_ok", "weather_setter", "weather_rider", "terrain",
})

# Rung counts per ladder kind. Fuel outranks flavor: a dead ability is a bug,
# thin flavor is a missed touch — so trimming drops flavor first (see _PRIORITY).
# The primary ladder starts at band 2: the L1 kit starter IS its ≤50BP rung
# (a lone weak STAB like Twister must not be demanded by two slots at once —
# the repeat-move rule would make that unfillable).
_PRIMARY_RUNGS = 4

# Signature / species-locked moves kept OUT of generated candidate lists — a
# specific mon's identity move, not generic fuel. The type-changing signatures
# (Judgment, Techno Blast, …) default to Normal, so they'd flood every -ate
# fuel slot. An explicit `moves` filter or the broad L0/kit lists still carry
# them. (Moved here from suggest.py so the slot builder and the ability
# shortlist share one set.)
SIGNATURE_MOVES: frozenset[str] = frozenset({
    "judgment", "techno blast", "multi-attack", "tera blast", "tera starstorm",
    "blood moon", "revelation dance", "relic song",
})
_SECONDARY_RUNGS = 3
_GRANTED_RUNGS = 3
_FLAVOR_RUNGS = 2
_STATUS_SLOTS = 4
_STATUS_LEVELS = (8, 20, 30, 40, 50, 60, 64)  # anchors; k slots take an even spread
_MAX_PROMPT_CANDIDATES = 14  # names shown per slot line; validation uses the full set

# Trim priority when the skeleton overflows LEARNSET_SIZE_MAX — higher drops first.
_PRIORITY = {
    "kit": 0, "reward": 0, "fuel": 0, "named": 0,
    "stab": 1, "status": 2, "flavor": 3,
}
_STAB_EXTRA_PRIORITY = 4  # 3rd+ rung of non-primary ladders
_FLAVOR_PRIORITY = 5


def _fuel_table() -> dict[str, Any]:
    """The ability-fuel table, read fresh so edits apply without a restart."""
    return json.loads(_FUEL_PATH.read_text("utf-8"))["abilities"]


def _bands() -> list[dict[str, Any]]:
    """Coverage bands as [{label, lo_power, hi_power, window}], upper-inclusive."""
    edges = json.loads(_BAND_PATH.read_text("utf-8"))["coverage_bands"]["edges"]
    out = []
    for i, edge in enumerate(edges):
        hi = edges[i + 1]["min_power"] - 1 if i + 1 < len(edges) else 10_000
        out.append({
            "label": edge["label"],
            "lo_power": edge["min_power"],
            "hi_power": hi,
            "window": tuple(edge["window"]),
        })
    return out


def offensive_bias(stats: dict[str, Any]) -> str | None:
    """"physical" / "special" for a species leaning one way, else None (mixed)."""
    atk, spa = stats.get("atk"), stats.get("spa")
    if not isinstance(atk, int) or not isinstance(spa, int) or atk == spa:
        return None
    return "physical" if atk > spa else "special"


def _matches(row: dict[str, Any], filt: dict[str, Any], bias: str | None) -> bool:
    """Does one pool row pass one fuel/slot filter?"""
    cat = (row.get("category") or "").casefold()
    if "moves" in filt:
        allowed = {m.casefold() for m in filt["moves"]}
        if (row.get("move") or "").casefold() not in allowed:
            return False
    if "move_type" in filt and (row.get("type") or "").casefold() != filt["move_type"].casefold():
        return False
    if "flags_any" in filt and not set(filt["flags_any"]) & set(row.get("flags") or ()):
        return False
    if "category" in filt and cat != filt["category"].casefold():
        return False
    if filt.get("attacking"):
        power = row.get("power")
        if cat == "status" or not isinstance(power, int) or power <= 1:
            return False
    if filt.get("on_stat") and bias and cat != bias:
        return False
    if filt.get("has_secondary") and not row.get("secondary"):
        return False
    if "effect_any" in filt and (row.get("effect") or "") not in set(filt["effect_any"]):
        return False
    if "power_max" in filt:
        power = row.get("power")
        if not isinstance(power, int) or power > filt["power_max"]:
            return False
    if "accuracy_max" in filt:
        acc = row.get("accuracy")
        if isinstance(acc, int) and acc > filt["accuracy_max"]:
            return False
    return True


def _select(
    pool: list[dict[str, Any]], filt: dict[str, Any], bias: str | None
) -> list[dict[str, Any]]:
    """Pool rows passing the filter; relaxes ``on_stat`` when it empties the set.

    Signature moves stay out unless the filter names them in ``moves`` — an
    explicit named list is a deliberate inclusion.
    """
    if "moves" not in filt:
        pool = [
            r for r in pool
            if (r.get("move") or "").casefold() not in SIGNATURE_MOVES
        ]
    rows = [r for r in pool if _matches(r, filt, bias)]
    if not rows and filt.get("on_stat"):
        relaxed = {k: v for k, v in filt.items() if k != "on_stat"}
        rows = [r for r in pool if _matches(r, relaxed, bias)]
    return rows


def _band_of(power: int, bands: list[dict[str, Any]]) -> dict[str, Any]:
    """The band a base power falls in (upper-inclusive edges)."""
    hit = bands[0]
    for band in bands:
        if power >= band["lo_power"]:
            hit = band
    return hit


def species_fuel(
    ability_slots: dict[str, Any], all_abilities: list[dict[str, Any]]
) -> list[tuple[str, dict[str, Any]]]:
    """The fuel-table entries for a species' current abilities, as (name, entry).

    Ability slots carry display names; the table keys chrooked_ids — the merged
    abilities pool provides the name→id bridge.
    """
    table = _fuel_table()
    id_by_name = {
        (a.get("name") or "").strip().casefold(): a.get("chrooked_id", "")
        for a in all_abilities
    }
    out = []
    seen: set[str] = set()
    for slot in ("primary", "secondary", "hidden"):
        name = ability_slots.get(slot)
        if not name:
            continue
        aid = id_by_name.get(name.strip().casefold(), "")
        if aid in table and aid not in seen:
            seen.add(aid)
            out.append((name, table[aid]))
    return out


def build_skeleton(
    entry: dict[str, Any],
    all_abilities: list[dict[str, Any]],
    move_pool: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the slot skeleton for one species.

    Returns ``{"slots": [...], "leans": [...], "dropped": [...]}``. Each slot is
    ``{level, role, label, candidates, required}`` — candidates are exact pool
    move names; the model must pick one per slot. Leans are the soft-fuel
    directive lines; dropped records slots the pool could not fill.
    """
    from .suggest import LEARNSET_SIZE_MAX  # constants only; no call cycle

    bands = _bands()
    stats = entry.get("stats") or {}
    bias = offensive_bias(stats)
    types = [t for t in entry.get("types") or [] if t]
    fuel = species_fuel(entry.get("abilities") or {}, all_abilities)
    is_evolved = bool((entry.get("evolution") or {}).get("from"))

    leans: list[str] = []
    dropped: list[str] = []
    # (priority, band|None, role, label, filter, required)
    specs: list[dict[str, Any]] = []

    def stab_filter(move_type: str) -> dict[str, Any]:
        return {"move_type": move_type, "attacking": True, "on_stat": True}

    # --- ladders: own types, then ability-granted (fuel first is about SLOT
    # trimming — _PRIORITY keeps fuel/named at 0 so flavor is squeezed out first.
    ladders: list[tuple[str, dict[str, Any], int, int]] = []  # (type, rung filter, rungs, prio)
    for i, t in enumerate(types):
        rungs = _PRIMARY_RUNGS if i == 0 else _SECONDARY_RUNGS
        ladders.append((t, stab_filter(t), rungs, _PRIORITY["stab"]))
    granted_types = {t.casefold() for t in types}
    laddered: set[str] = set()  # fuel entries that became a ladder
    for name, spec in fuel:
        for t in spec.get("stab_types") or []:
            if t.casefold() in granted_types:
                # Pixilate on a pure Fairy-type: the granted type IS an own
                # type, so no new ladder — but the entry's fuel demand (its
                # Normal moves) still applies via the fuel-slot branch below.
                continue
            granted_types.add(t.casefold())
            laddered.add(name)
            rung_filter = dict(spec["filter"]) if spec.get("filter") else stab_filter(t)
            ladders.append((t, rung_filter, _GRANTED_RUNGS, _PRIORITY["stab"]))
    for t in entry.get("flavor_types") or []:
        if t.casefold() in granted_types:
            continue
        ladders.append((t, stab_filter(t), _FLAVOR_RUNGS, _FLAVOR_PRIORITY))

    for lad_i, (t, rung_filter, rungs, prio) in enumerate(ladders):
        is_flavor = prio == _FLAVOR_PRIORITY
        role = "flavor" if is_flavor else "stab"
        # Flavor ladders climb the mid/late bands; STAB ladders climb from the
        # bottom. Rungs = one per band, taken from the top down for short ladders
        # so every ladder still reaches its payoff band.
        band_rows = (
            bands[1:1 + rungs] if is_flavor else bands[len(bands) - rungs:]
        )
        for rung_i, band in enumerate(band_rows):
            filt = dict(rung_filter)
            filt["_band"] = band
            extra = rung_i >= 2 and lad_i > 0 and not is_flavor
            specs.append({
                "priority": _STAB_EXTRA_PRIORITY if extra else prio,
                "band": band, "role": role,
                "label": f"{role.upper()} {t} rung ({band['label']}BP)",
                "filter": filt, "required": True,
            })

    # --- hard fuel without a granted ladder (flag boosters, sheer force, and
    # an -ate whose granted type collapsed into an own-type ladder above)
    for name, spec in fuel:
        if not spec.get("hard") or name in laddered:
            # stab-granting fuel already became a ladder; its named_moves still land.
            pass
        elif spec["shape"] == "status_reward":
            # Satisfied by the status slots below — mark them required instead.
            leans.append(f"{name}: rewards status moves — the STATUS slots are load-bearing.")
        else:
            cands = _select(move_pool, spec.get("filter") or {}, bias)
            cands.sort(key=lambda r: (r.get("power") or 0, r["move"]))
            want = min(spec.get("min_moves", 1), len(cands)) if cands else 0
            if want < spec.get("min_moves", 1):
                dropped.append(
                    f"{name}: pool has only {len(cands)} matching move(s) "
                    f"for its fuel requirement"
                )
            for i in range(want):
                chunk = cands[i * len(cands) // want:(i + 1) * len(cands) // want] or cands
                top_power = max((r.get("power") or 0) for r in chunk)
                band = _band_of(max(top_power, 2), bands)
                note = f" — {spec['note']}" if spec.get("note") else ""
                specs.append({
                    "priority": _PRIORITY["fuel"], "band": band, "role": "fuel",
                    "label": f"FUEL for {name}{note}",
                    "filter": None, "candidates": [r["move"] for r in chunk],
                    "required": True,
                })
        for mv in spec.get("named_moves") or []:
            if any((r.get("move") or "").casefold() == mv.casefold() for r in move_pool):
                specs.append({
                    "priority": _PRIORITY["named"], "band": None, "role": "named",
                    "label": f"NAMED for {name}", "filter": None,
                    "candidates": [mv], "required": True,
                })
        if not spec.get("hard"):
            lean = spec.get("lean") or spec.get("note")
            if lean:
                leans.append(f"{name}: {lean}")

    # --- status slots
    status_moves = sorted(
        r["move"] for r in move_pool if (r.get("category") or "").casefold() == "status"
    )
    for _ in range(min(_STATUS_SLOTS, len(status_moves))):
        specs.append({
            "priority": _PRIORITY["status"], "band": None, "role": "status",
            "label": "STATUS / utility", "filter": None,
            "candidates": status_moves, "required": True,
        })

    # --- kit + reward
    low_band = bands[0]
    kit_filter = stab_filter(types[0]) if types else {"attacking": True}
    kit_stab = [
        r for r in _select(move_pool, kit_filter, bias)
        if isinstance(r.get("power"), int) and r["power"] <= low_band["hi_power"]
    ]
    specs.append({
        "priority": _PRIORITY["kit"], "band": None, "role": "kit", "level": 1,
        "label": f"KIT — weak {types[0] if types else ''} STAB starter (≤{low_band['hi_power']}BP)",
        "filter": None,
        "candidates": [r["move"] for r in kit_stab] or [r["move"] for r in move_pool],
        "required": True,
    })
    kit_util = sorted(
        r["move"] for r in move_pool
        if (r.get("category") or "").casefold() == "status"
        or (isinstance(r.get("power"), int) and 1 < r["power"] <= low_band["hi_power"])
    )
    specs.append({
        "priority": _PRIORITY["kit"], "band": None, "role": "kit", "level": 1,
        "label": "KIT — utility or weak attack", "filter": None,
        "candidates": kit_util, "required": True,
    })
    if is_evolved:
        specs.append({
            "priority": _PRIORITY["reward"], "band": None, "role": "reward", "level": 0,
            "label": "L0 EVOLUTION REWARD — the line's signature payoff "
                     "([CUSTOM] moves are prime picks)",
            "filter": None, "candidates": [r["move"] for r in move_pool],
            "required": True,
        })

    # --- resolve candidates for band rungs, drop unfillable slots
    resolved: list[dict[str, Any]] = []
    for spec in specs:
        if spec.get("candidates") is None:
            filt = dict(spec["filter"])
            band = filt.pop("_band")
            rows = _select(move_pool, filt, bias)
            rows = [
                r for r in rows
                if isinstance(r.get("power"), int)
                and band["lo_power"] <= r["power"] <= band["hi_power"]
            ]
            if not rows:
                dropped.append(f"{spec['label']}: no pool move fits — slot dropped")
                continue
            rows.sort(key=lambda r: (-(r.get("power") or 0), r["move"]))
            spec = {**spec, "candidates": [r["move"] for r in rows]}
        resolved.append(spec)

    # Singleton-collision guard: a move a singleton slot claims outright is
    # struck from every other slot's list — two slots demanding the same lone
    # move would be unfillable under the repeat-move rule (one Twister cannot
    # fill both the kit and a rung). A slot emptied by the strike is dropped.
    claimed: set[str] = set()
    survivors: list[dict[str, Any]] = []
    for spec in resolved:
        cands = spec["candidates"]
        if len(cands) == 1 and spec.get("level") != 0:
            key = cands[0].casefold()
            if key in claimed:  # two singletons want the same lone move
                dropped.append(
                    f"{spec['label']}: its only candidate is already claimed "
                    "by another slot — slot dropped"
                )
                continue
            claimed.add(key)
        survivors.append(spec)
    resolved = []
    for spec in survivors:
        # The L0 reward is exempt from the claim-strike: the repeat rule allows
        # a move at L0 AND one non-zero level, so a singleton's claim must not
        # strike the reward list (Luster Cannon can be the L49 rung and the L0
        # reward at once).
        if spec.get("level") != 0 and len(spec["candidates"]) > 1:
            trimmed = [
                c for c in spec["candidates"] if c.casefold() not in claimed
            ]
            if not trimmed:
                # Keeping the claimed moves would let a fill here starve the
                # singleton slot — drop this slot instead (tiny-pool case only).
                dropped.append(
                    f"{spec['label']}: every candidate is claimed by a "
                    "single-option slot — slot dropped"
                )
                continue
            spec = {**spec, "candidates": trimmed}
        resolved.append(spec)

    # --- trim to size (drop highest priority number first, last-added first)
    while len(resolved) > LEARNSET_SIZE_MAX:
        victim = max(
            reversed(resolved),
            key=lambda s: (s["priority"], resolved.index(s)),
        )
        if victim["priority"] == 0:
            break  # never trim kit/reward/fuel/named below the cap
        dropped.append(f"{victim['label']}: trimmed to fit the size cap")
        resolved.remove(victim)

    _assign_levels(resolved)
    resolved.sort(key=lambda s: (s["level"], s["role"] != "kit", s["label"]))
    slots = [
        {k: s[k] for k in ("level", "role", "label", "candidates", "required")}
        for s in resolved
    ]
    return {"slots": slots, "leans": leans, "dropped": dropped}


def _assign_levels(specs: list[dict[str, Any]]) -> None:
    """Give every slot a deterministic level, in place.

    Banded slots spread evenly inside their band's level window; status/named
    slots take an even spread of the fixed anchors; kit/reward levels are already
    pinned. Duplicate levels (beyond the L1 kit pair) bump upward to stay unique.
    """
    by_band: dict[str, list[dict[str, Any]]] = {}
    free: list[dict[str, Any]] = []
    for spec in specs:
        if spec.get("level") is not None:
            continue
        if spec.get("band"):
            by_band.setdefault(spec["band"]["label"], []).append(spec)
        else:
            free.append(spec)
    for group in by_band.values():
        lo, hi = group[0]["band"]["window"]
        lo = max(lo, 5)  # L1-4 belongs to the kit
        for i, spec in enumerate(group):
            spec["level"] = lo + (i * (hi - lo)) // max(len(group), 1)
    anchors = _STATUS_LEVELS
    for i, spec in enumerate(free):
        spec["level"] = anchors[(i * len(anchors)) // max(len(free), 1)]
    # dedupe (kit L1 pair and the L0 reward stay put)
    taken: set[int] = set()
    for spec in sorted(specs, key=lambda s: s["level"]):
        if spec["level"] <= 1:
            continue
        level = spec["level"]
        while level in taken:
            level += 1
        spec["level"] = min(level, 70)
        while spec["level"] in taken:  # clamped collision walks back down
            spec["level"] -= 1
        taken.add(spec["level"])


def format_skeleton(skeleton: dict[str, Any]) -> str:
    """The skeleton as the prompt block the model fills in."""
    lines = [
        "SLOT SKELETON — the learnset's structure is FIXED. Produce EXACTLY one "
        "row per slot below, at the stated level, choosing a move from that "
        "slot's allowed list. No other rows, no other levels.",
    ]
    for slot in skeleton["slots"]:
        cands = slot["candidates"]
        shown = ", ".join(cands[:_MAX_PROMPT_CANDIDATES])
        overflow = len(cands) - _MAX_PROMPT_CANDIDATES
        more = f" (+{overflow} more in the pool)" if overflow > 0 else ""
        if slot["role"] == "status" and len(cands) > _MAX_PROMPT_CANDIDATES:
            shown, more = "any STATUS move from the pool", ""
        if slot["role"] == "reward":
            shown, more = "any pool move worthy of the slot", ""
        lines.append(f"- L{slot['level']} · {slot['label']} → pick one of: {shown}{more}")
    for lean in skeleton["leans"]:
        lines.append(f"- LEAN: {lean}")
    return "\n".join(lines)


def validate_against_skeleton(
    rows: list[dict[str, Any]], skeleton: dict[str, Any]
) -> list[str]:
    """Hard per-slot check of a draft against the skeleton. Returns error strings."""
    errors: list[str] = []
    slots_by_level: dict[int, list[dict[str, Any]]] = {}
    for slot in skeleton["slots"]:
        slots_by_level.setdefault(slot["level"], []).append(slot)
    rows_by_level: dict[int, list[str]] = {}
    for row in rows:
        rows_by_level.setdefault(int(row.get("level", -1)), []).append(row.get("move", ""))

    for level, slots in sorted(slots_by_level.items()):
        moves = list(rows_by_level.get(level, []))
        if len(moves) != len(slots):
            errors.append(
                f"level {level}: expected {len(slots)} row(s) "
                f"({'; '.join(s['label'] for s in slots)}), got {len(moves)}"
            )
            continue
        # Greedy match: narrowest slot first so the broad slot takes the leftover.
        for slot in sorted(slots, key=lambda s: len(s["candidates"])):
            allowed = {c.casefold() for c in slot["candidates"]}
            hit = next((m for m in moves if m.casefold() in allowed), None)
            if hit is None:
                errors.append(
                    f"level {level}: no row satisfies '{slot['label']}' "
                    f"(allowed: {', '.join(slot['candidates'][:8])}…)"
                )
            else:
                moves.remove(hit)
    for level, moves in sorted(rows_by_level.items()):
        if level not in slots_by_level:
            errors.append(
                f"level {level}: row(s) {', '.join(moves)} at a level with no slot"
            )
    return errors


def validate_fuel_table() -> list[str]:
    """Structural check of ability_fuel.json — the load-time drift guard.

    Verifies every filter field is in the closed set, every flag is a real
    MOVE_FLAG, and every shape is known. Returns problem strings (tests assert
    empty); does not check ability ids against the dex — that needs the snapshot
    and lives in the tripwire test.
    """
    from ..model.schema import MOVE_FLAGS

    problems: list[str] = []
    for aid, spec in _fuel_table().items():
        where = f"ability_fuel.json:{aid}"
        if spec.get("shape") not in _SHAPES:
            problems.append(f"{where}: unknown shape {spec.get('shape')!r}")
        filt = spec.get("filter") or {}
        unknown = set(filt) - FILTER_KEYS
        if unknown:
            problems.append(f"{where}: unknown filter field(s) {sorted(unknown)}")
        bad_flags = set(filt.get("flags_any") or ()) - MOVE_FLAGS
        if bad_flags:
            problems.append(f"{where}: unknown move flag(s) {sorted(bad_flags)}")
        if spec.get("hard") and not (filt or spec.get("stab_types") or spec.get("named_moves")):
            problems.append(f"{where}: hard entry with nothing to gate on")
    return problems
