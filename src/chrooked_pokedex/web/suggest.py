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
