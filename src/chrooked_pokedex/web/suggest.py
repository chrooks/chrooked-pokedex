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

from typing import Any

from .llm import DEFAULT_MAX_TOKENS, LlmProvider

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
