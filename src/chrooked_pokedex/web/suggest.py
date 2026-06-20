"""The ability-, typing-, and stats-suggest capabilities over the reusable propose
Seam (M2).

Each capability assembles species context server-side from the snapshot ⊕ Ruleset
(the merged dex entry + the relevant pool), builds its own scoring rubric, calls the
Port for ONE structured draft, validates the draft against the real data, and returns
the reusable contract::

    {draft: {...field set...},
     rationale: {<key>: str},
     alternatives: [{value, rationale}]}

None of these functions ever writes a file — drafts flow back to the caller (the chat
skill or, later, the UI), and the accept path is the existing CRUD/loader Boundary.

Reuse note (ac6): the Seam is fixed (assemble → call → validate → return; never
write); a new capability adds its own ``_build_*_rubric`` (the scoring criteria),
its own context assembly (what field set it proposes), and its own draft schema.
The three shared pieces — the :class:`~chrooked_pokedex.web.llm.LlmProvider` Port,
this ``{draft, rationale, alternatives}`` contract, and the accept-through-CRUD path
— are reused unchanged across every sibling (#7 learnset, #8 new-ability, #9 move,
#10 stats, #32).
"""

from __future__ import annotations

import re
from typing import Any

from .llm import DEFAULT_MAX_TOKENS, LlmProvider

# Learnset responses return a whole list with per-move reasoning (~15–25 rows,
# 2–3k tokens in full mode). The shared DEFAULT_MAX_TOKENS (1024) is sized for
# the tiny ability/typing/stats outputs and truncates a learnset response.
# Only this capability uses the larger budget; the other three stay on 1024.
LEARNSET_MAX_TOKENS = 4096

# The ability slots an Override may set, in display order. The draft is a partial
# Override: only the slots the model proposes appear.
_ABILITY_SLOTS = ("primary", "secondary", "hidden")


class SuggestError(Exception):
    """A suggest request could not be served as asked (→ a clean 4xx detail).

    Distinct from an LLM transport failure (`LlmError`): this is a server-side
    validation problem — an unknown species, or a draft naming an ability that
    isn't in the real pool — that the endpoint surfaces as an honest message.
    """


# --------------------------------------------------------------------------- #
# Context assembly — server-side, from the merged dex entry + the ability pool
# --------------------------------------------------------------------------- #


def build_ability_pool(abilities: list[dict[str, Any]]) -> list[dict[str, str]]:
    """The compact ability pool the model picks from: name + description only.

    Built from the merged abilities collection (``build_abilities``) so it is the
    real, current set (base ⊕ Ruleset). Trimmed to the two fields the rubric
    needs — sending the full objects would bloat the cached prefix for no gain.
    Sorted by name for a deterministic, cache-stable prefix.
    """
    pool = [
        {"name": entry["name"], "description": entry.get("description", "")}
        for entry in abilities
        if entry.get("name")
    ]
    return sorted(pool, key=lambda entry: entry["name"])


def _pool_names(pool: list[dict[str, str]]) -> set[str]:
    """The case-folded set of real ability names, for validating a draft."""
    return {entry["name"].strip().casefold() for entry in pool}


def _format_pool(pool: list[dict[str, str]]) -> str:
    """Render the ability pool as a compact, cache-stable text block."""
    return "\n".join(f"- {entry['name']}: {entry['description']}" for entry in pool)


def _format_learnset(learnset: list[dict[str, Any]]) -> str:
    """Render the learnset as ``L<level> <Move>`` lines, or a placeholder."""
    if not learnset:
        return "(no level-up learnset)"
    return ", ".join(
        f"L{entry.get('level', '?')} {entry.get('move', '?')}" for entry in learnset
    )


def _format_current_abilities(abilities: dict[str, Any]) -> str:
    """Render the species' current ability slots, naming empty ones explicitly."""
    parts = []
    for slot in _ABILITY_SLOTS:
        value = abilities.get(slot)
        parts.append(f"{slot}: {value if value else '(none)'}")
    return " / ".join(parts)


# --------------------------------------------------------------------------- #
# The rubric — ported from the dreamstone ability-suggest skill (existing mode)
# --------------------------------------------------------------------------- #


def _build_rubric() -> str:
    """The ability-suggest system rubric (the capability prompt).

    Ported from dreamstone's ``ability-suggest`` skill, existing mode: score
    candidates on type synergy, stat alignment, learnset synergy, move-flag
    synergy, thematic fit, competitive balance, and avoid-redundancy — and pick
    only from the real ability pool. This is the *policy* hole in the Template
    Method; a sibling capability swaps it for its own rubric.
    """
    return (
        "You are a Pokémon game-design assistant. Given one species and the full "
        "pool of existing abilities, recommend the best-fit EXISTING ability for a "
        "slot. You MUST pick only from the provided ability pool — never invent a "
        "new ability. Score candidates on:\n"
        "- Type synergy: the ability boosts or interacts with the species' types.\n"
        "- Stat alignment: physical abilities for physical attackers, special for "
        "special, defensive for tanks (judge by the base stats).\n"
        "- Learnset synergy: e.g. Iron Fist fits a punching-heavy learnset; Sheer "
        "Force fits moves with secondary effects.\n"
        "- Move-flag synergy: punching / slicing / sound / biting / wind moves in "
        "the learnset matching category-boosting abilities.\n"
        "- Thematic fit: the species' concept matches the ability's name/mechanic.\n"
        "- Competitive balance: don't make an already-strong species broken; do "
        "help an underserved one.\n"
        "- Avoid redundancy: don't suggest an ability the species already has.\n"
        "Propose the single best ability for the target slot in `draft`, a "
        "per-slot reason in `rationale`, and up to three runner-up abilities (each "
        "with a one-line reason) in `alternatives`. Every ability name you emit "
        "must appear verbatim in the ability pool."
    )


def _build_user_context(entry: dict[str, Any], direction: str | None) -> str:
    """The fresh per-species delta: stats/types/abilities/learnset + direction."""
    stats = entry.get("stats", {})
    stat_line = " ".join(
        f"{key.upper()} {stats[key]}" for key in stats
    ) or "(unknown)"
    lines = [
        f"Species: {entry.get('name', entry['chrooked_id'])}",
        f"Types: {', '.join(entry.get('types', [])) or '(unknown)'}",
        f"Base stats: {stat_line}",
        f"Current abilities: {_format_current_abilities(entry.get('abilities', {}))}",
        f"Learnset: {_format_learnset(entry.get('learnset', []))}",
    ]
    if direction and direction.strip():
        lines.append(f"Direction from the user: {direction.strip()}")
    return "\n".join(lines)


