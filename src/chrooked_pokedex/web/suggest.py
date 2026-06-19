"""The ability-suggest capability over the reusable propose Seam (M2).

This is the first capability built on the LLM Port (``web/llm.py``). It assembles
the species' context server-side from the snapshot ⊕ Ruleset (the merged dex
entry + the full ability pool with descriptions), builds the ability-suggest
rubric (ported from the dreamstone ``ability-suggest`` skill), calls the Port for
ONE structured draft, validates that every proposed ability exists in the real
pool, and returns the reusable contract::

    {draft: {abilities: {...partial slots...}},
     rationale: {<slot>: str},
     alternatives: [{value, rationale}]}

It **never writes a file** — the draft flows back to the caller (the chat skill
or, later, the UI), and the accept path is the existing CRUD/loader Boundary.

Reuse note (ac6): a new capability (#7 learnset, #8 new-ability, #9 move, #10
stats, #32) is a sibling of this module — it supplies its own ``_build_rubric``
(the capability prompt), its own context assembly (the field set it proposes),
and its own draft schema, then reuses the exact same three shared pieces: the
:class:`~chrooked_pokedex.web.llm.LlmProvider` Port, this ``{draft, rationale,
alternatives}`` contract, and the accept-through-CRUD path. The Seam (assemble →
call → validate → return; never write) is fixed; only the rubric + field set vary.
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
