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
import re
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
# Both own-type ladders run ALL five bands (Chris's grid: L5 = primary's first
# rung, L9 = secondary's — a Steel line owes its Metal Claw-class starter too),
# PLUS a second ≤50BP rung in the teens (2026-08-26 ruling): the early levels
# are where the player spends the most game, so a type's STAB must not go
# silent from L9 to the 50-75BP rung in the twenties.
# The L1 kit starter is a weak NORMAL attack (Scratch/Tackle class), so it no
# longer collides with the primary ladder's ≤50BP rung.
_PRIMARY_RUNGS = 5
_SECONDARY_RUNGS = 5

# The L1 kit starter shortlist (2026-08-26 ruling): the physical side is the
# canon Tackle class; the special side is our special Tackle clone. The slot
# falls back to the old broad weak-attack search only when none of these are
# in the pool (the special clone predates nothing — until it is accepted and
# written, special attackers keep the fallback).
_KIT_STARTERS: dict[str, tuple[str, ...]] = {
    "physical": ("Tackle", "Pound", "Scratch"),
    "special": ("Flicker",),
}

# Signature / species-locked moves kept OUT of generated candidate lists — a
# specific mon's identity move, not generic fuel. The type-changing signatures
# (Judgment, Techno Blast, …) default to Normal, so they'd flood every -ate
# fuel slot. An explicit `moves` filter or the broad L0/kit lists still carry
# them. (Moved here from suggest.py so the slot builder and the ability
# shortlist share one set.)
SIGNATURE_MOVES: frozenset[str] = frozenset({
    "judgment", "techno blast", "multi-attack", "tera blast", "tera starstorm",
    "blood moon", "revelation dance", "relic song", "moongeist beam",
})


def is_battle_gimmick(row: dict[str, Any]) -> bool:
    """True for a Z-move or a Dynamax/G-Max move — never a level-up learnset row.

    Dynamax moves all carry effect ``max_move``; Max Guard hides behind
    ``protect``, so the name prefix catches it. Z-moves share no effect or flag —
    their only tell in the pool row is 1 PP. Struggle, Sketch, and Revival
    Blessing also carry 1 PP and ride along; none belongs in a generated
    learnset either (add Revival Blessing by hand if a species ever wants it).

    Applied once where the pool enters ``suggest_learnset``, so the prompt text,
    the slot skeleton, and the draft validator all see the same trimmed pool.
    """
    if (row.get("effect") or "") == "max_move":
        return True
    if (row.get("move") or "").startswith(("Max ", "G-Max ")):
        return True
    pp = row.get("pp")
    return isinstance(pp, int) and pp <= 1


_GRANTED_RUNGS = 3
_FLAVOR_RUNGS = 2
_DIRECTION_RUNGS = 3  # a type the user's direction names gets a real ladder
_STATUS_SLOTS = 4
# Chris's cadence ruling (2026-08-26, superseding 2026-08-07): L1 is the kit,
# the first rung lands at L5, and rows step 3-4 levels apart. The tail relaxes —
# no forced L70 payoff back-to-back with L69; the last position sits at L72.
# The grid IS the level plan; band windows steer WHICH position a rung takes.
_GRID: tuple[int, ...] = (
    5, 9, 12, 16, 19, 23, 26, 30, 33, 37,
    40, 44, 47, 51, 54, 58, 61, 65, 68, 72,
)
# Late-game BP floors, same ruling: an attacking row at L50+ carries ≥90BP,
# at L60+ ≥100BP. Enforced by candidate trim, like the pacing caps.
_LATE_BP_FLOORS: tuple[tuple[int, int], ...] = ((60, 100), (50, 90))
# Density target: the July 2026 audit put curated learnsets at median 21 rows.
# A skeleton landing under this widens with extra status slots and duplicate
# mid/late STAB rungs before giving up.
_TARGET_SLOTS = 20
_STATUS_EXTRA = 2  # widening may add at most this many status slots
# Weave pattern: every third grid position holds a status/utility row, the
# rest hold attacking rungs in ascending-band order.
_STATUS_EVERY = 3
_MAX_PROMPT_CANDIDATES = 14  # names shown per slot line; validation uses the full set