def _draft_schema() -> dict[str, Any]:
    """The JSON schema the draft is forced to match (the field set).

    A partial abilities Override (each slot optional) + per-slot rationale +
    alternatives. Forcing this shape means the returned draft is structurally
    valid before the pool check; the loader is still the gate on accept.
    """
    slot_schema = {"type": "string"}
    return {
        "type": "object",
        "properties": {
            "draft": {
                "type": "object",
                "properties": {
                    "abilities": {
                        "type": "object",
                        "properties": {slot: slot_schema for slot in _ABILITY_SLOTS},
                        "additionalProperties": False,
                    }
                },
                "required": ["abilities"],
                "additionalProperties": False,
            },
            "rationale": {
                "type": "object",
                "properties": {slot: {"type": "string"} for slot in _ABILITY_SLOTS},
                "additionalProperties": False,
            },
            "alternatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["value", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["draft", "rationale", "alternatives"],
        "additionalProperties": False,
    }


# --------------------------------------------------------------------------- #
# The capability: assemble → call the Port → validate → return (never write)
# --------------------------------------------------------------------------- #


def suggest_ability(
    *,
    provider: LlmProvider,
    entry: dict[str, Any],
    abilities: list[dict[str, Any]],
    direction: str | None = None,
) -> dict[str, Any]:
    """Propose a best-fit existing ability for a species; never writes a file.

    Assembles the rubric + context, runs ONE bounded Port call, then validates
    that every ability the model named (in the draft slots and in the
    alternatives) exists in the real pool — a hallucinated name is a clean
    :class:`SuggestError`, not a silently-bad draft. Returns the reusable
    ``{draft, rationale, alternatives}`` contract.
    """
    pool = build_ability_pool(abilities)
    if not pool:
        raise SuggestError("No abilities are available to suggest from.")

    cached_context = "Ability pool (pick only from these):\n" + _format_pool(pool)
    result = provider.propose(
        system=_build_rubric(),
        cached_context=cached_context,
        user=_build_user_context(entry, direction),
        schema=_draft_schema(),
        max_tokens=DEFAULT_MAX_TOKENS,
    )

    return _validate_result(result, pool)


def _validate_result(
    result: dict[str, Any], pool: list[dict[str, str]]
) -> dict[str, Any]:
    """Shape-and-pool check on the model's draft (the draft is never trusted).

    The Port forces the JSON shape, but the *values* are model output: confirm
    `result` carries the contract keys and that every proposed/alternative
    ability name is a real pool member. Any miss is a `SuggestError` — nothing
    is written and the endpoint surfaces an honest message.
    """
    if not isinstance(result, dict):
        raise SuggestError("The suggestion came back in an unexpected shape.")

    draft = result.get("draft")
    if not isinstance(draft, dict) or not isinstance(draft.get("abilities"), dict):
        raise SuggestError("The suggestion was missing a draft abilities object.")

    known = _pool_names(pool)
    proposed_slots = {
        slot: value
        for slot, value in draft["abilities"].items()
        if slot in _ABILITY_SLOTS and value
    }
    if not proposed_slots:
        raise SuggestError("The suggestion did not propose any ability.")

    for slot, value in proposed_slots.items():
        if value.strip().casefold() not in known:
            raise SuggestError(
                f"The suggested ability {value!r} for the {slot} slot is not an "
                "existing ability; only existing abilities can be suggested."
            )

    alternatives = []
    for alt in result.get("alternatives") or []:
        if not isinstance(alt, dict):
            continue
        value = alt.get("value")
        if not value or value.strip().casefold() not in known:
            # Drop a hallucinated alternative rather than failing the whole
            # request — the primary draft is the load-bearing part.
            continue
        alternatives.append({"value": value, "rationale": alt.get("rationale", "")})

    rationale = {
        slot: text
        for slot, text in (result.get("rationale") or {}).items()
        if slot in proposed_slots and isinstance(text, str)
    }

    return {
        "draft": {"abilities": proposed_slots},
        "rationale": rationale,
        "alternatives": alternatives,
    }


# =========================================================================== #
# Typing suggest — propose 1-2 types for a species
# =========================================================================== #

# The six stat keys in the same order the Essentials applier uses them.
# Used here to format the stat line and by stats-suggest to validate keys.
_STAT_KEYS = ("hp", "atk", "def", "spa", "spd", "spe")


def _build_typing_rubric() -> str:
    """The typing-suggest system rubric (the capability prompt).

    Ported from the typing half of dreamstone's ``species-edit`` skill, extended
    with the type-fit judgment from the existing ability rubric. Score candidates
    on STAB synergy with the offensive movepool, defensive profile against common
    threats, thematic identity, and competitive balance. Propose exactly 1-2 types;
    pick ONLY from the provided type pool. This is the *policy* hole in the
    Template Method; the typing sibling swaps in its own rubric.
    """
    return (
        "You are a Pokémon game-design assistant. Given one species and the full "
        "type pool, recommend the best-fit typing (1 or 2 types). You MUST pick "
        "only from the provided type pool — never invent a new type. Score "
        "candidates on:\n"
        "- STAB synergy: does the typing provide STAB on the species' key "
        "offensive moves (judge from the learnset)?\n"
        "- Defensive profile: how does the typing fare against common threats? "
        "Avoid stacking weaknesses without compensating resistances.\n"
        "- Thematic identity: the species' concept, design, or lore supports "
        "the chosen type(s).\n"
        "- Competitive balance: don't make an already-strong species broken; do "
        "help an underserved one reach a viable niche.\n"
        "Propose the typing in `draft.types` (a list of 1 or 2 type strings), a "
        "single rationale string in `rationale.types` explaining the choice, and "
        "up to three runner-up typings (each a short type string like 'Fire' or "
        "'Fire/Flying' with a one-line reason) in `alternatives`. Every type "
        "string you emit must appear verbatim in the type pool."
    )


def _format_type_pool(type_pool: list[str]) -> str:
    """Render the type pool as a compact, cache-stable bullet list."""
    return "\n".join(f"- {t}" for t in type_pool)


def _build_typing_user_context(entry: dict[str, Any], direction: str | None) -> str:
    """The fresh per-species delta for typing suggest: stats/current types/learnset."""
    stats = entry.get("stats", {})
    stat_line = " ".join(
        f"{key.upper()} {stats[key]}" for key in _STAT_KEYS if key in stats
    ) or "(unknown)"
    lines = [
        f"Species: {entry.get('name', entry['chrooked_id'])}",
        f"Current types: {', '.join(entry.get('types', [])) or '(unknown)'}",
        f"Base stats: {stat_line}",
        f"Learnset: {_format_learnset(entry.get('learnset', []))}",
    ]
    if direction and direction.strip():
        lines.append(f"Direction from the user: {direction.strip()}")
    return "\n".join(lines)


def _typing_draft_schema() -> dict[str, Any]:
    """The JSON schema the typing draft is forced to match.

    Proposed types as a list, a single rationale string, and alternatives.
    The Port forces this shape so the draft is structurally valid before the
    pool check; the loader is still the gate on accept.
    """
    return {
        "type": "object",
        "properties": {
            "draft": {
                "type": "object",
                "properties": {
                    "types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 2,
                    }
                },
                "required": ["types"],
                "additionalProperties": False,
            },
            "rationale": {
                "type": "object",
                "properties": {"types": {"type": "string"}},
                "required": ["types"],
                "additionalProperties": False,
            },
            "alternatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["value", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["draft", "rationale", "alternatives"],
        "additionalProperties": False,
    }


def suggest_typing(
    *,
    provider: LlmProvider,
    entry: dict[str, Any],
    type_pool: list[str],
    direction: str | None = None,
) -> dict[str, Any]:
    """Propose a best-fit typing (1-2 types) for a species; never writes a file.

    Assembles the rubric + context, runs ONE bounded Port call, then validates
    that every type the model named (in the draft and in the alternatives) exists
    in the real type pool — a hallucinated type is a clean :class:`SuggestError`,
    not a silently-bad draft. Returns the reusable ``{draft, rationale,
    alternatives}`` contract.
    """
    if not type_pool:
        raise SuggestError("No types are available to suggest from.")

    cached_context = "Type pool (pick only from these):\n" + _format_type_pool(type_pool)
    result = provider.propose(
        system=_build_typing_rubric(),
        cached_context=cached_context,
        user=_build_typing_user_context(entry, direction),
        schema=_typing_draft_schema(),
        max_tokens=DEFAULT_MAX_TOKENS,
    )

    return _validate_typing_result(result, type_pool)


def _validate_typing_result(
    result: dict[str, Any], type_pool: list[str]
) -> dict[str, Any]:
    """Shape-and-pool check on the typing draft (the draft is never trusted).

    Confirms the contract keys, that 1-2 types were proposed, and that every
    proposed/alternative type name is a real pool member. Any miss on the
    proposed types is a `SuggestError`. Hallucinated alternatives are dropped
    (mirroring `_validate_result` for abilities), never a request failure.
    """
    if not isinstance(result, dict):
        raise SuggestError("The suggestion came back in an unexpected shape.")

    draft = result.get("draft")
    if not isinstance(draft, dict) or not isinstance(draft.get("types"), list):
        raise SuggestError("The suggestion was missing a draft types list.")

    proposed = [t for t in draft["types"] if isinstance(t, str) and t.strip()]
    if not proposed:
        raise SuggestError("The suggestion did not propose any type.")
    if len(proposed) > 2:
        raise SuggestError(
            f"The suggestion proposed {len(proposed)} types; at most 2 are allowed."
        )

    known = {t.strip().casefold() for t in type_pool}
    for proposed_type in proposed:
        if proposed_type.strip().casefold() not in known:
            raise SuggestError(
                f"The suggested type {proposed_type!r} is not in the type pool; "
                "only existing types can be suggested."
            )

    alternatives = []
    for alt in result.get("alternatives") or []:
        if not isinstance(alt, dict):
            continue
        value = alt.get("value")
        if not value or not isinstance(value, str):
            continue
        # Alternatives may be "Fire/Flying" compound strings or single types.
        # Drop any alternative whose constituent types are not all in the pool.
        parts = [p.strip() for p in value.split("/")]
        if any(p.casefold() not in known for p in parts):
            # Drop a hallucinated alternative rather than failing the whole request.
            continue
        alternatives.append({"value": value, "rationale": alt.get("rationale", "")})

    rationale_text = (result.get("rationale") or {}).get("types")
    rationale = {"types": rationale_text} if isinstance(rationale_text, str) else {}

    return {
        "draft": {"types": proposed},
        "rationale": rationale,
        "alternatives": alternatives,
    }


# =========================================================================== #
# Stats suggest — propose a six-stat spread for a species
# =========================================================================== #


def _build_stats_rubric() -> str:
    """The stats-suggest system rubric (the capability prompt).

    Ported from the stats half of dreamstone's ``species-edit`` skill. Score
    candidates on direction compliance (honor a freeform direction or audit the
    current spread when none is given), BST proximity (keep the total near the
    current BST unless a tier change is implied), and role coherence (the spread
    must match the species' offense/defense identity). This is the *policy* hole in
    the Template Method; the stats sibling swaps in its own rubric.
    """
    return (
        "You are a Pokémon game-design assistant. Given one species, propose a "
        "six-stat base-stat spread (HP, ATK, DEF, SPA, SPD, SPE). Use the exact "
        "keys: hp, atk, def, spa, spd, spe. Score candidates on:\n"
        "- Direction compliance: if a direction is given ('faster special attacker', "
        "'bulkier wall', etc.), honor it — shift the relevant stats, let others "
        "stay close to the current values.\n"
        "- BST proximity: when no direction implies a tier change, keep the total "
        "BST within ~10 points of the current total. A direction like 'stronger "
        "overall' permits a larger shift.\n"
        "- Role coherence: the spread must match the species' offense/defense "
        "identity — a physical attacker should have high ATK, not SPA; a defensive "
        "wall should have high DEF/SPD and moderate HP.\n"
        "- Learnset synergy: if the learnset is mostly physical, a high ATK matters "
        "more than SPA, and vice versa.\n"
        "Propose the full six-stat spread in `draft.stats` (an object with exactly "
        "the six keys: hp, atk, def, spa, spd, spe — all integers in [1, 255]), "
        "a single rationale string in `rationale.stats` explaining the choices, "
        "and up to two alternative spreads (each a short description like "
        "'bulkier: hp+10 def+10 spe-10' with a one-line reason) in `alternatives`."
    )


def _build_stats_user_context(entry: dict[str, Any], direction: str | None) -> str:
    """The fresh per-species delta for stats suggest: types/current stats/learnset."""
    stats = entry.get("stats", {})
    stat_line = " ".join(
        f"{key.upper()} {stats[key]}" for key in _STAT_KEYS if key in stats
    ) or "(unknown)"
    bst = sum(int(stats.get(k, 0)) for k in _STAT_KEYS)
    lines = [
        f"Species: {entry.get('name', entry['chrooked_id'])}",
        f"Types: {', '.join(entry.get('types', [])) or '(unknown)'}",
        f"Current base stats: {stat_line}  (BST: {bst})",
        f"Learnset: {_format_learnset(entry.get('learnset', []))}",
    ]
    if direction and direction.strip():
        lines.append(f"Direction from the user: {direction.strip()}")
    else:
        lines.append(
            "Direction: AUDIT — no direction given. Evaluate the current spread "
            "for coherence and propose improvements that preserve the BST."
        )
    return "\n".join(lines)


def _stats_draft_schema() -> dict[str, Any]:
    """The JSON schema the stats draft is forced to match.

    All six stat keys as integers, a single rationale string, and alternatives.
    The Port forces this shape so the draft is structurally valid before the
    value check; the loader is still the gate on accept.
    """
    stat_properties = {key: {"type": "integer"} for key in _STAT_KEYS}
    return {
        "type": "object",
        "properties": {
            "draft": {
                "type": "object",
                "properties": {
                    "stats": {
                        "type": "object",
                        "properties": stat_properties,
                        "required": list(_STAT_KEYS),
                        "additionalProperties": False,
                    }
                },
                "required": ["stats"],
                "additionalProperties": False,
            },
            "rationale": {
                "type": "object",
                "properties": {"stats": {"type": "string"}},
                "required": ["stats"],
                "additionalProperties": False,
            },
            "alternatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["value", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["draft", "rationale", "alternatives"],
        "additionalProperties": False,
    }


def suggest_stats(
    *,
    provider: LlmProvider,
    entry: dict[str, Any],
    direction: str | None = None,
) -> dict[str, Any]:
    """Propose a six-stat spread for a species; never writes a file.

    Assembles the rubric + context (including the current BST), runs ONE bounded
    Port call, then validates that every stat key is one of the six canonical keys
    and each value is an integer in [1, 255]. An out-of-range or unknown key is a
    clean :class:`SuggestError`. Returns the reusable ``{draft, rationale,
    alternatives}`` contract.
    """
    result = provider.propose(
        system=_build_stats_rubric(),
        cached_context=(
            f"Valid stat keys: {', '.join(_STAT_KEYS)}. "
            "All values must be integers in the range [1, 255]."
        ),
        user=_build_stats_user_context(entry, direction),
        schema=_stats_draft_schema(),
        max_tokens=DEFAULT_MAX_TOKENS,
    )

    return _validate_stats_result(result)


def _validate_stats_result(result: dict[str, Any]) -> dict[str, Any]:
    """Shape-and-range check on the stats draft (the draft is never trusted).

    Confirms the contract keys, that exactly the six canonical stat keys are
    present, and that every value is an integer in [1, 255]. Any miss is a
    `SuggestError` — nothing is written and the endpoint surfaces an honest message.
    """
    if not isinstance(result, dict):
        raise SuggestError("The suggestion came back in an unexpected shape.")

    draft = result.get("draft")
    if not isinstance(draft, dict) or not isinstance(draft.get("stats"), dict):
        raise SuggestError("The suggestion was missing a draft stats object.")

    raw_stats = draft["stats"]
    unknown_keys = set(raw_stats) - set(_STAT_KEYS)
    if unknown_keys:
        raise SuggestError(
            f"The suggestion included unknown stat key(s): "
            f"{', '.join(sorted(unknown_keys))}. Valid keys: {', '.join(_STAT_KEYS)}."
        )

    validated_stats: dict[str, int] = {}
    for key in _STAT_KEYS:
        value = raw_stats.get(key)
        if value is None:
            raise SuggestError(
                f"The suggestion was missing stat key {key!r}."
            )
        if not isinstance(value, int) or isinstance(value, bool):
            raise SuggestError(
                f"The suggested value for {key!r} is not an integer: {value!r}."
            )
        if not (1 <= value <= 255):
            raise SuggestError(
                f"The suggested value for {key!r} ({value}) is out of range [1, 255]."
            )
        validated_stats[key] = value

    alternatives = []
    for alt in result.get("alternatives") or []:
        if not isinstance(alt, dict):
            continue
        value = alt.get("value")
        if not value or not isinstance(value, str):
            continue
        alternatives.append({"value": value, "rationale": alt.get("rationale", "")})

    rationale_text = (result.get("rationale") or {}).get("stats")
    rationale = {"stats": rationale_text} if isinstance(rationale_text, str) else {}

    return {
        "draft": {"stats": validated_stats},
        "rationale": rationale,
        "alternatives": alternatives,
    }


# =========================================================================== #
# Learnset suggest — propose a full level-up learnset (or surgical edit)
# =========================================================================== #


def _build_learnset_rubric() -> str:
    """The learnset-suggest system rubric (the capability prompt).

    Directs the model to design a level-up learnset that picks ONLY from the
    provided move pool, honors STAB with the species' types, aligns move
    categories (physical/special) with the base stats, accounts for ability
    synergy (e.g. Iron Fist favors punching moves, Sheer Force favors moves with
    secondary effects), maintains a sensible level progression, and places a
    signature evolution-reward move at L0 (on-evolution) for evolved forms or
    near the evo level for pre-evos. Every row must carry a one-line `reasoning`.
    In surgical mode the model changes ONLY what the instruction names and returns
    the whole learnset otherwise byte-identical to the current one.
    """
    return (
        "You are a Pokémon game-design assistant. Given one species and the full "
        "move pool, design a complete level-up learnset. Each row is "
        "{level, move, reasoning}. Level 0 means 'learned on evolution'. "
        "You MUST pick only moves from the provided move pool — never invent a "
        "move name. Design the learnset to:\n"
        "- Provide STAB on the species' types wherever possible.\n"
        "- Match move category (Physical/Special/Status) to the base stats: "
        "high ATK → Physical leaning; high SPA → Special leaning; balanced → mix.\n"
        "- Synergize with the species' abilities (e.g. Iron Fist ability → prefer "
        "punching-flag moves; Sheer Force → prefer moves with secondary effects; "
        "Pixilate/Refrigerate → Normal moves hit harder as that type).\n"
        "- Maintain a sensible level progression: weaker/basic moves early, "
        "stronger/signature moves late.\n"
        "- For evolved forms (when 'Evolved from' is shown): place an "
        "evolution-reward move at level 0 ('learned on evolution').\n"
        "- For pre-evolutionary forms (when 'Evolves into' at a specific level is "
        "shown): place a reward move near that evo level.\n"
        "- In SURGICAL mode: change ONLY what the instruction names. Return the "
        "FULL learnset with every other row byte-identical to the current learnset. "
        "Do not reorder, rename, or adjust any row not targeted by the instruction.\n"
        "Emit the full learnset in `draft.learnset`, a rationale string explaining "
        "the overall design in `rationale.learnset`, and up to three alternative "
        "move suggestions (each as a short 'Move @ Lvel — reason' string) in "
        "`alternatives`. Every move name you emit must appear in the move pool."
    )


def _format_move_pool(pool: list[dict[str, Any]]) -> str:
    """Render the move pool as a compact, cache-stable text block."""
    lines = []
    for row in pool:
        pwr = f" {row['power']}bp" if row.get("power") is not None else ""
        lines.append(
            f"- {row['move']} ({row['type']} {row['category']}{pwr}; {row['effect']})"
        )
    return "\n".join(lines)


def _format_abilities_with_effects(
    ability_slots: dict[str, Any], all_abilities: list[dict[str, Any]]
) -> str:
    """Format the species' ability slots with effect descriptions from the merged pool.

    Looks up each slot's ability name in the full merged abilities list (which
    carries `description`) so the learnset rubric can reason about ability synergy
    with the current, possibly edited effect text — not names-only.
    """
    ability_by_name: dict[str, str] = {
        entry["name"].strip().casefold(): entry.get("description", "")
        for entry in all_abilities
        if entry.get("name")
    }
    parts = []
    for slot in _ABILITY_SLOTS:
        name = ability_slots.get(slot)
        if not name:
            continue
        desc = ability_by_name.get(name.strip().casefold(), "")
        parts.append(f"{slot}: {name}" + (f" — {desc}" if desc else ""))
    return " / ".join(parts) if parts else "(none)"


def _format_evo_context(entry: dict[str, Any]) -> str:
    """Format the evolution context for the learnset rubric.

    - Is-evolved: backward `evolution.from` present → "Evolved from {species}".
    - Forward evo level: `evolves_into[].method_detail.param` when `kind == EVO_LEVEL`.
    """
    lines: list[str] = []

    evolution = entry.get("evolution")
    if evolution and evolution.get("from"):
        lines.append(f"Evolved from: {evolution['from']}")

    for edge in entry.get("evolves_into") or []:
        method_detail = edge.get("method_detail") or {}
        if method_detail.get("kind") == "EVO_LEVEL":
            to_name = edge.get("to_name") or edge.get("to", "")
            param = method_detail.get("param", "?")
            lines.append(f"Evolves into {to_name} at level {param}")

    return "\n".join(lines) if lines else "(no evolution data)"


def _build_learnset_user_context(
    entry: dict[str, Any],
    all_abilities: list[dict[str, Any]],
    mode: str,
    instruction: str | None,
    direction: str | None,
) -> str:
    """The fresh per-species delta for learnset suggest.

    Extends `_build_user_context` with ability-effect text + evo context (D3).
    The ability descriptions come from the merged abilities pool so a Ruleset
    retune of an ability shifts move picks (not names-only like the base context).
    """
    stats = entry.get("stats", {})
    stat_line = " ".join(
        f"{key.upper()} {stats[key]}" for key in _STAT_KEYS if key in stats
    ) or "(unknown)"
    lines = [
        f"Species: {entry.get('name', entry['chrooked_id'])}",
        f"Types: {', '.join(entry.get('types', [])) or '(unknown)'}",
        f"Base stats: {stat_line}",
        f"Current abilities (with effects): "
        f"{_format_abilities_with_effects(entry.get('abilities', {}), all_abilities)}",
        f"Current learnset: {_format_learnset(entry.get('learnset', []))}",
        f"Evolution: {_format_evo_context(entry)}",
        f"Mode: {mode.upper()}",
    ]
    if instruction and instruction.strip():
        lines.append(f"Surgical instruction: {instruction.strip()}")
    if direction and direction.strip():
        lines.append(f"Direction from the user: {direction.strip()}")
    return "\n".join(lines)


def _learnset_draft_schema() -> dict[str, Any]:
    """The JSON schema the learnset draft is forced to match.

    Whole learnset as [{level, move, reasoning}] rows, a single rationale string,
    and alternatives. The Port forces this shape so the draft is structurally
    valid before the pool + level checks; the loader is still the gate on accept
    (where `reasoning` is not stored — accept strips it before PUT).
    """
    return {
        "type": "object",
        "properties": {
            "draft": {
                "type": "object",
                "properties": {
                    "learnset": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "level": {"type": "integer"},
                                "move": {"type": "string"},
                                "reasoning": {"type": "string"},
                            },
                            "required": ["level", "move", "reasoning"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["learnset"],
                "additionalProperties": False,
            },
            "rationale": {
                "type": "object",
                "properties": {"learnset": {"type": "string"}},
                "required": ["learnset"],
                "additionalProperties": False,
            },
            "alternatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["value", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["draft", "rationale", "alternatives"],
        "additionalProperties": False,
    }


def _pool_move_names(pool: list[dict[str, Any]]) -> dict[str, str]:
    """Case-folded → canonical-name mapping for the move pool.

    Returns a dict keyed by the case-folded display name, valued by the pool's
    canonical display name. Enables case-insensitive validation + normalization.
    """
    return {row["move"].strip().casefold(): row["move"] for row in pool}


def _validate_learnset_result(
    result: dict[str, Any],
    move_pool: list[dict[str, Any]],
    *,
    mode: str,
    current_learnset: list[dict[str, Any]],
    instruction: str | None = None,
) -> dict[str, Any]:
    """Shape, pool, level, and repeat-move checks on the learnset draft.

    Steps (in order):
    1. Shape: result must carry the contract keys and a non-empty learnset list.
    2. Pool (AC3): every `move` in the draft must exist in the merged move pool
       (case-insensitive); a miss is a SuggestError. Normalize to canonical name.
    3. Level (AC5/D4): each level must be an int in [0, 100].
    4. Repeat-move B rule (AC5/D4): a move may appear at most once at a non-zero
       level, and optionally once at L0. Two non-zero levels, >2 rows, or a
       duplicated L0 are rejected.
    5. Dedup exact (level, move) pairs silently.
    6. Sort by (level, name) — normalizes storage order.
    7. Surgical untouched-rows guard (AC2/D1): every (level, move) row NOT
       implicated by the instruction must be byte-identical to current_learnset.
    8. Alternatives: drop hallucinated move names; keep valid ones.

    Returns the validated {draft, rationale, alternatives} contract.
    """
    if not isinstance(result, dict):
        raise SuggestError("The learnset suggestion came back in an unexpected shape.")

    draft = result.get("draft")
    if not isinstance(draft, dict) or not isinstance(draft.get("learnset"), list):
        raise SuggestError("The suggestion was missing a draft learnset list.")

    raw_rows = draft["learnset"]
    if not raw_rows:
        raise SuggestError("The suggestion proposed an empty learnset.")

    known_moves = _pool_move_names(move_pool)

    # Step 2+3: pool check + level range + normalize move name.
    validated_rows: list[dict[str, Any]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            raise SuggestError("A learnset row was not a dict.")
        move_raw = row.get("move")
        if not isinstance(move_raw, str) or not move_raw.strip():
            raise SuggestError("A learnset row is missing a move name.")
        canonical = known_moves.get(move_raw.strip().casefold())
        if canonical is None:
            raise SuggestError(
                f"The suggested move {move_raw!r} is not in the move pool; "
                "only moves from the merged move pool can be suggested."
            )
        level = row.get("level")
        if not isinstance(level, int) or isinstance(level, bool):
            raise SuggestError(
                f"The suggested level for {move_raw!r} is not an integer: {level!r}."
            )
        if not (0 <= level <= 100):
            raise SuggestError(
                f"The suggested level for {move_raw!r} ({level}) is outside [0, 100]."
            )
        validated_rows.append(
            {
                "level": level,
                "move": canonical,
                "reasoning": str(row.get("reasoning", "")),
            }
        )

    # Step 4: repeat-move B rule — deduplicate exact (level, move) pairs first,
    # then enforce: ≤1 non-zero level per move + optional 1 L0 per move.
    seen_pairs: set[tuple[int, str]] = set()
    deduped: list[dict[str, Any]] = []
    for row in validated_rows:
        pair = (row["level"], row["move"])
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            deduped.append(row)

    move_levels: dict[str, list[int]] = {}
    for row in deduped:
        move_levels.setdefault(row["move"], []).append(row["level"])

    for move_name, levels in move_levels.items():
        non_zero = [lvl for lvl in levels if lvl != 0]
        zeros = [lvl for lvl in levels if lvl == 0]
        if len(non_zero) > 1:
            raise SuggestError(
                f"The move {move_name!r} appears at multiple non-zero levels "
                f"({', '.join(str(l) for l in non_zero)}). A move may appear at "
                "most once at a non-zero level (plus optionally once at L0)."
            )
        if len(zeros) > 1:
            raise SuggestError(
                f"The move {move_name!r} appears more than once at level 0. "
                "A move may appear at most once at L0."
            )
        if len(levels) > 2:
            raise SuggestError(
                f"The move {move_name!r} appears {len(levels)} times; "
                "at most 2 rows per move are allowed (one L0 + one non-zero)."
            )

    # Step 6: sort by (level, move name).
    deduped.sort(key=lambda r: (r["level"], r["move"]))

    # Step 7: surgical untouched-rows guard.
    if mode == "surgical":
        _check_untouched_rows(deduped, current_learnset, instruction)

    # Step 8: alternatives — drop any whose extracted move name is hallucinated.
    alternatives = []
    for alt in result.get("alternatives") or []:
        if not isinstance(alt, dict):
            continue
        value = alt.get("value")
        if not value or not isinstance(value, str):
            continue
        # Alternatives are free-text like "Aqua Jet @ L24 — priority STAB option".
        # We only drop them if they contain a move name that isn't in the pool — but
        # since the format is freeform we just keep them as-is (they're advisory).
        alternatives.append({"value": value, "rationale": alt.get("rationale", "")})

    rationale_text = (result.get("rationale") or {}).get("learnset")
    rationale = (
        {"learnset": rationale_text} if isinstance(rationale_text, str) else {}
    )

    return {
        "draft": {"learnset": deduped},
        "rationale": rationale,
        "alternatives": alternatives,
    }


def _check_untouched_rows(
    proposed: list[dict[str, Any]],
    current_learnset: list[dict[str, Any]],
    instruction: str | None,
) -> None:
    """Assert that non-targeted rows are byte-identical to the current learnset.

    The "targeted" rows are ones the instruction plausibly names. Since we can't
    parse free-text instructions reliably, we define the implicated set as rows
    that differ between the proposal and the current learnset — and raise if any
    row is unexpectedly changed when no instruction covers it.

    Practical approach: build a set of (level, move) pairs from the current
    learnset. Every (level, move) pair in the proposed learnset that is NOT in
    the current set is a "change". In surgical mode we tolerate changes only for
    rows that the instruction plausibly targets. Since the instruction is free
    text we allow at most ONE new pair that wasn't in the current learnset, plus
    at most ONE pair that was removed from the current learnset (a single swap).
    More than that is evidence the model perturbed untouched rows.

    Edge case: if the current learnset is empty (no prior learnset), surgical mode
    is not meaningful — raise immediately.
    """
    if not current_learnset:
        raise SuggestError(
            "Surgical mode requires an existing learnset to edit, "
            "but this species has none. Use full mode instead."
        )

    current_pairs: set[tuple[int, str]] = {
        (row["level"], row["move"]) for row in current_learnset
    }
    proposed_pairs: set[tuple[int, str]] = {
        (row["level"], row["move"]) for row in proposed
    }

    added = proposed_pairs - current_pairs
    removed = current_pairs - proposed_pairs

    # A pure surgical swap touches exactly 1 row (removed) and adds exactly 1 row
    # (added). Tolerate: 0 changes (instruction had no effect, odd but valid) or
    # exactly 1 removal + 1 addition (one move swapped/changed).
    if len(added) > 1 or len(removed) > 1:
        changed = sorted(str(p) for p in (added | removed))
        raise SuggestError(
            "Surgical mode: the proposed learnset changed more rows than the "
            "instruction targets. Unexpected changes: "
            + ", ".join(changed)
            + ". Only the targeted move(s) may differ from the current learnset."
        )


def suggest_learnset(
    *,
    provider: LlmProvider,
    entry: dict[str, Any],
    move_pool: list[dict[str, Any]],
    abilities: list[dict[str, Any]],
    mode: str = "full",
    instruction: str | None = None,
    direction: str | None = None,
) -> dict[str, Any]:
    """Propose a level-up learnset for a species; never writes a file.

    Assembles the rubric + context (stats, types, abilities with effect text, evo
    context, current learnset, mode/instruction/direction), passes the full move
    pool as the ``cached_context`` prompt-cache prefix, runs ONE bounded Port call,
    then validates the draft (pool, level range, repeat-move B rule, surgical
    untouched-rows guard). Returns the reusable ``{draft, rationale, alternatives}``
    contract.

    Surgical mode with no instruction raises :class:`SuggestError` before the
    Port call — never wastes a round-trip. An empty pool raises similarly.
    """
    if not move_pool:
        raise SuggestError("No moves are available to suggest from.")

    if mode == "surgical" and not (instruction and instruction.strip()):
        raise SuggestError(
            "Surgical mode requires an instruction describing which move(s) to change."
        )

    cached_context = (
        "Move pool (pick ONLY from these moves):\n" + _format_move_pool(move_pool)
    )
    user_context = _build_learnset_user_context(
        entry, abilities, mode, instruction, direction
    )
    current_learnset = list(entry.get("learnset") or [])

    result = provider.propose(
        system=_build_learnset_rubric(),
        cached_context=cached_context,
        user=user_context,
        schema=_learnset_draft_schema(),
        max_tokens=LEARNSET_MAX_TOKENS,
    )

    return _validate_learnset_result(
        result,
        move_pool,
        mode=mode,
        current_learnset=current_learnset,
        instruction=instruction,
    )


# =========================================================================== #
# Ability creation — DRAFT a new owned ability + an engine-neutral behavior
# stub + a species-distribution plan (#8). The FIRST capability that *creates*
# owned content rather than picking from a pool, so it does NOT validate against
# an ability pool — instead it slugifies a new id, REFUSES to clobber an existing
# id (collision → SuggestError, D4 — a HARD fail), forces the behavior stub's
# engine_hints empty (D1 — a HARD fail), and validates each distribution row
# against the dex. A row naming an out-of-dex species or an invalid slot is
# DROPPED with a warning (bounce-1 amendment to D4) — the model knows ~1000
# species but this dex carries a subset, so an out-of-dex pick must not fail the
# whole proposal; valid rows are kept and `replaces` is enriched from the real
# current slot. The model is fed the in-dex species roster so its picks land.
# =========================================================================== #

# The "STUB" note the draft must carry on its behavior so the human's grounding
# pass is unmistakable. Asserted in validation so a draft that drops it still
# lands a clear marker on disk (D1).
_BEHAVIOR_STUB_NOTE = (
    "STUB — engine_hints ungrounded, needs human grounding pass"
)


def slugify_ability_id(name: str) -> str:
    """Derive a new ability's chrooked_id from its display name (D4).

    The owned-ability id style is lowercase with NO separators (matches
    ``aerodynamic``/``bonebreaker``): lowercase the name and strip everything
    outside ``[a-z0-9]``. ``"Tidal Force" -> "tidalforce"``.
    """
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def _build_ability_creation_rubric() -> str:
    """The ability-creation system rubric (the capability prompt).

    Directs the model to DESIGN one brand-new ability from a freeform direction:
    a name, a one-paragraph mechanic description, an advisory AI rating, an
    engine-neutral behavior spec stub (effects + test_cases + design notes), and
    a distribution plan (species BY NAME, slot, brief reasoning). Two hard rules
    fence off the core hazard and keep create honest:
    - MUST NOT write ``engine_hints`` — engine grounding is a human pass (D1).
    - MUST NOT reuse an existing ability name/id — create means new (D4).
    """
    triggers = ", ".join(sorted(_NEUTRAL_TRIGGERS))
    return (
        "You are a Pokémon game-design assistant. From a freeform direction, "
        "DESIGN ONE brand-new ability. Produce:\n"
        "- `ability`: a `name` (Title Case) and a one-paragraph `description` of "
        "the mechanic.\n"
        "- `behavior`: an engine-neutral behavior spec for the ability. Each "
        "effect is {summary, trigger, when, effect}; the `trigger` MUST be one of: "
        f"{triggers}. `when` is an optional plain-language condition (use '' if "
        "always-on). Include 2-3 `test_cases` ({given, expect}) and design `notes`.\n"
        "- `distribution`: a list of species the ability fits — each {species "
        "(real Pokémon NAME), slot (one of primary/secondary/hidden), reasoning}. "
        "Choose distribution species ONLY from the provided roster; do NOT name any "
        "species not listed (this dex is a subset of all Pokémon). It is fine to "
        "propose ZERO species (author now, distribute later).\n"
        "- `ai_rating`: a short advisory competitive-power rating (e.g. 'A- — "
        "strong pivot, not broken'). Advisory only; not stored as data.\n"
        "HARD RULES:\n"
        "1. You MUST NOT write any `engine_hints` — leave it empty. Engine "
        "grounding (C citations / Essentials translation) is a human pass; a "
        "fabricated citation is the one thing you must never invent.\n"
        "2. You MUST NOT reuse the name of any existing ability in the pool; this "
        "is a NEW ability.\n"
        "Put the ability + behavior + distribution in `draft`, the reasoning in "
        "`rationale` (with `ability`, `ai_rating`, and `distribution` strings), "
        "and up to three alternative ability ideas in `alternatives`."
    )


# The neutral battle triggers an effect may attach to. Mirrors
# ``collections.TRIGGERS`` (the behavior-spec source of truth) so the rubric and
# the schema stay aligned with the loader's accepted set.
_NEUTRAL_TRIGGERS = frozenset(
    {
        "switch-in",
        "turn-order",
        "accuracy-check",
        "damage-calc",
        "on-hit",
        "on-contact",
        "status-apply",
        "stat-change",
        "turn-end",
        "faint",
    }
)


def _ability_creation_draft_schema() -> dict[str, Any]:
    """The JSON schema the ability-creation draft is forced to match.

    Forces the {ability, behavior, distribution} draft shape so it is
    structurally valid before the create-flow validation (id slugify + collision,
    empty engine_hints, distribution species/slot checks). ``engine_hints`` is
    typed as an empty-only object so the model is steered away from filling it;
    the validator is still the hard gate (D1).
    """
    return {
        "type": "object",
        "properties": {
            "draft": {
                "type": "object",
                "properties": {
                    "ability": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["name", "description"],
                        "additionalProperties": False,
                    },
                    "behavior": {
                        "type": "object",
                        "properties": {
                            "effects": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "summary": {"type": "string"},
                                        "trigger": {"type": "string"},
                                        "when": {"type": "string"},
                                        "effect": {"type": "string"},
                                    },
                                    "required": ["summary", "trigger", "effect"],
                                    "additionalProperties": False,
                                },
                            },
                            "test_cases": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "given": {"type": "string"},
                                        "expect": {"type": "string"},
                                    },
                                    "required": ["given", "expect"],
                                    "additionalProperties": False,
                                },
                            },
                            "notes": {"type": "array", "items": {"type": "string"}},
                            "engine_hints": {
                                "type": "object",
                                "additionalProperties": False,
                            },
                        },
                        "required": ["effects"],
                        "additionalProperties": False,
                    },
                    "distribution": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "species": {"type": "string"},
                                "slot": {"type": "string"},
                                "reasoning": {"type": "string"},
                            },
                            "required": ["species", "slot"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["ability", "behavior", "distribution"],
                "additionalProperties": False,
            },
            "rationale": {
                "type": "object",
                "properties": {
                    "ability": {"type": "string"},
                    "ai_rating": {"type": "string"},
                    "distribution": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "alternatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["value", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["draft", "rationale", "alternatives"],
        "additionalProperties": False,
    }


def _format_roster(roster: list[str]) -> str:
    """Render the species roster as a compact, cache-stable bullet list."""
    return "\n".join(f"- {name}" for name in roster)


def suggest_ability_creation(
    *,
    provider: LlmProvider,
    direction: str,
    ability_pool: list[dict[str, str]],
    ability_ids: set[str],
    behavior_ids: set[str],
    dex_lookup: dict[str, dict[str, Any]],
    roster: list[str],
) -> dict[str, Any]:
    """Draft a brand-new ability + behavior stub + distribution; never writes.

    Assembles the rubric + the existing ability pool AND the species roster (both
    as ``cached_context``, so the model neither duplicates an existing ability nor
    names a species this dex doesn't carry), runs ONE bounded Port call, then
    validates the draft:

    - the new ability id is ``slugify_ability_id(name)`` and must NOT collide
      with an existing owned-ability OR behavior id (collision → a
      :class:`SuggestError` — create refuses to clobber, D4 — UNCHANGED hard fail);
    - the behavior stub's ``engine_hints`` MUST be empty (else SuggestError, D1);
    - each distribution row's species must exist in ``dex_lookup`` and its slot
      must be one of primary/secondary/hidden, and ``replaces`` is enriched from
      that species' real current slot occupant (D2/D4). A row naming an unknown
      species or an invalid slot is DROPPED with a ``warnings`` entry rather than
      failing the whole proposal (bounce-1 amendment to D4).

    ``direction`` is required (the freeform brief). ``dex_lookup`` is keyed by
    case-folded species NAME → merged dex entry. ``roster`` is the sorted list of
    in-dex species display names fed to the model. Returns the reusable
    ``{draft, rationale, alternatives}`` contract, plus a ``warnings`` list (empty
    when every row was valid).
    """
    if not direction or not direction.strip():
        raise SuggestError(
            "An ability-creation direction is required (describe the ability)."
        )

    cached_context = (
        "Existing abilities (do NOT reuse a name; this is a NEW ability):\n"
        + (_format_pool(ability_pool) or "(none)")
        + "\n\nSpecies roster (choose distribution species ONLY from these — this "
        "dex is a subset of all Pokémon; do NOT name any species not listed):\n"
        + (_format_roster(roster) or "(none)")
    )
    result = provider.propose(
        system=_build_ability_creation_rubric(),
        cached_context=cached_context,
        user=f"Direction from the user: {direction.strip()}",
        schema=_ability_creation_draft_schema(),
        max_tokens=LEARNSET_MAX_TOKENS,
    )

    return _validate_ability_creation_result(
        result,
        ability_ids=ability_ids,
        behavior_ids=behavior_ids,
        dex_lookup=dex_lookup,
    )


def _validate_ability_creation_result(
    result: dict[str, Any],
    *,
    ability_ids: set[str],
    behavior_ids: set[str],
    dex_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Shape + create-safety check on the ability-creation draft.

    Steps (in order):
    1. Shape: contract keys, a draft with `ability`/`behavior`/`distribution`.
    2. Ability name non-empty; ``chrooked_id = slugify_ability_id(name)``.
    3. Collision (D4): the id must not match any existing owned-ability OR
       behavior id → a SuggestError (create never clobbers — HARD fail, unchanged).
    4. Behavior stub (D1): engine_hints MUST be empty; at least one effect; each
       effect's trigger must be a neutral trigger. The stub is forced to carry
       empty engine_hints + aka and the "needs grounding" note. Filling
       engine_hints is a HARD SuggestError (unchanged).
    5. Distribution (D2/D4, softened at bounce 1): each species must exist in the
       dex (by name) and each slot ∈ {primary, secondary, hidden}; `replaces` is
       enriched from the species' real current slot occupant. A row that fails
       either check is DROPPED with a `warnings` entry (not a request failure);
       zero surviving rows is valid.

    A shape/name/collision/engine_hints miss is a :class:`SuggestError` — nothing
    is written and the endpoint surfaces an honest message. A bad distribution row
    is dropped-with-warning, mirroring how a hallucinated alternative is dropped.
    """
    if not isinstance(result, dict):
        raise SuggestError("The suggestion came back in an unexpected shape.")

    draft = result.get("draft")
    if not isinstance(draft, dict):
        raise SuggestError("The suggestion was missing a draft object.")

    ability = draft.get("ability")
    if not isinstance(ability, dict):
        raise SuggestError("The suggestion was missing a draft ability object.")
    name = ability.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SuggestError("The drafted ability has no name.")
    name = name.strip()
    chrooked_id = slugify_ability_id(name)
    if not chrooked_id:
        raise SuggestError(
            f"The drafted ability name {name!r} has no usable characters for an id."
        )

    # Collision (D4): create refuses to clobber an existing id. We surface the
    # collision in `warnings` AND raise so the route can both inform and refuse.
    if chrooked_id in ability_ids or chrooked_id in behavior_ids:
        raise SuggestError(
            f"id {chrooked_id!r} (from name {name!r}) already exists as an "
            "ability or behavior — rename before creating (create never clobbers)."
        )

    behavior = _validate_behavior_stub(draft.get("behavior"), name, chrooked_id)
    distribution, warnings = _validate_distribution(
        draft.get("distribution"), dex_lookup
    )

    rationale_raw = result.get("rationale") or {}
    rationale = {
        key: rationale_raw[key]
        for key in ("ability", "ai_rating", "distribution")
        if isinstance(rationale_raw.get(key), str)
    }

    alternatives = []
    for alt in result.get("alternatives") or []:
        if not isinstance(alt, dict):
            continue
        value = alt.get("value")
        if not value or not isinstance(value, str):
            continue
        alternatives.append({"value": value, "rationale": alt.get("rationale", "")})

    return {
        "draft": {
            "ability": {
                "chrooked_id": chrooked_id,
                "name": name,
                "description": str(ability.get("description", "")),
            },
            "behavior": behavior,
            "distribution": distribution,
        },
        "rationale": rationale,
        "alternatives": alternatives,
        "warnings": warnings,
    }


def _validate_behavior_stub(
    behavior: Any, name: str, chrooked_id: str
) -> dict[str, Any]:
    """Validate + normalize the engine-neutral behavior stub (D1).

    Enforces: at least one effect, every effect's trigger is a neutral trigger,
    and ``engine_hints`` is empty. Forces the stub's ``engine_hints``/``aka``
    empty and guarantees the "needs grounding" note is present so the on-disk
    write is unambiguously an ungrounded scaffold.
    """
    if not isinstance(behavior, dict):
        raise SuggestError("The suggestion was missing a draft behavior object.")

    # D1: the model must not fabricate engine grounding.
    engine_hints = behavior.get("engine_hints")
    if engine_hints:
        raise SuggestError(
            "The drafted behavior set engine_hints; engine grounding is a human "
            "pass and must be left empty (the LLM must not fabricate it)."
        )

    raw_effects = behavior.get("effects")
    if not isinstance(raw_effects, list) or not raw_effects:
        raise SuggestError("The drafted behavior has no effects.")

    effects = []
    for effect in raw_effects:
        if not isinstance(effect, dict):
            raise SuggestError("A behavior effect was not an object.")
        trigger = effect.get("trigger", "")
        if trigger not in _NEUTRAL_TRIGGERS:
            raise SuggestError(
                f"The behavior effect trigger {trigger!r} is not a neutral "
                f"trigger; allowed: {', '.join(sorted(_NEUTRAL_TRIGGERS))}."
            )
        when = effect.get("when")
        effects.append(
            {
                "summary": str(effect.get("summary", "")),
                "trigger": trigger,
                "when": when if (isinstance(when, str) and when.strip()) else None,
                "effect": str(effect.get("effect", "")),
            }
        )

    test_cases = [
        {"given": str(tc.get("given", "")), "expect": str(tc.get("expect", ""))}
        for tc in (behavior.get("test_cases") or [])
        if isinstance(tc, dict)
    ]

    notes = [str(note) for note in (behavior.get("notes") or []) if str(note).strip()]
    if _BEHAVIOR_STUB_NOTE not in notes:
        notes.append(_BEHAVIOR_STUB_NOTE)

    return {
        "name": name,
        "chrooked_id": chrooked_id,
        "applies_to": "ability",
        "aka": {},
        "effects": effects,
        "test_cases": test_cases,
        "notes": notes,
        "engine_hints": {},
    }


def _validate_distribution(
    distribution: Any, dex_lookup: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate + enrich the distribution plan (D2/D4, softened at bounce 1).

    Each row's ``species`` (proposed by NAME) must resolve in ``dex_lookup``
    (case-folded name → merged entry); the ``slot`` must be one of
    primary/secondary/hidden; ``replaces`` is enriched from that species' real
    current slot occupant ('(none)' for an empty slot).

    A row that names a species not in the dex, or an invalid slot, is DROPPED and
    recorded in the returned ``warnings`` list — not a request failure. This
    mirrors how a hallucinated alternative is dropped: the model knows ~1000
    species but this dex carries a subset, so an out-of-dex pick is expected and
    must not fail the whole proposal. An all-dropped distribution → an empty list
    (allowed) with warnings explaining why.

    Returns ``(rows, warnings)``.
    """
    warnings: list[str] = []
    if distribution is None:
        return [], warnings
    if not isinstance(distribution, list):
        warnings.append("Dropped the distribution — it was not a list.")
        return [], warnings

    rows: list[dict[str, Any]] = []
    for row in distribution:
        if not isinstance(row, dict):
            warnings.append("Dropped a distribution row — it was not an object.")
            continue
        species_name = row.get("species")
        if not isinstance(species_name, str) or not species_name.strip():
            warnings.append("Dropped a distribution row — missing a species name.")
            continue
        species_name = species_name.strip()
        entry = dex_lookup.get(species_name.casefold())
        if entry is None:
            warnings.append(f"Dropped {species_name!r} — not in the dex.")
            continue
        slot = row.get("slot")
        if slot not in _ABILITY_SLOTS:
            warnings.append(
                f"Dropped {species_name}/{slot!r} — invalid slot "
                f"(must be one of {', '.join(_ABILITY_SLOTS)})."
            )
            continue
        current = (entry.get("abilities") or {}).get(slot)
        rows.append(
            {
                "species": entry.get("chrooked_id", species_name),
                "slot": slot,
                "replaces": current if current else "(none)",
                "reasoning": str(row.get("reasoning", "")),
            }
        )
    return rows, warnings


# =========================================================================== #
# Move design / edit — DRAFT a new owned move OR an edit to an existing move
# (#9). Two modes:
#
# CREATE: the move name is new → slug the id, refuse collision (D4 hard),
#         produce a full field set (all move fields), produce an engine-neutral
#         behavior stub when the move has a custom mechanic.
# EDIT:   the caller supplies an existing move's chrooked_id → produce only the
#         fields that change (a delta), apply on top of the existing record, and
#         produce a before/after. Comparative input ("Thunderbolt but Dark")
#         resolves by cloning the source move's fields first.
#
# Behavior stub: if the draft includes a `behavior` key the same D1 rule applies
# (engine_hints forced empty, at least one effect, neutral triggers only). The
# LLM is instructed to include a behavior only when the move has a custom
# mechanic that cannot be expressed as a combination of existing effect/flags.
#
# Token budget: uses LEARNSET_MAX_TOKENS (a full move draft is a large
# structured output).
# =========================================================================== #

# The valid move categories per the loader (schema.py).
_MOVE_CATEGORIES: frozenset[str] = frozenset({"physical", "special", "status"})

# The fields the move loader (crud._MOVE_FIELDS) accepts on a PUT.  Used in
# edit mode to strip presentation-only fields (overridden_fields, base, etc.)
# that `build_moves` / the merged pool attaches but the loader rejects.
_MOVE_PAYLOAD_FIELDS: frozenset[str] = frozenset(
    {
        "name", "chrooked_id", "aka", "type",
        "category", "power", "accuracy", "pp", "description",
        "effect", "argument", "additional_effects", "flags", "priority", "target",
    }
)


def slugify_move_id(name: str) -> str:
    """Derive a new move's chrooked_id from its display name (D4).

    Mirrors ``slugify_ability_id``: lowercase, strip everything outside
    ``[a-z0-9]``. ``"Shadow Claw" -> "shadowclaw"``.
    """
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def _build_move_design_rubric(*, mode: str) -> str:
    """The move-design system rubric.

    CREATE mode: design one brand-new move from a freeform direction.
    EDIT mode:   propose only the fields to change and why.
    Both modes: include a behavior stub ONLY if the move needs a truly custom
    mechanic that cannot be expressed using standard effect/flags combinations;
    leave behavior absent otherwise. If present, the behavior stub MUST NOT set
    engine_hints.
    """
    triggers = ", ".join(sorted(_NEUTRAL_TRIGGERS))
    flags_list = (
        "contact, punching, biting, sound, slicing, wind, wing, "
        "kicking, piercing, bone, hammer, ballistic"
    )
    categories = "physical, special, status"
    if mode == "create":
        action = (
            "DESIGN ONE brand-new Pokémon move. Return ALL of these fields in `draft.move`:\n"
            "- `name` (Title Case display name)\n"
            "- `type` (one of the provided type pool)\n"
            f"- `category` (one of: {categories})\n"
            "- `power` (integer 1–250, or null for status moves)\n"
            "- `accuracy` (integer 1–100, or null for always-hit)\n"
            "- `pp` (integer 1–64)\n"
            "- `priority` (integer, usually 0; +1 for priority moves, -1 for last)\n"
            "- `target` (usually 'selected'; others: 'all-foes', 'all-allies', 'all', "
            "'self', 'random-foe', 'all-except-self')\n"
            f"- `flags` (array from: {flags_list}; use [] if none apply)\n"
            "- `effect` (plain effect name; use 'hit' for plain damage; "
            "examples: 'recoil', 'absorb', 'two-hit')\n"
            "- `additional_effects` (array of {effect, chance} for secondary "
            "effects e.g. burn 30%; use [] if none)\n"
            "- `description` (one sentence, plain English, concise)\n"
        )
    else:
        action = (
            "PROPOSE CHANGES to an existing Pokémon move. Return ONLY the fields "
            "that should change in `draft.move` (plus `name` always). Do NOT return "
            "unchanged fields. Explain what is changing and why in `rationale.edit`."
        )
    behavior_rule = (
        "\nBEHAVIOR STUB (OPTIONAL): include `draft.behavior` ONLY if this move "
        "needs a truly custom mechanic that cannot be expressed using standard "
        "effect/flags combinations. If included:\n"
        "- effects[]: each {summary, trigger, when, effect}; trigger MUST be one "
        f"of: {triggers}\n"
        "- test_cases[]: each {given, expect}\n"
        "- notes[]: design context\n"
        "HARD RULE: you MUST NOT set engine_hints — leave it empty or absent. "
        "Engine grounding (C citations / Essentials translation) is a human pass; "
        "a fabricated citation is the one thing you must never invent.\n"
        "If the move is a standard damaging move with no unusual mechanic, "
        "OMIT the behavior field entirely."
    )
    return (
        "You are a Pokémon game-design assistant. "
        + action
        + behavior_rule
        + "\n\nPut the move (and optionally behavior) in `draft`, the design "
        "reasoning in `rationale` (with `move` string and `edit` string for edits), "
        "and up to three alternative design ideas in `alternatives`."
    )


def _move_design_draft_schema() -> dict[str, Any]:
    """JSON schema for the move-design draft.

    `draft.move` is the proposed field set (all fields for create, partial for edit).
    `draft.behavior` is optional (only when a custom mechanic is needed).
    """
    behavior_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "effects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "trigger": {"type": "string"},
                        "when": {"type": "string"},
                        "effect": {"type": "string"},
                    },
                    "required": ["summary", "trigger", "effect"],
                    "additionalProperties": False,
                },
            },
            "test_cases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "given": {"type": "string"},
                        "expect": {"type": "string"},
                    },
                    "required": ["given", "expect"],
                    "additionalProperties": False,
                },
            },
            "notes": {"type": "array", "items": {"type": "string"}},
            "engine_hints": {
                "type": "object",
                "additionalProperties": False,
            },
        },
        "required": ["effects"],
        "additionalProperties": False,
    }

    move_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"type": "string"},
            "category": {"type": "string"},
            "power": {"type": ["integer", "null"]},
            "accuracy": {"type": ["integer", "null"]},
            "pp": {"type": "integer"},
            "priority": {"type": "integer"},
            "target": {"type": "string"},
            "flags": {"type": "array", "items": {"type": "string"}},
            "effect": {"type": "string"},
            "additional_effects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "effect": {"type": "string"},
                        "chance": {"type": "integer"},
                    },
                    "required": ["effect", "chance"],
                    "additionalProperties": False,
                },
            },
            "description": {"type": "string"},
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    return {
        "type": "object",
        "properties": {
            "draft": {
                "type": "object",
                "properties": {
                    "move": move_schema,
                    "behavior": behavior_schema,
                },
                "required": ["move"],
                "additionalProperties": False,
            },
            "rationale": {
                "type": "object",
                "properties": {
                    "move": {"type": "string"},
                    "edit": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "alternatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["value", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["draft", "rationale", "alternatives"],
        "additionalProperties": False,
    }


def suggest_move(
    *,
    provider: LlmProvider,
    direction: str,
    type_pool: list[str],
    move_ids: set[str],
    mode: str = "create",
    existing_move: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Draft a brand-new move (create) or propose edits to an existing one (edit).

    CREATE mode (``mode="create"``):
    - ``direction`` is required — a freeform design brief.
    - ``existing_move`` must be None.
    - The draft covers all move fields; the id is slugified from the name.
    - A name colliding with an existing owned move id → SuggestError (D4, hard fail).
    - If the move needs a custom mechanic the LLM includes a behavior stub; the
      stub's ``engine_hints`` MUST be empty (D1, hard fail if filled).

    EDIT mode (``mode="edit"``):
    - ``existing_move`` is required — the current move record (chrooked_id, all fields).
    - ``direction`` describes what to change.
    - The draft carries only the changed fields (plus ``name`` always); the existing
      move fields are the baseline. A before/after delta is included in the response.
    - The existing move's id is reused — collision is expected (it is an overwrite);
      no collision check for the EXISTING id.
    - Comparative input ("Thunderbolt but Dark") is handled by the LLM: it clones
      the source move's type and applies the delta (the caller passes the direction
      unchanged; the rubric is what resolves it).

    ``type_pool`` is the merged type universe; a hallucinated type is a SuggestError.
    ``move_ids`` is the set of existing owned move chrooked_ids (for create collision).
    Returns the reusable ``{draft, rationale, alternatives}`` contract plus:
    - ``warnings``: validation warnings (empty list when all clean).
    - ``before``: for edit mode, the original field values for changed fields.
    - ``chrooked_id``: the resolved id for the move (for the accept PUT path).
    """
    if not direction or not direction.strip():
        raise SuggestError("A move design direction is required.")

    if mode not in ("create", "edit"):
        raise SuggestError(f"Unknown mode {mode!r}; expected 'create' or 'edit'.")

    if mode == "edit" and existing_move is None:
        raise SuggestError("Edit mode requires an existing_move to be provided.")

    type_pool_str = "\n".join(f"- {t}" for t in sorted(type_pool))

    if mode == "create":
        cached_context = (
            "Type pool (use ONLY types from this list):\n"
            + (type_pool_str or "(none)")
            + "\n\nExisting owned move ids (the new move's id must NOT collide with "
            "any of these):\n"
            + ("\n".join(f"- {mid}" for mid in sorted(move_ids)) or "(none)")
        )
        user_msg = f"Direction: {direction.strip()}"
    else:
        assert existing_move is not None
        move_summary = _format_existing_move(existing_move)
        cached_context = (
            "Type pool (use ONLY types from this list):\n"
            + (type_pool_str or "(none)")
        )
        user_msg = (
            f"Existing move:\n{move_summary}\n\n"
            f"Edit direction: {direction.strip()}"
        )

    result = provider.propose(
        system=_build_move_design_rubric(mode=mode),
        cached_context=cached_context,
        user=user_msg,
        schema=_move_design_draft_schema(),
        max_tokens=LEARNSET_MAX_TOKENS,
    )

    return _validate_move_result(
        result,
        type_pool=type_pool,
        move_ids=move_ids,
        mode=mode,
        existing_move=existing_move,
    )


def _format_existing_move(move: dict[str, Any]) -> str:
    """Render a move entry as compact text for the edit-mode user message."""
    lines = [
        f"name: {move.get('name', '?')}",
        f"chrooked_id: {move.get('chrooked_id', '?')}",
        f"type: {move.get('type', '?')}",
        f"category: {move.get('category', '?')}",
        f"power: {move.get('power', 'null')}",
        f"accuracy: {move.get('accuracy', 'null')}",
        f"pp: {move.get('pp', '?')}",
        f"priority: {move.get('priority', 0)}",
        f"target: {move.get('target', 'selected')}",
        f"flags: {move.get('flags', [])}",
        f"effect: {move.get('effect', 'hit')}",
        f"additional_effects: {move.get('additional_effects', [])}",
        f"description: {move.get('description', '')}",
    ]
    return "\n".join(lines)


def _validate_move_result(
    result: dict[str, Any],
    *,
    type_pool: list[str],
    move_ids: set[str],
    mode: str,
    existing_move: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate and normalize the move-design draft.

    Steps:
    1. Shape: contract keys, a draft with `move`.
    2. Name non-empty; ``chrooked_id = slugify_move_id(name)``.
    3. For CREATE: collision check (D4, hard fail if id in move_ids).
    4. Field validation: category ∈ MOVE_CATEGORIES, type ∈ type_pool,
       power/accuracy/pp sane ranges, flags from MOVE_FLAGS.
    5. Behavior stub (if present, D1): engine_hints MUST be empty.
    6. For EDIT: build before/after delta from existing_move.
    """
    from chrooked_pokedex.model.schema import MOVE_FLAGS

    if not isinstance(result, dict):
        raise SuggestError("The suggestion came back in an unexpected shape.")

    draft = result.get("draft")
    if not isinstance(draft, dict):
        raise SuggestError("The suggestion was missing a draft object.")

    move_draft = draft.get("move")
    if not isinstance(move_draft, dict):
        raise SuggestError("The suggestion was missing a draft move object.")

    # --- Name ---
    name = move_draft.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SuggestError("The drafted move has no name.")
    name = name.strip()
    chrooked_id = slugify_move_id(name)
    if not chrooked_id:
        raise SuggestError(
            f"The drafted move name {name!r} has no usable characters for an id."
        )

    # --- Collision (CREATE only, D4) ---
    if mode == "create" and chrooked_id in move_ids:
        raise SuggestError(
            f"id {chrooked_id!r} (from name {name!r}) already exists as an owned "
            "move — rename before creating (create never clobbers)."
        )

    type_pool_set = {t.casefold() for t in type_pool}

    # --- Field validation ---
    warnings: list[str] = []
    validated: dict[str, Any] = {"name": name}

    # type
    move_type = move_draft.get("type")
    if move_type is not None:
        if not isinstance(move_type, str) or move_type.casefold() not in type_pool_set:
            raise SuggestError(
                f"The drafted move has an unrecognized type {move_type!r}; "
                f"must be one of the type pool."
            )
        # Normalize to the pool's canonical casing.
        canonical_type = next(
            t for t in type_pool if t.casefold() == move_type.casefold()
        )
        validated["type"] = canonical_type
    elif mode == "create":
        raise SuggestError("The drafted move is missing a type.")

    # category
    category = move_draft.get("category")
    if category is not None:
        if not isinstance(category, str) or category.lower() not in _MOVE_CATEGORIES:
            raise SuggestError(
                f"The drafted move has an invalid category {category!r}; "
                f"must be one of: {', '.join(sorted(_MOVE_CATEGORIES))}."
            )
        validated["category"] = category.lower()
    elif mode == "create":
        raise SuggestError("The drafted move is missing a category.")

    # power
    power = move_draft.get("power")
    if "power" in move_draft:
        if power is not None:
            if not isinstance(power, int) or not (1 <= power <= 250):
                raise SuggestError(
                    f"The drafted move has an invalid power {power!r}; "
                    "must be an integer 1–250 or null."
                )
        validated["power"] = power

    # accuracy
    accuracy = move_draft.get("accuracy")
    if "accuracy" in move_draft:
        if accuracy is not None:
            if not isinstance(accuracy, int) or not (1 <= accuracy <= 100):
                raise SuggestError(
                    f"The drafted move has an invalid accuracy {accuracy!r}; "
                    "must be an integer 1–100 or null."
                )
        validated["accuracy"] = accuracy

    # pp
    pp = move_draft.get("pp")
    if "pp" in move_draft:
        if not isinstance(pp, int) or not (1 <= pp <= 64):
            raise SuggestError(
                f"The drafted move has an invalid pp {pp!r}; "
                "must be an integer 1–64."
            )
        validated["pp"] = pp
    elif mode == "create":
        raise SuggestError("The drafted move is missing pp.")

    # priority
    if "priority" in move_draft:
        priority = move_draft["priority"]
        if not isinstance(priority, int):
            raise SuggestError(
                f"The drafted move has an invalid priority {priority!r}; must be an integer."
            )
        validated["priority"] = priority

    # target
    if "target" in move_draft:
        validated["target"] = str(move_draft["target"])

    # flags
    if "flags" in move_draft:
        raw_flags = move_draft["flags"]
        if not isinstance(raw_flags, list):
            raise SuggestError("The drafted move flags field is not a list.")
        bad_flags = [f for f in raw_flags if f not in MOVE_FLAGS]
        if bad_flags:
            warnings.append(
                f"Dropped unknown flags {bad_flags!r}; "
                f"allowed: {', '.join(sorted(MOVE_FLAGS))}."
            )
            raw_flags = [f for f in raw_flags if f in MOVE_FLAGS]
        validated["flags"] = raw_flags

    # effect
    if "effect" in move_draft:
        validated["effect"] = str(move_draft["effect"])

    # additional_effects
    if "additional_effects" in move_draft:
        raw_ae = move_draft["additional_effects"]
        if not isinstance(raw_ae, list):
            raise SuggestError("The drafted move additional_effects is not a list.")
        ae_list = []
        for entry in raw_ae:
            if not isinstance(entry, dict):
                continue
            effect_name = entry.get("effect")
            chance = entry.get("chance")
            if isinstance(effect_name, str) and isinstance(chance, int):
                ae_list.append({"effect": effect_name, "chance": chance})
        validated["additional_effects"] = ae_list

    # description
    if "description" in move_draft:
        validated["description"] = str(move_draft["description"])

    # --- Behavior stub (D1) ---
    behavior: dict[str, Any] | None = None
    if "behavior" in draft and draft["behavior"] is not None:
        behavior = _validate_behavior_stub(
            draft["behavior"], name=name, chrooked_id=chrooked_id
        )

    # --- Build before/after and full merged move for edit mode ---
    # In EDIT mode `validated` contains only the delta (fields the LLM proposed).
    # `draft.move` must carry the FULL merged record so the skill can PUT it
    # as-is without read-merging on the client side.  The `before` keeps only the
    # pre-change values of the changed fields (for the before/after display table).
    before: dict[str, Any] | None = None
    if mode == "edit" and existing_move is not None:
        # Capture the pre-change values for only the changed fields (minus `name`,
        # which the caller already knows from the existing move).
        before = {
            field: existing_move.get(field)
            for field in validated
            if field != "name"
        }
        # Merge: start from the full existing move, overlay the proposed delta.
        # Strip presentation-only fields (overridden_fields, base, …) that the
        # merged pool attaches but the loader's _MOVE_FIELDS rejects on PUT.
        # Also exclude chrooked_id here — it is re-injected as the dict key below.
        full_move: dict[str, Any] = {
            k: v
            for k, v in existing_move.items()
            if k in _MOVE_PAYLOAD_FIELDS and k != "chrooked_id"
        }
        full_move.update(validated)
    else:
        full_move = dict(validated)

    # --- Rationale + alternatives ---
    rationale_raw = result.get("rationale") or {}
    rationale: dict[str, str] = {}
    for key in ("move", "edit"):
        val = rationale_raw.get(key)
        if isinstance(val, str) and val.strip():
            rationale[key] = val

    alternatives = []
    for alt in result.get("alternatives") or []:
        if not isinstance(alt, dict):
            continue
        value = alt.get("value")
        if not value or not isinstance(value, str):
            continue
        alternatives.append({"value": value, "rationale": alt.get("rationale", "")})

    out: dict[str, Any] = {
        "draft": {
            "move": {"chrooked_id": chrooked_id, **full_move},
        },
        "rationale": rationale,
        "alternatives": alternatives,
        "warnings": warnings,
        "chrooked_id": chrooked_id,
    }
    if behavior is not None:
        out["draft"]["behavior"] = behavior
    if before is not None:
        out["before"] = before

    return out
