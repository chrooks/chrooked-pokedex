"""Design pipeline: Propose (#103, M2) — anonymized line profile + pools → packet.

Ports the chat skill's blind-design prompt (`.claude/skills/blind-design/SKILL.md`
section 4) behind the LLM Port so any client can trigger it. The model sees the
line's anonymized lore ("Stage 1/2/3", "Variant A/B") and the merged move and
ability pools as `cached_context`; it never sees a species name, its typing,
stats, abilities, or learnset. The pre-draft then runs the ordinary
`suggest_learnset` in blind mode with the packet's own moves as anchors.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from . import dex as dexmod
from . import suggest as suggestmod
from .design_store import DesignError, DesignRecord
from .learnset_skeleton import is_battle_gimmick

PROPOSE_MAX_TOKENS = 6000
PROPOSE_WORKERS = 4
ANCHOR_MAX = 8
STAGE_LABELS = ("basic stage", "middle stage", "final stage")
VARIANT_LETTERS = "ABCDEFGH"

# The SKILL.md section-4 prompt, constraints verbatim; the bracketed optional
# sections are requested per call by `_user_prompt`.
BLIND_RUBRIC = (
    "You are doing a blind creature-design exercise for a Pokémon-style fan game. "
    "You have NO context beyond the profile and the two pools you are given. Do not "
    "try to identify which existing creature this profile might describe — design "
    "purely from the profile.\n\n"
    "Read fully: the profile, the abilities pool, the moves pool. [CUSTOM]-tagged "
    "entries are net-new bespoke content.\n\n"
    "For the FINAL STAGE, propose from the pools only — never invent a name, EXCEPT "
    "in the custom section when it is requested:\n"
    "A. ABILITIES — 5–8 candidates, one line of reasoning each tied to a specific "
    "profile fact. Mark primary / secondary / hidden. [CUSTOM] on equal footing. "
    "Give pros and cons for every candidate. Put the runners-up on the bench with "
    "the same reasoning, pros, and cons.\n"
    "B. MOVES — 25–35 level-up-worthy moves grouped by role: STAB-flavored attacks "
    "(pick the types YOU think fit and say why — report them as inferred_types), "
    "predation/flavor coverage, lean utility. Half-line reason each; name the "
    "proposed ability a move pays off in pays_off (empty when none). Never include "
    "Glaive Rush or Precipice Blades.\n"
    "C. ONE NEW CUSTOM (only when the user asks for it) — exactly one brand-new move "
    "OR ability that best completes the kit: which kind and why, a working name plus "
    "five alternative names, terse pool-style description, exact mechanic, the "
    "profile facts it is built from, the closest pool entry and why it is not a "
    "duplicate.\n"
    "D. STATS (only when a BST band is given) — a six-stat spread in that band, one "
    "line per stat.\n"
    "Plus one short paragraph (axis) naming the one or two profile facts you treated "
    "as the design axis.\n\n"
    "Return exactly one packet per VARIANT, designed for that variant's final stage "
    "from all of its stages. Stages are NOT variants: a profile with Stage 1-3 and "
    "no variants is ONE packet. A profile with Variant A and B is two packets, in order."
)


# --------------------------------------------------------------------------- #
# Profile
# --------------------------------------------------------------------------- #

def _line_names(records: list[DesignRecord], snapshot: dict[str, Any]) -> list[str]:
    species = snapshot["species"]
    ids = [cid for r in records for cid in [*r.line, *r.forms]]
    return [species[cid]["name"] for cid in ids if cid in species]


def _form_word(cid: str, entry: dict[str, Any], snapshot: dict[str, Any], lore_provider: Any) -> str:
    """"Heat" for Rotom Heat when its lore fell back to the base, else "".

    Five Rotom forms share one base page, so their blocks came out identical and
    the model paired appliances to variants by canon order, not by record. The
    form word is the one fact that tells the variants apart.
    """
    lore = lore_provider.fetch(cid, entry["name"])
    base = snapshot["species"].get(lore.base_species) if lore.found else None
    if not base or lore.base_species == cid:
        return ""
    base_name = base["name"]
    name = entry["name"]
    return name[len(base_name):].strip() if name.startswith(base_name + " ") else ""


def _stage_blocks(
    record: DesignRecord,
    snapshot: dict[str, Any],
    ruleset: Any,
    lore_provider: Any,
    provider: Any,
    other_names: list[str],
) -> str:
    blocks = []
    for index, cid in enumerate(record.line):
        entry = dexmod.build_dex_entry(snapshot, ruleset, cid)
        if entry is None:
            raise DesignError(404, f"No species {cid!r} in the snapshot.")
        injection = suggestmod.build_lore_injection(
            entry=entry, lore_mode="blind", lore_provider=lore_provider,
            provider=provider, other_species_names=other_names,
        )
        label = STAGE_LABELS[min(index, len(STAGE_LABELS) - 1)]
        if len(record.line) == 1:
            label = "single stage"
        block = injection.block.strip()
        form = _form_word(cid, entry, snapshot, lore_provider)
        if form:
            block += f"\nForm: the {form} form of this creature (the lore above is the base form's)."
        blocks.append(f"Stage {index + 1} ({label}):\n{block}")
    return "\n\n".join(blocks)


def build_line_profile(
    records: list[DesignRecord] | DesignRecord,
    snapshot: dict[str, Any],
    ruleset: Any,
    lore_provider: Any,
    provider: Any,
) -> str:
    """Anonymized 'Stage N' blocks per line; a group renders 'Variant A/B' each.

    Carries no species name, typing, stats, or abilities: the whole point of
    the blind pass is that the model argues from what the creature IS.
    """
    group = [records] if isinstance(records, DesignRecord) else list(records)
    other = _line_names(group, snapshot)
    if len(group) == 1:
        return _stage_blocks(group[0], snapshot, ruleset, lore_provider, provider, other)
    parts = []
    for letter, record in zip(VARIANT_LETTERS, group):
        stages = _stage_blocks(record, snapshot, ruleset, lore_provider, provider, other)
        parts.append(f"Variant {letter}:\n{stages}")
    return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# Pools — the exact lines pool_dump.py wrote for the chat agent
# --------------------------------------------------------------------------- #

def build_pools(snapshot: dict[str, Any], ruleset: Any) -> tuple[str, str]:
    pool = [r for r in dexmod.build_move_pool(snapshot, ruleset) if not is_battle_gimmick(r)]
    lines = []
    for r in sorted(pool, key=lambda r: r["move"]):
        eff = (r.get("effect") or "").replace("\n", " ")
        desc = (r.get("description") or "").replace("\n", " ")[:90]
        tag = " [CUSTOM]" if r.get("custom") else ""
        lines.append(
            f"{r['move']} | {r.get('type')} | {r.get('category')} | BP {r.get('power')}"
            f" | acc {r.get('accuracy')} | {eff} | {desc}{tag}"
        )
    alines = []
    for a in sorted(dexmod.build_abilities(snapshot, ruleset), key=lambda a: a["name"]):
        tag = " [CUSTOM]" if a.get("custom") else ""
        alines.append(f"{a['name']} | {(a.get('description') or '').strip()}{tag}")
    return "\n".join(lines) + "\n", "\n".join(alines) + "\n"


def format_pools(pools: tuple[str, str]) -> str:
    moves, abilities = pools
    return f"ABILITIES POOL:\n{abilities}\nMOVES POOL:\n{moves}"


# --------------------------------------------------------------------------- #
# Schema + Port call
# --------------------------------------------------------------------------- #

def _obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": required if required is not None else list(props),
        "additionalProperties": False,
    }


def _str() -> dict[str, str]:
    return {"type": "string"}


def packet_schema(want_custom: bool, want_stats: bool) -> dict[str, Any]:
    """The JSON schema of one packet (Data & API Changes → packet schema)."""
    candidate = {"name": _str(), "reason": _str(), "pros": _str(), "cons": _str()}
    props: dict[str, Any] = {
        "profile": {"type": "array", "items": _obj(
            {"stage": _str(), "ecological_role": _str(), "fantastical": _str()}
        )},
        "axis": _str(),
        "inferred_types": {"type": "array", "items": _str(), "minItems": 1, "maxItems": 2},
        "abilities": {"type": "array", "items": _obj({
            **candidate, "slot": {"type": "string", "enum": ["primary", "secondary", "hidden"]},
        })},
        "bench": {"type": "array", "items": _obj(candidate)},
        "moves": {"type": "array", "items": _obj(
            {"move": _str(), "role": _str(), "reason": _str(), "pays_off": _str()}
        )},
    }
    if want_custom:
        props["custom"] = _obj({
            "kind": {"type": "string", "enum": ["ability", "move"]},
            "working_name": _str(),
            "names": {"type": "array", "items": _str(), "minItems": 5, "maxItems": 5},
            "description": _str(),
            "mechanic": _str(),
            "closest_pool_entry": _str(),
            "why_not_duplicate": _str(),
        })
    if want_stats:
        props["stats"] = _obj({k: {"type": "integer"} for k in ("hp", "atk", "def", "spa", "spd", "spe")})
    return _obj(props)


def batch_schema(count: int, want_custom: bool, want_stats: bool) -> dict[str, Any]:
    """One packet per variant, in profile order."""
    return _obj({"packets": {
        "type": "array", "items": packet_schema(want_custom, want_stats),
        "minItems": count, "maxItems": count,
    }})


def wants_custom(steer: str) -> bool:
    return "custom" in (steer or "").lower()


def _user_prompt(profile: str, steer: str, want_custom: bool, bst_band: str | None, count: int) -> str:
    lines = [profile, ""]
    lines.append(
        f"Return exactly {count} packet(s) in `packets`: one for the FINAL STAGE of each "
        "variant, never one per stage."
    )
    if steer:
        lines.append(f"Steer from the user: {steer}")
    if want_custom:
        lines.append("Include section C: exactly one new custom move or ability.")
    if bst_band:
        lines.append(f"Include section D: a six-stat spread in the BST band {bst_band}.")
    return "\n".join(lines).rstrip() + "\n"


def propose_packet(
    provider: Any,
    profile: str,
    pools: tuple[str, str],
    steer: str,
    want_custom: bool,
    bst_band: str | None,
    count: int = 1,
) -> list[dict[str, Any]]:
    """One Port call → `count` raw packets (unvalidated)."""
    result = provider.propose(
        system=BLIND_RUBRIC,
        cached_context=format_pools(pools),
        user=_user_prompt(profile, steer, want_custom, bst_band, count),
        schema=batch_schema(count, want_custom, bst_band is not None),
        # A group answers with one packet per member in the same call; the cap
        # scales with it or a pair truncates (seen on the first real batch).
        max_tokens=PROPOSE_MAX_TOKENS * count,
    )
    packets = result.get("packets") if isinstance(result, dict) else None
    if not isinstance(packets, list) or len(packets) != count:
        raise DesignError(502, f"Provider returned {0 if not packets else len(packets)} packets, expected {count}.")
    return packets


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

def _canon(names: list[str]) -> dict[str, str]:
    return {n.casefold(): n for n in names}


def _current(entry: dict[str, Any]) -> dict[str, Any]:
    stats = dict(entry.get("stats") or {})
    return {
        "types": list(entry.get("types") or []),
        "abilities": dict(entry.get("abilities") or {}),
        "stats": stats,
        "bst": sum(v for v in stats.values() if isinstance(v, int)),
        "learnset_rows": len(entry.get("learnset") or []),
    }


def reference_stats(
    record: DesignRecord, snapshot: dict[str, Any], ruleset: Any
) -> list[dict[str, Any]]:
    out = []
    for cid in record.references:
        entry = dexmod.build_dex_entry(snapshot, ruleset, cid)
        if entry is not None:
            cur = _current(entry)
            out.append({"id": cid, "bst": cur["bst"], "stats": cur["stats"]})
    return out


def bst_band(refs: list[dict[str, Any]]) -> str | None:
    """A BST target from the steer's references, or None when there are none."""
    if not refs:
        return None
    values = sorted(r["bst"] for r in refs)
    return str(values[0]) if values[0] == values[-1] else f"{values[0]}–{values[-1]}"