# Trim priority when the skeleton overflows LEARNSET_SIZE_MAX — higher drops first.
_PRIORITY = {
    "kit": 0, "reward": 0, "fuel": 0, "named": 0,
    "stab": 1, "status": 2, "flavor": 3,
}
# 3rd+ rung of non-primary OWN/granted ladders. Kept BELOW direction/flavor
# coverage (2026-08-26 Granbull ruling): trimming a STAB ladder's payoff rungs
# to keep a coverage ladder's 100BP rung stalled Ground at 60BP from L26 up.
_STAB_EXTRA_PRIORITY = 2
_WIDENER_PRIORITY = 4  # density-pad duplicate rungs — first attackers to trim
_FLAVOR_PRIORITY = 5


def _fuel_table() -> dict[str, Any]:
    """The ability-fuel table, read fresh so edits apply without a restart."""
    return json.loads(_FUEL_PATH.read_text("utf-8"))["abilities"]


def _rung_exclusions() -> frozenset[str]:
    """Chris's curated non-rung moves (Foul Play class), as slugs.

    Shared with scripts/move_coverage.py via the band Contract: these pass the
    mechanical filters but are too flavor- or effect-specific to serve as a
    generic STAB/flavor rung. Band rung candidates skip them; the L0 reward,
    kit, and fuel lists still may carry them.
    """
    data = json.loads(_BAND_PATH.read_text("utf-8"))["coverage_bands"]
    return frozenset(data.get("rung_exclusions") or ())


def _slug(name: str) -> str:
    """A move display name as its comparison slug (``Foul Play`` → ``foulplay``)."""
    return "".join(ch for ch in name.casefold() if ch.isalnum())


# Fixed two/three-hitters hide behind a plain effect; the description is the
# only tell (Double Kick "twice", Triple Dive "three times").
_TWO_HIT_RE = re.compile(r"\btwice\b|\btwo times\b", re.IGNORECASE)
_THREE_HIT_RE = re.compile(r"\bthree times\b", re.IGNORECASE)
_MULTI_HIT_AVG = 3.5  # 2-to-5 hit movers: avg of the hit range, per Chris
_TRIPLE_KICK_MULT = 6  # 1x+2x+3x ramp across three hits


def effective_power(row: dict[str, Any]) -> int | None:
    """A move's banding power: base power × average hit count (2026-08-26).

    Multi-hit movers (Bullet Seed 25) list per-hit BP, so raw power banded
    them as starter-tier and they never surfaced as real rungs. Filters like
    ``power_max`` (Technician fuel) still read RAW power — the boost there is
    per hit by design; only band placement and pacing caps use this.
    """
    power = row.get("power")
    if not isinstance(power, int) or power <= 1:
        return power
    effect = row.get("effect") or ""
    desc = row.get("description") or ""
    if effect == "multi_hit":
        return round(power * _MULTI_HIT_AVG)
    if effect == "triple_kick":
        return power * _TRIPLE_KICK_MULT
    if _THREE_HIT_RE.search(desc):
        return power * 3
    if _TWO_HIT_RE.search(desc):
        return power * 2
    return power


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
    direction: str | None = None,
    anchors: list[str] | None = None,
) -> dict[str, Any]:
    """Build the slot skeleton for one species.

    Returns ``{"slots": [...], "leans": [...], "dropped": [...]}``. Each slot is
    ``{level, role, label, candidates, required}`` — candidates are exact pool
    move names; the model must pick one per slot. Leans are the soft-fuel
    directive lines; dropped records slots that did not survive, each tagged
    ``crowded: `` (another slot took the space — worth telling the author) or
    ``unfillable: `` (the pool had nothing — noise, and not the author's doing).

    ``direction`` is the user's free-text steer; any pool type it names grows a
    real coverage ladder — a redirect asking for "flying and grass coverage"
    must change the structure, not just the prose the model reads.

    ``anchors`` are moves the user demands by name. Each becomes its own
    single-candidate ``named`` slot, which the trim never drops and the
    collision guard reserves — the structural half of the mandate the rubric
    could only ask for in prose.
    """
    from .suggest import LEARNSET_SIZE_MAX  # constants only; no call cycle

    bands = _bands()
    stats = entry.get("stats") or {}
    bias = offensive_bias(stats)
    types = [t for t in entry.get("types") or [] if t]
    fuel = species_fuel(entry.get("abilities") or {}, all_abilities)
    is_evolved = bool((entry.get("evolution") or {}).get("from"))
    # Moves any fuel entry's filter matches — starred in the prompt and sorted
    # first in rung candidate lists, so an ability-boosted 80BP pick is not
    # shadowed by a stronger unmarked one (2026-08-26 Granbull ruling: Play
    # Rough outshone Lovely Bite, the Strong Jaw STAB fang built for the slot).
    fuel_moves = {
        r["move"]
        for _name, spec in fuel
        if spec.get("filter")
        for r in _select(move_pool, spec["filter"], bias)
    }

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
    # Direction-named coverage first (survives trimming longer than generic
    # flavor): any pool type the user's steer mentions grows a real ladder.
    pool_types = {r.get("type") for r in move_pool if r.get("type")}
    direction_words = (direction or "").casefold()
    # A direction naming a MOVE ("give it Fire Fang") is a mandate for that
    # move, not for Fire coverage — strip pool move names before type matching
    # so they cannot spawn phantom coverage ladders (2026-08-26 Granbull
    # ruling: "Fire Fang" in the steer grew a Fire ladder demanding a 100BP
    # payoff). A move named exactly after a type (Psychic) stays: that word
    # doubles as a type steer.
    type_names = {t.casefold() for t in pool_types}
    for r in move_pool:
        name = (r.get("move") or "").casefold()
        if name and name not in type_names and name in direction_words:
            direction_words = direction_words.replace(name, " ")
    for t in sorted(pool_types):
        if t.casefold() in granted_types or t.casefold() not in direction_words:
            continue
        granted_types.add(t.casefold())
        ladders.append((t, stab_filter(t), _DIRECTION_RUNGS, _PRIORITY["flavor"]))
    for t in entry.get("flavor_types") or []:
        if t.casefold() in granted_types:
            continue
        ladders.append((t, stab_filter(t), _FLAVOR_RUNGS, _FLAVOR_PRIORITY))

    for lad_i, (t, rung_filter, rungs, prio) in enumerate(ladders):
        is_flavor = prio in (_FLAVOR_PRIORITY, _PRIORITY["flavor"])
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
        if not is_flavor and rungs >= len(bands):
            # Own-type ladders get a SECOND ≤50BP rung in the teens — the
            # early game is where playtime concentrates, so a type's STAB
            # must not go silent between L9 and the 50-75BP rung in the 20s.
            filt = dict(rung_filter)
            filt["_band"] = bands[0]
            specs.append({
                "priority": prio, "band": bands[0], "role": role,
                "label": f"{role.upper()} {t} rung (≤{bands[0]['hi_power']}BP, "
                         "second early rung)",
                "filter": filt, "required": True, "early_extra": True,
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
            cands.sort(key=lambda r: (effective_power(r) or 0, r["move"]))
            want = min(spec.get("min_moves", 1), len(cands)) if cands else 0
            if want < spec.get("min_moves", 1):
                dropped.append(
                    f"unfillable: {name}: pool has only {len(cands)} matching "
                    f"move(s) for its fuel requirement"
                )
            for i in range(want):
                chunk = cands[i * len(cands) // want:(i + 1) * len(cands) // want] or cands
                top_power = max((effective_power(r) or 0) for r in chunk)
                band = _band_of(max(top_power, 2), bands)
                note = f" — {spec['note']}" if spec.get("note") else ""
                specs.append({
                    "priority": _PRIORITY["fuel"], "band": band, "role": "fuel",
                    "label": f"FUEL for {name}{note}",
                    "filter": None, "candidates": [r["move"] for r in chunk],
                    "powers": {r["move"]: effective_power(r) for r in chunk},
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

    # --- anchors: moves the user named outright. One single-candidate slot each,
    # emitted after fuel so they count toward _TARGET_SLOTS (suppressing density
    # padding) and sit ahead of status in the utility level walk. _PRIORITY
    # "named" is 0, so the trim pass never drops one. Band stays None on purpose:
    # the utility branch of _assign_levels skips _cap_and_floor_legal, so a
    # banded anchor whose lone candidate fails the pacing cap at every free
    # position would be dropped outright — a guaranteed anchor turned into a lost
    # one. Pacing-exempt and seated beats paced and missing.
    anchor_seen = {
        c.casefold()
        for s in specs
        if s["role"] == "named"
        for c in s["candidates"]
    }
    for raw in anchors or []:
        row = next(
            (r for r in move_pool if (r.get("move") or "").casefold() == str(raw).casefold()),
            None,
        )
        if row is None:
            continue  # boundary already rejects these; stay total if bypassed
        canon = row["move"]
        if canon.casefold() in anchor_seen:
            continue
        anchor_seen.add(canon.casefold())
        specs.append({
            "priority": _PRIORITY["named"], "band": None, "role": "named",
            "label": f"ANCHOR — the user named {canon}", "filter": None,
            "candidates": [canon], "required": True, "anchor": True,
        })

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

    # --- kit + reward. The L1 kit is a weak NORMAL starter (Scratch/Tackle
    # class) plus a basic status row (Leer/Growl class) — the type ladders own
    # everything from L5 up, so the kit never collides with a rung.
    low_band = bands[0]
    # The starter slot is a fixed shortlist (Tackle class + the special clone),
    # sided by the offensive bias; the broad weak-attack search is only the
    # fallback for a pool missing all of them.
    starter_names = {
        n.casefold()
        for side, names in _KIT_STARTERS.items()
        if bias in (None, side)
        for n in names
    }
    kit_stab = [
        r for r in move_pool
        if (r.get("move") or "").casefold() in starter_names
    ] or [
        r for r in _select(
            move_pool,
            {"move_type": "Normal", "attacking": True, "on_stat": True},
            bias,
        )
        if isinstance(r.get("power"), int) and r["power"] <= low_band["hi_power"]
    ] or [
        r for r in _select(move_pool, {"attacking": True}, bias)
        if isinstance(r.get("power"), int) and r["power"] <= low_band["hi_power"]
    ]
    specs.append({
        "priority": _PRIORITY["kit"], "band": None, "role": "kit", "level": 1,
        "label": f"KIT — weak starter attack (≤{low_band['hi_power']}BP, Scratch/Tackle class)",
        "filter": None,
        "candidates": [r["move"] for r in kit_stab] or [r["move"] for r in move_pool],
        "required": True,
    })
    status_or_weak = sorted(
        r["move"] for r in move_pool
        if (r.get("category") or "").casefold() == "status"
        or (isinstance(r.get("power"), int) and 1 < r["power"] <= low_band["hi_power"])
    )
    specs.append({
        "priority": _PRIORITY["kit"], "band": None, "role": "kit", "level": 1,
        "label": "KIT — basic status (Leer/Growl class)", "filter": None,
        "candidates": status_moves or status_or_weak, "required": True,
    })
    if is_evolved:
        specs.append({
            "priority": _PRIORITY["reward"], "band": None, "role": "reward", "level": 0,
            "label": "L0 EVOLUTION REWARD — the line's signature payoff "
                     "([CUSTOM] moves are prime picks)",
            "filter": None, "candidates": [r["move"] for r in move_pool],
            "required": True,
        })

    # --- widening pass: a sparse skeleton (mono-type, thin ladders) reads as
    # "very little moves, very spaced out". Pad toward the density target with
    # extra status slots, then duplicate mid/late rungs of the own-type ladders.
    wideners: list[dict[str, Any]] = []
    if status_moves:
        for _ in range(_STATUS_EXTRA):
            wideners.append({
                "priority": _PRIORITY["status"], "band": None, "role": "status",
                "label": "STATUS / utility", "filter": None,
                "candidates": status_moves, "required": True,
            })
    for t in types:
        for band in reversed(bands[1:4]):  # 51-75 · 76-90 · 91-110, payoff first
            wideners.append({
                "priority": _WIDENER_PRIORITY, "band": band, "role": "stab",
                "label": f"STAB {t} rung ({band['label']}BP)",
                "filter": {**stab_filter(t), "_band": band}, "required": True,
            })
    while len(specs) < _TARGET_SLOTS and wideners:
        specs.append(wideners.pop(0))

    # --- resolve candidates for band rungs, drop unfillable slots
    resolved: list[dict[str, Any]] = []
    for spec in specs:
        if spec.get("candidates") is None:
            filt = dict(spec["filter"])
            band = filt.pop("_band")

            exclusions = _rung_exclusions()

            def in_band(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
                # Banding reads EFFECTIVE power (multi-hit = BP × avg hits),
                # so Bullet Seed-class movers surface as real mid rungs.
                return [
                    r for r in rows
                    if isinstance(effective_power(r), int)
                    and band["lo_power"] <= effective_power(r) <= band["hi_power"]
                    and _slug(r.get("move") or "") not in exclusions
                ]

            rows = in_band(_select(move_pool, filt, bias))
            if not rows and filt.get("on_stat"):
                # Relax AFTER the band cut, not before: a physical Bug species
                # whose only 91-110BP Bug move is special still deserves the
                # rung — the off-stat pick beats a hole in the ladder. The
                # July sweep found 273 rungs dropped to this ordering bug.
                relaxed = {k: v for k, v in filt.items() if k != "on_stat"}
                rows = in_band(_select(move_pool, relaxed, bias))
            if not rows:
                dropped.append(
                    f"unfillable: {spec['label']}: no pool move fits — slot dropped"
                )
                continue
            rows.sort(
                key=lambda r: (
                    r["move"] not in fuel_moves,
                    -(effective_power(r) or 0),
                    r["move"],
                )
            )
            spec = {
                **spec,
                "candidates": [r["move"] for r in rows],
                "powers": {r["move"]: effective_power(r) for r in rows},
            }
        resolved.append(spec)

    # Singleton-collision guard: a move a singleton slot claims outright is
    # struck from every other slot's list — two slots demanding the same lone
    # move would be unfillable under the repeat-move rule (one Twister cannot
    # fill both the kit and a rung). A slot emptied by the strike is dropped.
    # Anchors claim FIRST. The pass is otherwise first-come, and in a narrow pool
    # a generated rung whose candidate list collapsed to the same lone move would
    # take it and strike the anchor slot out of existence — the user's explicit
    # demand losing to a slot the code invented. Order the claim, not the output.
    claimed: set[str] = set()
    struck: set[int] = set()
    claim_order = sorted(
        range(len(resolved)), key=lambda i: 0 if resolved[i].get("anchor") else 1
    )
    for i in claim_order:
        spec = resolved[i]
        cands = spec["candidates"]
        if len(cands) == 1 and spec.get("level") != 0:
            key = cands[0].casefold()
            if key in claimed:  # two singletons want the same lone move
                dropped.append(
                    f"crowded: {spec['label']} lost its only candidate to "
                    "another slot that claimed the same move"
                )
                struck.add(i)
                continue
            claimed.add(key)
    survivors: list[dict[str, Any]] = [
        spec for i, spec in enumerate(resolved) if i not in struck
    ]
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
                    f"crowded: {spec['label']} lost every candidate to slots "
                    "that claimed those moves outright"
                )
                continue
            spec = {**spec, "candidates": trimmed}
        resolved.append(spec)

    # --- trim to size: the grid holds len(_GRID) non-pinned rows, and the
    # overall cap still applies (drop highest priority number, last-added first)
    pinned = sum(1 for s in resolved if s.get("level") is not None)
    cap = min(LEARNSET_SIZE_MAX, pinned + len(_GRID))
    while len(resolved) > cap:
        victim = max(
            reversed(resolved),
            key=lambda s: (s["priority"], resolved.index(s)),
        )
        if victim["priority"] == 0:
            break  # never trim kit/reward/fuel/named below the cap
        dropped.append(
            f"crowded: {victim['label']} was trimmed — the learnset ran out of "
            "room before this slot"
        )
        resolved.remove(victim)

    empty = _assign_levels(resolved)
    for spec in empty:
        dropped.append(
            f"unfillable: {spec['label']}: no candidate satisfies the pacing "
            "cap and late-game BP floor at its grid level — slot dropped"
        )
        resolved.remove(spec)
    resolved.sort(key=lambda s: (s["level"], s["role"] != "kit", s["label"]))
    slots = [
        {
            **{k: s[k] for k in ("level", "role", "label", "candidates", "required")},
            "fuel": [c for c in s["candidates"] if c in fuel_moves],
        }
        for s in resolved
    ]
    return {"slots": slots, "leans": leans, "dropped": dropped}


def _pacing_bands() -> list[dict[str, Any]]:
    """The level→BP pacing table (the UI badge source), read fresh."""
    return json.loads(_BAND_PATH.read_text("utf-8"))["bands"]


def _pacing_allows(level: int, power: int, pacing: list[dict[str, Any]]) -> bool:
    """True when a move of ``power`` at ``level`` draws no pacing badge.

    Mirrors the advisory check in suggest.py: the FIRST pacing band containing
    the level decides, and a band with no ``bp_max`` allows anything.
    """
    band = next(
        (b for b in pacing if b["level_min"] <= level <= b["level_max"]), None
    )
    cap = band.get("bp_max") if band else None
    return cap is None or power <= cap


def _cap_and_floor_legal(
    spec: dict[str, Any],
    powers: dict[str, Any],
    level: int,
    pacing: list[dict[str, Any]],
) -> list[str]:
    """Candidates whose BP fits the pacing cap AND late-game floor at ``level``."""
    floor = next((bp for lvl, bp in _LATE_BP_FLOORS if level >= lvl), 0)
    return [
        c for c in spec["candidates"]
        if not isinstance(powers.get(c), int) or powers[c] <= 1
        or (_pacing_allows(level, powers[c], pacing) and powers[c] >= floor)
    ]


def _assign_levels(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Weave every non-pinned slot onto the fixed 3-4-level grid, in place.

    Chris's cadence: L1 is the kit, the first rung lands at L5, and rows step
    3-4 levels apart (see _GRID). Attacking slots take grid positions in
    ascending-band order (primary's first rung at L5, the secondary's next),
    each PREFERRING a position inside its band's level window (the coverage
    Contract) so rungs land where the band plan says they belong instead of
    front-loading. At each assigned level the candidate list trims to what
    the level→BP pacing cap AND the late-game floors (≥90BP at L50+, ≥100BP
    at L60+) allow, so the workbench badge cannot fire whatever the model
    picks. Returns slots left with NO legal candidate (caller drops them).
    """
    pacing = _pacing_bands()
    attacking: list[dict[str, Any]] = []
    utility: list[dict[str, Any]] = []
    for spec in specs:
        if spec.get("level") is not None:
            continue
        if spec.get("band"):
            attacking.append(spec)
        else:
            utility.append(spec)
    # Ascending bands; within a band the least-trimmable slot (primary STAB,
    # fuel) goes first so it gets the earlier grid step. Stable on insert
    # order, which already runs primary → secondary → granted → flavor.
    # The second early ≤50 rungs sort AFTER both first rungs so the opening
    # keeps its primary-at-L5 / secondary-next shape.
    attacking.sort(
        key=lambda s: (s["band"]["lo_power"], bool(s.get("early_extra")))
    )

    # Each attacking slot prefers the earliest free grid position INSIDE its
    # band's window that keeps the WHOLE candidate list; failing that, the
    # best (in-window, full-list, most-survivors) position anywhere. Plain
    # earliest-any starved lists — a 91-110 rung grabbed L49 (cap 99) and
    # lost Earthquake to keep only its 95BP sibling. Utility rows then fill
    # the holes the attack ladder leaves, sprinkling them through the list.
    free = list(_GRID)
    empty: list[dict[str, Any]] = []
    for spec in attacking:
        powers = spec["powers"]
        window_lo, window_hi = spec["band"].get("window") or (1, 100)
        best_pos: int | None = None
        best_legal: list[str] = []
        best_key = (-1, -1, -1)
        for position in free:
            legal = _cap_and_floor_legal(spec, powers, position, pacing)
            if not legal:
                continue
            in_window = window_lo <= position <= window_hi
            full = len(legal) == len(spec["candidates"])
            if in_window and full:
                best_pos, best_legal = position, legal
                break
            key = (int(in_window), int(full), len(legal))
            if key > best_key:
                best_key, best_pos, best_legal = key, position, legal
        if best_pos is None:
            empty.append(spec)
        else:
            spec["level"] = best_pos
            spec["candidates"] = best_legal
            free.remove(best_pos)
    for spec in utility:
        if free:
            spec["level"] = free.pop(0)
        else:
            empty.append(spec)

    # dedupe (kit L1 pair and the L0 reward stay put; unplaced slots are the
    # caller's to drop)
    taken: set[int] = set()
    placed = [s for s in specs if s.get("level") is not None]
    for spec in sorted(placed, key=lambda s: s["level"]):
        if spec["level"] <= 1:
            continue
        level = spec["level"]
        while level in taken:
            level += 1
        spec["level"] = min(level, 75)
        while spec["level"] in taken:  # clamped collision walks back down
            spec["level"] -= 1
        taken.add(spec["level"])
    return empty


def format_skeleton(skeleton: dict[str, Any]) -> str:
    """The skeleton as the prompt block the model fills in."""
    lines = [
        "SLOT SKELETON — the learnset's structure is FIXED. Produce EXACTLY one "
        "row per slot below, at the stated level, choosing a move from that "
        "slot's allowed list. No other rows, no other levels. Every pick must "
        "be a DIFFERENT move — a repeated move is dropped and its slot fails; "
        "in particular each STATUS slot needs its own distinct status move. "
        "Sole exception: the L0 reward move may also appear once at a later "
        "level. A candidate marked * is ability fuel — an ability of this "
        "species boosts or demands it, so its real output beats its listed BP; "
        "prefer a *-marked candidate over a stronger unmarked one unless the "
        "reasoning states why not.",
    ]
    for slot in skeleton["slots"]:
        cands = slot["candidates"]
        marks = set(slot.get("fuel") or ())
        shown = ", ".join(
            f"{c}*" if c in marks else c for c in cands[:_MAX_PROMPT_CANDIDATES]
        )
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


def autofill(
    rows: list[dict[str, Any]], skeleton: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Deterministically finish a draft that almost fills the skeleton.

    The backstop behind the retry loop: when the model keeps misplacing a row
    or two (an attack in a status slot, a rung at the wrong level), the server
    can complete the draft itself — drop the off-slot row, seat each unfilled
    slot with its first unused candidate — instead of surfacing a salvage
    banner. Returns ``(rows, notes)``; the caller re-validates and only uses
    the result when it comes back clean.
    """
    slots_by_level: dict[int, list[dict[str, Any]]] = {}
    for slot in skeleton["slots"]:
        slots_by_level.setdefault(slot["level"], []).append(slot)

    kept: list[dict[str, Any]] = []
    notes: list[str] = []
    used_nonzero: set[str] = set()
    used_zero: set[str] = set()
    unfilled: list[dict[str, Any]] = []

    for level, slots in sorted(slots_by_level.items()):
        at_level = [r for r in rows if int(r.get("level", -1)) == level]
        for slot in sorted(slots, key=lambda s: len(s["candidates"])):
            allowed = {c.casefold() for c in slot["candidates"]}
            hit = next(
                (r for r in at_level if (r.get("move") or "").casefold() in allowed),
                None,
            )
            if hit is None:
                unfilled.append(slot)
                continue
            at_level.remove(hit)
            kept.append(hit)
            (used_zero if level == 0 else used_nonzero).add(hit["move"].casefold())
        for stray in at_level:
            notes.append(
                f"auto-repair: dropped {stray.get('move')} @L{level} — it fits "
                "no slot at that level"
            )
    # Rows at levels with no slot are dropped too (the validator rejects them).
    for row in rows:
        if int(row.get("level", -1)) not in slots_by_level:
            notes.append(
                f"auto-repair: dropped {row.get('move')} @L{row.get('level')} — "
                "no slot at that level"
            )

    for slot in unfilled:
        used = used_zero if slot["level"] == 0 else used_nonzero
        pick = next(
            (c for c in slot["candidates"] if c.casefold() not in used), None
        )
        if pick is None:
            continue  # nothing unused — re-validation will fail honestly
        used.add(pick.casefold())
        kept.append({
            "level": slot["level"],
            "move": pick,
            "reasoning": "auto-filled by the server — the draft left this "
                         f"slot ({slot['label']}) empty",
        })
        notes.append(f"auto-repair: filled {slot['label']} with {pick}")

    kept.sort(key=lambda r: (r["level"], r["move"]))
    return kept, notes


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