def validate_packet(
    draft: dict[str, Any],
    move_pool: list[dict[str, Any]],
    abilities: list[dict[str, Any]],
    *,
    entry: dict[str, Any] | None = None,
    refs: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Drop pool-foreign names into warnings; attach `current` and `reference_stats`."""
    known_moves = _canon([r["move"] for r in move_pool if not is_battle_gimmick(r)])
    known_abilities = _canon([a["name"] for a in abilities])
    warnings: list[str] = []

    def keep(rows: Any, key: str, known: dict[str, str], kind: str) -> list[dict[str, Any]]:
        kept = []
        for row in rows or []:
            name = str(row.get(key) or "").strip()
            canon = known.get(name.casefold())
            if canon is None:
                warnings.append(f"{kind} {name!r} is not in the pool — dropped")
                continue
            kept.append({**row, key: canon})
        return kept

    packet = {
        "profile": list(draft.get("profile") or []),
        "axis": str(draft.get("axis") or ""),
        "inferred_types": list(draft.get("inferred_types") or []),
        "abilities": keep(draft.get("abilities"), "name", known_abilities, "ability"),
        "bench": keep(draft.get("bench"), "name", known_abilities, "ability"),
        "moves": keep(draft.get("moves"), "move", known_moves, "move"),
        "custom": draft.get("custom"),
        "stats": draft.get("stats"),
        "current": _current(entry) if entry else None,
        "reference_stats": list(refs or []),
        "draft_learnset": None,
        "warnings": warnings,
    }
    return packet, warnings


# --------------------------------------------------------------------------- #
# Pre-draft learnset
# --------------------------------------------------------------------------- #

def packet_anchors(packet: dict[str, Any]) -> list[str]:
    """The first eight STAB/role moves of the packet, in the model's order."""
    ranked = sorted(
        packet["moves"],
        key=lambda m: 0 if "stab" in (m.get("role") or "").lower() else 1,
    )
    anchors: list[str] = []
    for m in ranked:
        if m["move"] not in anchors:
            anchors.append(m["move"])
    return anchors[:ANCHOR_MAX]


def packet_direction(packet: dict[str, Any]) -> str:
    primary = next(
        (a["name"] for a in packet["abilities"] if a.get("slot") == "primary"),
        packet["abilities"][0]["name"] if packet["abilities"] else "",
    )
    axis = packet.get("axis") or ""
    return f"{axis} Primary ability: {primary}.".strip() if primary else axis


def predraft_learnset(
    provider: Any,
    entry: dict[str, Any],
    packet: dict[str, Any],
    move_pool: list[dict[str, Any]],
    abilities: list[dict[str, Any]],
    lore_provider: Any,
) -> dict[str, Any]:
    """Run `suggest_learnset` in blind mode from the packet; returns the packet with `draft_learnset`."""
    result = suggestmod.suggest_learnset(
        provider=provider, entry=entry, move_pool=move_pool, abilities=abilities,
        direction=packet_direction(packet), anchors=packet_anchors(packet),
        lore_mode="blind", lore_provider=lore_provider,
    )
    rows = [
        {"level": r["level"], "move": r["move"]} for r in result["draft"]["learnset"]
    ]
    warnings = list(result.get("warnings") or [])
    return {**packet, "draft_learnset": {
        "rows": rows,
        "warnings": [w for w in warnings if not w.startswith("lint: ")],
        "lint": [w[len("lint: "):] for w in warnings if w.startswith("lint: ")],
    }}


# --------------------------------------------------------------------------- #
# The job
# --------------------------------------------------------------------------- #

def _propose_group(ctx: Any, records: list[DesignRecord], snapshot: dict[str, Any], ruleset: Any, pools: tuple[str, str]) -> None:
    provider = ctx.llm_provider()
    lore_provider = ctx.lore_provider(snapshot, "blind")
    move_pool = dexmod.build_move_pool(snapshot, ruleset)
    abilities = dexmod.build_abilities(snapshot, ruleset)
    try:
        profile = build_line_profile(records, snapshot, ruleset, lore_provider, provider)
        steer = " / ".join(r.steer for r in records if r.steer)
        refs = {r.id: reference_stats(r, snapshot, ruleset) for r in records}
        band = bst_band([ref for rs in refs.values() for ref in rs])
        drafts = propose_packet(
            provider, profile, pools, steer, wants_custom(steer), band, count=len(records)
        )
    except Exception as error:  # noqa: BLE001 — every failure lands on the record
        for r in records:
            ctx.store.transition(r.id, "error", activity="error", error=str(error))
        return
    for record, draft in zip(records, drafts):
        try:
            entry = dexmod.build_dex_entry(snapshot, ruleset, record.id)
            packet, _ = validate_packet(
                draft, move_pool, abilities, entry=entry, refs=refs[record.id]
            )
            try:
                packet = predraft_learnset(
                    provider, entry, packet, move_pool, abilities, lore_provider
                )
            except Exception as error:  # noqa: BLE001
                # The pre-draft is a convenience over the packet, not the packet:
                # a skeleton the model cannot fill (three retries) must not cost
                # Chris the abilities and moves. Realize builds the real draft
                # from his anchors anyway.
                packet = {**packet, "draft_learnset": None,
                          "warnings": [*packet.get("warnings", []), f"pre-draft skipped: {error}"]}
            ctx.store.transition(record.id, "proposed", activity="ready", packet=packet)
        except Exception as error:  # noqa: BLE001
            ctx.store.transition(record.id, "error", activity="error", error=str(error))


def run_propose(ctx: Any, ids: list[str]) -> None:
    """Propose every id; records sharing a group go in one Port call."""
    snapshot = ctx.load_snapshot()
    ruleset = ctx.load_ruleset()
    pools = build_pools(snapshot, ruleset)
    records = [ctx.store.get(i) for i in ids]
    groups: dict[str, list[DesignRecord]] = {}
    for r in records:
        groups.setdefault(r.group or r.id, []).append(r)
    with ThreadPoolExecutor(max_workers=PROPOSE_WORKERS) as pool:
        list(pool.map(
            lambda g: _propose_group(ctx, g, snapshot, ruleset, pools), groups.values()
        ))


def _start(ctx: Any, ids: list[str], background: BackgroundTasks) -> dict[str, Any]:
    started = []
    for record_id in ids:
        try:
            ctx.store.transition(record_id, "proposing", activity="proposing")
        except DesignError as error:
            raise HTTPException(status_code=error.status, detail=error.message) from error
        started.append(record_id)
    if started:
        background.add_task(run_propose, ctx, started)
    return {"started": started}


def register(router: APIRouter, ctx: Any) -> None:
    @router.post("/propose")
    def propose_all(background: BackgroundTasks, body: dict[str, Any] | None = None) -> dict[str, Any]:
        ids = [r.id for r in ctx.store.list() if r.state == "queued"]
        for extra in (body or {}).get("ids") or []:
            if extra not in ids:
                ids.append(extra)
        return _start(ctx, ids, background)

    @router.post("/{record_id}/propose")
    def propose_one(record_id: str, background: BackgroundTasks) -> dict[str, Any]:
        return _start(ctx, [record_id], background)
