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

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from . import learnset_skeleton
from .llm import DEFAULT_MAX_TOKENS, LlmProvider, condense_provider
from .lore import LoreError, LoreProvider
from .lore_text import render_lore

# Learnset responses return a whole list with per-move reasoning (~15–25 rows,
# 2–3k tokens in full mode). The shared DEFAULT_MAX_TOKENS (1024) is sized for
# the tiny ability/typing/stats outputs and truncates a learnset response.
# Only this capability uses the larger budget; the other three stay on 1024.
# A full learnset draft is ~20-25 rows, each with a per-row `reasoning` string,
# plus a section rationale and alternatives. A verbose generation of that overran
# the old 4096 cap → truncation (or a truncation-adjacent empty draft), the real
# cause of the "missing a draft learnset list" dead-end. 8192 gives comfortable
# headroom (a typical response is ~2k completion tokens); the repair layer is the
# safety net for the rest.
LEARNSET_MAX_TOKENS = 8192

# Learnset drafts are the fattest, most fragile output; Chris's ruling is that
# they should retry harder than other modes (which default to one extra attempt).
_LEARNSET_MAX_RETRIES = 3

# Learnset shape bounds — the tunable knobs for suggested-learnset consistency.
# Derived from a July 2026 audit of all 1,162 curated ruleset learnsets:
# median 21 rows, mean 20.5, p10–p90 spread 14–27; max level ≤70 everywhere;
# moves at L5-or-below median 5 (worst case 12 — the early-packing problem).
# The rubric states these and validation enforces them (FULL mode only —
# surgical edits inherit the current learnset's shape and must not fail on it).
LEARNSET_SIZE_MIN = 16  # floor scales down when the move pool is smaller
LEARNSET_SIZE_MAX = 26
LEARNSET_MAX_LEVEL = 75  # no level-up move above this level
LEARNSET_MAX_MOVES_THROUGH_L5 = 5  # rows with level ≤5, counting the L0/L1 kit
LEARNSET_MAX_MOVES_THROUGH_L10 = 7  # rows with level ≤10
# Anchors each claim one of the skeleton's 20 non-pinned grid seats, and the trim
# pass drops flavor → widener → status → STAB before ever touching one. Leave
# room for a dual-type ladder (~8 rungs) plus the status slots (~4). A knob, not
# a law: raise it and the generated ladder shrinks to match.
LEARNSET_ANCHOR_MAX = 8

# The shared band Contract (also the workbench Signifier's data and the
# coverage-band source for scripts/move_coverage.py). The pacing bands feed the
# learnset rubric prompt and ADVISORY warnings — never a hard fail: a July 2026
# audit found 32% of curated attack rows over these caps, so enforcement would
# reject nearly every draft. Tune the bounds in learnset_rubric.json.
_BAND_CONTRACT_PATH = Path(__file__).resolve().parent / "learnset_rubric.json"


def _pacing_bands() -> list[dict[str, Any]]:
    """The level→BP pacing bands, read fresh so edits apply without a restart."""
    return json.loads(_BAND_CONTRACT_PATH.read_text("utf-8"))["bands"]


def _format_pacing_bands() -> str:
    """The pacing bands as one compact rubric clause, e.g. ``L1–19: ≤60BP · …``."""
    parts = []
    for band in _pacing_bands():
        span = (
            f"L{band['level_min']}–{band['level_max']}"
            if band["level_max"] < 100
            else f"L{band['level_min']}+"
        )
        cap = band.get("bp_max")
        parts.append(
            f"{span}: ≤{cap}BP" if cap is not None
            else f"{span}: no cap (the 100+BP payoffs live here)"
        )
    return " · ".join(parts)


# The ability slots an Override may set, in display order. The draft is a partial
# Override: only the slots the model proposes appear.
_ABILITY_SLOTS = ("primary", "secondary", "hidden")


class SuggestError(Exception):
    """A suggest request could not be served as asked (→ a clean 4xx detail).

    Distinct from an LLM transport failure (`LlmError`): this is a server-side
    validation problem — an unknown species, or a draft naming an ability that
    isn't in the real pool — that the endpoint surfaces as an honest message.

    ``salvage`` optionally carries a best-effort *editable* draft even though
    validation failed — set when the draft is fully normalized (pool-checked,
    deduped, sorted) and only tripped a soft shape bound (e.g. a learnset with
    too many early-level rows). The web layer may hand it back as a 200 with an
    ``error`` note so the author can fix it in place, instead of a bare 422.
    ``None`` when nothing usable survived.
    """

    def __init__(self, *args: Any, salvage: dict[str, Any] | None = None) -> None:
        super().__init__(*args)
        self.salvage = salvage


# --------------------------------------------------------------------------- #
# Lore injection (#77) — shared by the two capabilities that reason from a
# creature's identity. Off by default and inert until asked for: with the mode
# off the assembled prompt is byte-identical to what it was before this existed.
#
# Why: given no sources, the model answers from training recall, and on
# 2026-08-12 it justified a Glalie ability with "its name derived from *glace*
# (French: ice)". The real etymology is glacier + goalie. Fetching first and
# injecting the text turns recall into reading.
# --------------------------------------------------------------------------- #

# The three modes a request may ask for. Anything else is off — a typo in the
# request body is not consent to start making network calls.
LORE_MODES = ("off", "full", "condensed")

# The condensation is a brief, not a design. A tight cap keeps the extra call
# cheap and stops it re-expanding the very text it was asked to shrink.
_CONDENSE_MAX_TOKENS = 700

_CONDENSE_RUBRIC = (
    "You compress reference text. Given researched lore about one Pokémon, "
    "return a tight factual brief of it: what the creature IS, its category, "
    "the recurring facts across its Pokedex entries, its design origin, and its "
    "name etymology. Keep every concrete noun, place, animal, object, and "
    "language a name derives from — those specifics are the whole point. Drop "
    "repetition and game-version chatter. Invent NOTHING: if the source does not "
    "say it, it does not appear. Aim for under 900 characters of plain prose."
)

_CONDENSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"lore": {"type": "string"}},
    "required": ["lore"],
    "additionalProperties": False,
}

# Added to the rubric — and ONLY when the lookup found nothing. Without it,
# turning lore on for a bespoke species makes fabrication more likely, not less:
# the model reads "no lore" as an invitation. The user-context block states the
# absence; this makes owning it in the rationale a rule.
_NO_LORE_RUBRIC_NOTE = (
    "LORE LOOKUP RAN AND FOUND NOTHING for this species. You must NOT supply "
    "dex flavor, etymology, or real-world inspiration from memory — say plainly "
    "in your rationale that no published lore was available, and reason only "
    "from the concrete data you were given."
)


def normalize_lore_mode(value: Any) -> str:
    """The requested lore mode, or ``"off"`` for anything unrecognized."""
    return value if isinstance(value, str) and value in LORE_MODES else "off"


@dataclass(frozen=True)
class LoreInjection:
    """What one lore lookup contributes to one suggest call.

    ``block`` goes into the USER context, never the rubric: the rubric is the
    cache-stable prefix shared across species, and varying it per species would
    defeat prompt caching. ``rubric_note`` is the one exception — a single
    do-not-invent line, added only on a miss.
    """

    provenance: Mapping[str, Any]
    block: str = ""
    rubric_note: str = ""


LORE_OFF = LoreInjection(provenance={"mode": "off"})


def build_lore_injection(
    *,
    entry: dict[str, Any],
    lore_mode: str,
    lore_provider: LoreProvider | None,
    provider: LlmProvider,
) -> LoreInjection:
    """Fetch and render the lore block for one species, or nothing at all.

    Returns :data:`LORE_OFF` — an empty block and a bare ``{"mode": "off"}``
    provenance — when the mode is off or no provider is attached. A
    :class:`LoreError` degrades to the same emptiness with the reason recorded:
    a lore lookup is an enhancement, and a dead network must never cost the
    author their suggestion.
    """
    mode = normalize_lore_mode(lore_mode)
    if mode == "off" or lore_provider is None:
        return LORE_OFF

    chrooked_id = str(entry.get("chrooked_id", ""))
    species_name = str(entry.get("name") or chrooked_id)
    try:
        result = lore_provider.fetch(chrooked_id, species_name)
    except LoreError as error:
        return LoreInjection(
            provenance={
                "mode": mode,
                "found": False,
                "sources": [],
                "chars": 0,
                "error": str(error),
            }
        )

    # render_lore owns the not-found statement, the base-species label, and the
    # character cap — all of it decided once, in one place.
    block = render_lore(
        found=result.found,
        genus=result.genus,
        dex_entries=result.dex_entries,
        origin=result.origin,
        name_origin=result.name_origin,
        requested_id=chrooked_id,
        base_species=result.base_species,
    )

    ran_as = mode
    if mode == "condensed" and result.found:
        condensed = _condense_lore(provider, block)
        if condensed:
            block = condensed
        else:
            # The condenser is an optimization; its failure costs the author
            # nothing but a longer prompt. Provenance names what actually ran.
            ran_as = "full"

    provenance: dict[str, Any] = {
        "mode": ran_as,
        "found": result.found,
        "sources": list(result.sources),
        "chars": len(block),
    }
    if result.base_species and result.base_species != chrooked_id:
        provenance["base_species"] = result.base_species

    return LoreInjection(
        provenance=provenance,
        block=block,
        rubric_note="" if result.found else _NO_LORE_RUBRIC_NOTE,
    )


def _condense_lore(provider: LlmProvider, block: str) -> str:
    """One extra bounded call turning the fetched lore into a tight brief.

    Returns ``""`` on any failure, which the caller reads as "keep the raw
    block". The broad catch is deliberate: every way this call can go wrong — a
    transport error, a missing key, a malformed draft — has the same right
    answer, and none of them is worth failing a suggestion over.
    """
    try:
        result = condense_provider(provider).propose(
            system=_CONDENSE_RUBRIC,
            cached_context="",
            user=block,
            schema=_CONDENSE_SCHEMA,
            max_tokens=_CONDENSE_MAX_TOKENS,
        )
    except Exception:  # noqa: BLE001 — see docstring
        return ""
    text = result.get("lore") if isinstance(result, dict) else None
    return text.strip() if isinstance(text, str) else ""


def _with_lore_note(system: str, injection: LoreInjection) -> str:
    """The rubric, plus the do-not-invent line when the lookup found nothing."""
    return f"{system}\n{injection.rubric_note}" if injection.rubric_note else system


# --------------------------------------------------------------------------- #
# Shared repair layer — validate → ONE retry feeding the violation back →
# degrade honestly. Applied uniformly across the raise-based modes (typing,
# stats, lore-options, learnset). A hard truncation still surfaces as an
# ``LlmError`` from the Port (finish_reason == "length") and is NOT retried —
# retrying a truncation is futile; that is why the token limit is the real cure.
# Abilities keeps its own per-slot PARTIAL degradation (same one-retry principle,
# different degradation), built in ``suggest_ability``.
# --------------------------------------------------------------------------- #


def _describe_draft(result: Any) -> str:
    """An honest one-line description of what the model actually returned, so a
    twice-failed suggest names the shape instead of leaving a bare dead end."""
    if not isinstance(result, dict):
        return f"the response was not an object ({type(result).__name__})"
    draft = result.get("draft")
    if not isinstance(draft, dict):
        return f"the response had no draft object (top-level keys: {sorted(result)})"
    if not draft:
        return "the draft object was empty (likely truncated)"
    return f"the draft had keys {sorted(draft)}"


def _generic_repair_note(error_msg: str) -> str:
    """The correction fed back to the model on the single self-repair retry."""
    return (
        "Your previous answer was rejected: "
        f"{error_msg}\n"
        "Return the COMPLETE structured proposal matching the required schema — "
        "every required field present and non-empty. Do not omit any field, and "
        "do not truncate the output."
    )


def propose_with_repair(
    *,
    provider: LlmProvider,
    system: str,
    cached_context: str,
    user: str,
    schema: dict[str, Any],
    max_tokens: int,
    validate: "Callable[[dict[str, Any]], dict[str, Any]]",
    max_retries: int = 1,
) -> dict[str, Any]:
    """Propose → ``validate``; on a :class:`SuggestError`, retry up to
    ``max_retries`` times feeding the violation back each round, then validate
    again. The final failure raises an honest error naming what the model
    returned (a truncated/empty draft is not a bare dead end). ``LlmError`` from
    the Port (transport / hard truncation) propagates unretried.

    ``max_retries`` is the number of *extra* attempts after the first. Modes with
    fragile, high-token drafts (learnset) pass a higher value — Chris's ruling is
    that learnset suggestion should be especially eager to retry. The deterministic
    auto-repairs a validator can make (dedupe, drop-and-warn) never reach here;
    they happen inside ``validate`` and cost no retry."""

    def _run(user_text: str) -> dict[str, Any]:
        return provider.propose(
            system=system,
            cached_context=cached_context,
            user=user_text,
            schema=schema,
            max_tokens=max_tokens,
        )

    result = _run(user)
    for _ in range(max(0, max_retries)):
        try:
            return _validate_draft(validate, result)
        except SuggestError as error:
            result = _run(f"{user}\n\n{_generic_repair_note(str(error))}")
    try:
        return _validate_draft(validate, result)
    except SuggestError as final_error:
        attempts = max(1, max_retries)
        plural = "retry" if attempts == 1 else "retries"
        # Carry any salvageable editable draft through the wrapper so the caller
        # can offer it for hand-editing rather than only naming the failure.
        raise SuggestError(
            f"{final_error} — after {attempts} automatic {plural}, "
            f"{_describe_draft(result)}.",
            salvage=getattr(final_error, "salvage", None),
        ) from final_error


_DRAFT_SHAPE_ERRORS = (AttributeError, TypeError, KeyError, ValueError, IndexError)


def _validate_draft(
    validate: "Callable[[dict[str, Any]], dict[str, Any]]", result: dict[str, Any]
) -> dict[str, Any]:
    """LLM output is untrusted; a validator crashing on its shape IS a validation
    failure (retryable), never a 500."""
    try:
        return validate(result)
    except SuggestError:
        raise
    except _DRAFT_SHAPE_ERRORS as exc:
        raise SuggestError(
            f"The draft had an unexpected shape ({type(exc).__name__}: {exc})"
        ) from exc


def _rationale_map(result: dict[str, Any], fallback_key: str) -> dict[str, str]:
    """The model sometimes returns ``rationale`` as a bare string instead of an
    object; tolerate both. A bare string lands under ``fallback_key``."""
    raw = result.get("rationale")
    if isinstance(raw, dict):
        return {k: v for k, v in raw.items() if isinstance(v, str)}
    if isinstance(raw, str) and raw:
        return {fallback_key: raw}
    return {}


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
        {
            "name": entry["name"],
            "description": entry.get("description", ""),
            "custom": bool(entry.get("custom")),
        }
        for entry in abilities
        if entry.get("name")
    ]
    return sorted(pool, key=lambda entry: entry["name"])


def _pool_names(pool: list[dict[str, str]]) -> set[str]:
    """The case-folded set of real ability names, for validating a draft."""
    return {entry["name"].strip().casefold() for entry in pool}


def _format_pool(pool: list[dict[str, Any]]) -> str:
    """Render the ability pool as a compact, cache-stable text block.

    Net-new created abilities get a ``[CUSTOM]`` tag, same as the move pool: the
    model has no training prior pulling toward them, so untagged they read as
    noise among the canon names and never get picked.
    """
    return "\n".join(
        f"- {entry['name']}: {entry['description']}"
        f"{' [CUSTOM]' if entry.get('custom') else ''}"
        for entry in pool
    )


def _format_learnset(learnset: list[dict[str, Any]]) -> str:
    """Render the learnset as ``L<level> <Move>`` lines, or a placeholder."""
    if not learnset:
        return "(no level-up learnset)"
    return ", ".join(
        f"L{entry.get('level', '?')} {entry.get('move', '?')}" for entry in learnset
    )


def _format_move_names(learnset: list[dict[str, Any]]) -> str:
    """Render just the move NAMES (no levels) — the full-mode prior-art hint.

    Full mode redesigns the pacing from scratch; showing the current level
    placement anchors the model into copying it and inheriting its early-level
    packing. Names-only keeps the move vocabulary (signature/continuity moves)
    without handing the model levels to copy. De-dups on first-seen order (a move
    may appear at both L0 and a level-up row)."""
    if not learnset:
        return "(no level-up learnset)"
    seen: set[str] = set()
    names: list[str] = []
    for entry in learnset:
        move = entry.get("move")
        if move and move not in seen:
            seen.add(move)
            names.append(move)
    return ", ".join(names)


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
        "new ability, and NEVER propose a MOVE. A move is not an ability: names "
        "like 'Nasty Plot', 'Swords Dance', or 'Recover' are MOVES and must never "
        "appear in an ability slot. Every value you emit for a slot must be an "
        "ability that appears verbatim in the ability pool below.\n"
        "FIRST, before scoring anything: state the species' IDENTITY in one clause "
        "— what the creature IS, from its dex flavor, name etymology, real-world "
        "inspiration, and signature traits — and, when the author gave a "
        "direction, what that direction asks the species to become. Everything "
        "below is scored against that identity. A pick that only fits the base "
        "stats is a FAILED pick: the generic stat-shaped default (Sturdy on a "
        "wall, a plain -orb/pinch ability on an attacker) is the answer to reject "
        "unless it genuinely expresses the identity. Prefer the ability that "
        "makes this species play unlike anything else with the same stat line.\n"
        "Abilities tagged [CUSTOM] are bespoke to this game — invented for this "
        "dex, never seen in the base games. Actively weigh them: when a [CUSTOM] "
        "ability fits the identity as well as a canon one, prefer the [CUSTOM] "
        "ability.\n"
        "If NOTHING in the pool expresses the identity, still emit your closest "
        "pick, and say plainly in that slot's rationale that no existing ability "
        "captures it and a bespoke one would fit better — the author can create "
        "one.\n"
        "Score candidates on:\n"
        "- Identity fit (WEIGHTED HIGHEST): the ability reads as this creature's "
        "lore made mechanical, and honors the author's direction.\n"
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
        "per-slot reason in `rationale` — EVERY slot you propose gets its own "
        "reason, and a reason is a sentence explaining the pick, never the "
        "ability name repeated back — and up to three runner-up abilities (each "
        "with a one-line reason) in `alternatives`. Every ability name you emit "
        "must appear verbatim in the ability pool."
    )


def _build_user_context(
    entry: dict[str, Any],
    direction: str | None,
    locked: list[str] | None = None,
    lore_block: str = "",
) -> str:
    """The fresh per-species delta: stats/types/abilities/learnset + direction.

    ``lore_block`` is the researched-lore text when the author asked for it, and
    empty otherwise — an empty block appends nothing, so a lore-off prompt is
    byte-identical to what this returned before lore existed.
    """
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
    # Lore sits BEFORE the constraints and the steer, never last. Appended last
    # it ended the prompt with a page of encyclopedia prose, and the first live
    # run came back degenerate: all three slots echoed back unchanged with the
    # ability's own name as its "rationale". Both injection modes did it — the
    # 1.2k condensed block as readily as the 3k raw one — so it was recency, not
    # length. The task-shaped lines have to be the last thing read.
    if lore_block:
        lines.append(lore_block)
    if locked:
        free = [slot for slot in _ABILITY_SLOTS if slot not in locked]
        lines.append(
            "Locked slots (the author has fixed these — keep their current "
            f"ability, do NOT propose for them): {', '.join(locked)}. "
            f"Propose only for: {', '.join(free) or '(none)'}."
        )
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
    locked: list[str] | None = None,
    lore_mode: str = "off",
    lore_provider: LoreProvider | None = None,
) -> dict[str, Any]:
    """Propose best-fit existing abilities for a species; never writes a file.

    Assembles the rubric + context and runs a bounded Port call. If the model
    names something that is NOT an existing ability (typically a MOVE, e.g.
    'Nasty Plot'), it does ONE automatic self-repair retry, feeding the violation
    back verbatim. Valid slots from BOTH attempts are preserved; any slot still
    invalid after the retry becomes a per-slot ``warnings`` entry (verbatim
    message) rather than nuking the whole proposal. Only when ZERO slots survive
    is it a :class:`SuggestError` (NO PROPOSAL). Returns the reusable
    ``{draft, rationale, alternatives}`` contract, plus ``warnings`` and a
    ``repaired`` count when a repair ran, and always a ``lore`` provenance object
    saying what the lookup did (``{"mode": "off"}`` when it did nothing).
    """
    pool = build_ability_pool(abilities)
    if not pool:
        raise SuggestError("No abilities are available to suggest from.")

    known = _pool_names(pool)
    # Only real slot names count as locks; anything else in the payload is noise.
    locked_slots = [slot for slot in _ABILITY_SLOTS if slot in (locked or [])]
    if len(locked_slots) == len(_ABILITY_SLOTS):
        raise SuggestError("All ability slots are locked — unlock one to propose.")
    injection = build_lore_injection(
        entry=entry,
        lore_mode=lore_mode,
        lore_provider=lore_provider,
        provider=provider,
    )
    system = _with_lore_note(_build_rubric(), injection)
    cached_context = "Ability pool (pick only from these):\n" + _format_pool(pool)
    user = _build_user_context(entry, direction, locked_slots, injection.block)

    def _run(user_text: str) -> dict[str, Any]:
        return provider.propose(
            system=system,
            cached_context=cached_context,
            user=user_text,
            schema=_draft_schema(),
            max_tokens=DEFAULT_MAX_TOKENS,
        )

    result = _run(user)
    valid, invalid = _split_ability_slots(_draft_abilities(result), known)

    repaired = 0
    if invalid:
        # ONE self-repair retry: feed the exact violation back so the model can
        # correct the offending slot(s). No more than one — an unbounded loop on a
        # stubborn model would burn tokens for nothing.
        result = _run(f"{user}\n\n{_ability_repair_note(invalid)}")
        valid_retry, invalid = _split_ability_slots(_draft_abilities(result), known)
        repaired = 1
        # Preserve valid slots from EITHER attempt (the retry wins a conflict), so
        # a good slot from the first pass is not lost if the retry drops it.
        valid = {**valid, **valid_retry}
        invalid = [(slot, value) for slot, value in invalid if slot not in valid]

    # The prompt asks the model to leave locked slots alone; strip them anyway so
    # a stubborn response can never surface a change on a slot the author fixed.
    valid = {slot: value for slot, value in valid.items() if slot not in locked_slots}
    invalid = [(slot, value) for slot, value in invalid if slot not in locked_slots]

    warnings = [_ability_slot_warning(slot, value) for slot, value in invalid]

    if not valid:
        # Nothing survived even after the repair — an honest NO PROPOSAL.
        raise SuggestError(
            warnings[0] if warnings else "The suggestion did not propose any ability."
        )

    return {
        **_build_ability_response(result, valid, known, warnings, repaired),
        "lore": dict(injection.provenance),
    }


def _draft_abilities(result: Any) -> dict[str, Any]:
    """The draft.abilities object, or a `SuggestError` on a malformed response."""
    if not isinstance(result, dict):
        raise SuggestError("The suggestion came back in an unexpected shape.")
    draft = result.get("draft")
    if not isinstance(draft, dict) or not isinstance(draft.get("abilities"), dict):
        raise SuggestError("The suggestion was missing a draft abilities object.")
    return draft["abilities"]


def _split_ability_slots(
    abilities: dict[str, Any], known: set[str]
) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Partition proposed slots into (valid pool members, invalid name pairs)."""
    valid: dict[str, str] = {}
    invalid: list[tuple[str, str]] = []
    for slot, value in abilities.items():
        if slot not in _ABILITY_SLOTS or not value:
            continue
        if value.strip().casefold() in known:
            valid[slot] = value
        else:
            invalid.append((slot, value))
    return valid, invalid


def _ability_slot_warning(slot: str, value: str) -> str:
    """The verbatim per-slot rejection message (unchanged wording, now a warning)."""
    return (
        f"The suggested ability {value!r} for the {slot} slot is not an existing "
        "ability; only existing abilities can be suggested."
    )


def _ability_repair_note(invalid: list[tuple[str, str]]) -> str:
    """The correction fed back to the model on the one self-repair retry."""
    lines = ["Your previous answer named things that are NOT existing abilities:"]
    for slot, value in invalid:
        lines.append(
            f"- {value!r} for the {slot} slot (this is likely a MOVE or an invented "
            "name, not an ability)."
        )
    lines.append(
        "Re-propose using ONLY ability names that appear verbatim in the ability "
        "pool. Do not propose any move."
    )
    return "\n".join(lines)


def _build_ability_response(
    result: dict[str, Any],
    valid: dict[str, str],
    known: set[str],
    warnings: list[str],
    repaired: int,
) -> dict[str, Any]:
    """Assemble the contract from the surviving valid slots + filtered extras."""
    alternatives = []
    for alt in result.get("alternatives") or []:
        if not isinstance(alt, dict):
            continue
        value = alt.get("value")
        if not value or value.strip().casefold() not in known:
            # Drop a hallucinated alternative; the primary draft is load-bearing.
            continue
        alternatives.append({"value": value, "rationale": alt.get("rationale", "")})

    rationale = {
        slot: text
        for slot, text in _rationale_map(result, "ability").items()
        if slot in valid and isinstance(text, str)
    }

    response: dict[str, Any] = {
        "draft": {"abilities": valid},
        "rationale": rationale,
        "alternatives": alternatives,
    }
    if warnings:
        response["warnings"] = warnings
    if repaired:
        response["repaired"] = repaired
    return response


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


def _build_typing_user_context(
    entry: dict[str, Any], direction: str | None, lore_block: str = ""
) -> str:
    """The fresh per-species delta for typing suggest: stats/current types/learnset.

    ``lore_block`` carries researched lore when the author asked for it. Empty
    appends nothing, so a lore-off prompt is byte-identical to the old one.
    """
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
    # Lore before the steer, for the reason spelled out in _build_user_context:
    # ending the prompt with encyclopedia prose degenerates the answer.
    if lore_block:
        lines.append(lore_block)
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
    return propose_with_repair(
        provider=provider,
        system=_build_typing_rubric(),
        cached_context=cached_context,
        user=_build_typing_user_context(entry, direction),
        schema=_typing_draft_schema(),
        max_tokens=DEFAULT_MAX_TOKENS,
        validate=lambda draft: _validate_typing_result(draft, type_pool),
    )


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

    rationale_text = _rationale_map(result, "types").get("types")
    rationale = {"types": rationale_text} if isinstance(rationale_text, str) else {}

    return {
        "draft": {"types": proposed},
        "rationale": rationale,
        "alternatives": alternatives,
    }


# =========================================================================== #
# Lore options — the makeover opening move: 2-3 lore-grounded typing+role
# directions to pick from (species-suggest Seam, a `mode` on the typing endpoint,
# NOT a second prompt path). Same assemble → call → validate → return contract,
# returning `draft.options` instead of a single `draft.types`.
# =========================================================================== #


def _build_lore_options_rubric(
    kept_types: list[str] | None = None,
    kept_abilities: dict[str, Any] | None = None,
) -> str:
    """The lore-options system rubric (the makeover opening move, server-side).

    Directs the model to research the species' flavor — dex text, name etymology,
    real-world inspiration, signature traits — and propose 2-3 DISTINCT makeover
    directions, each a typing (1-2 pool types) plus a short battle-role label,
    grounded in that lore. Mirrors the "Makeover opening move" in the
    species-suggest skill so chat and UI share one prompt path (One Seam).

    À la carte KEPT facets constrain the options: a KEPT typing is fixed (every
    option keeps it verbatim and differentiates by role), and KEPT abilities must
    not be the axis an option hinges on.
    """
    base = (
        "You are a Pokémon game-design assistant helping brainstorm a species "
        "makeover. Given one species and the full type pool, research the "
        "species' lore — its dex flavor, name etymology, real-world inspiration, "
        "and signature traits — then propose 2 to 3 DISTINCT makeover directions. "
        "Each direction names a typing (1 or 2 types) and a short battle ROLE "
        "label (e.g. 'physical wall', 'fast special attacker', 'trapper'), "
        "grounded in that lore. You MUST pick types only from the provided type "
        "pool — never invent a type. Keep the directions meaningfully different "
        "from each other. Each direction ALSO names `flavor_types`: 0-2 pool "
        "types that fit what the creature IS and become its coverage moves — "
        "e.g. Goodra-Hisui the Dragon/Steel SLUG gets Water and Poison flavor. "
        "Flavor comes from the body and lore, NEVER from patching the typing's "
        "weaknesses; leave it empty when nothing fits naturally. Return the "
        "directions in `draft.options` (each {types: [1-2 pool types], role: "
        "short label, flavor_types: [0-2 pool types], rationale: one line of "
        "why this fits the lore}), and a one-line framing in `rationale.options`."
    )
    constraints = []
    if kept_types:
        joined = "/".join(kept_types)
        constraints.append(
            f"HARD CONSTRAINT — the typing is KEPT and FIXED at {joined}. EVERY "
            f"option MUST use exactly this typing ([{', '.join(kept_types)}]) "
            "verbatim; do NOT change or add a type. Differentiate the options by "
            "battle ROLE and identity WITHIN this typing (e.g. physical "
            "wallbreaker vs bulky trapper vs speed-crept bruiser), not by type."
        )
    if kept_abilities:
        constraints.append(
            "HARD CONSTRAINT — the abilities are KEPT. Do NOT propose options that "
            "hinge on a new or changed ability; the role must work with the "
            "current abilities."
        )
    if constraints:
        return base + "\n" + "\n".join(constraints)
    return base


def _lore_options_draft_schema() -> dict[str, Any]:
    """The JSON schema the lore-options draft is forced to match.

    A list of {types, role, rationale} options. The Port forces this shape so the
    draft is structurally valid before the pool check.
    """
    return {
        "type": "object",
        "properties": {
            "draft": {
                "type": "object",
                "properties": {
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "types": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "minItems": 1,
                                    "maxItems": 2,
                                },
                                "role": {"type": "string"},
                                "flavor_types": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "maxItems": 2,
                                },
                                "rationale": {"type": "string"},
                            },
                            "required": ["types", "role", "rationale"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["options"],
                "additionalProperties": False,
            },
            "rationale": {
                "type": "object",
                "properties": {"options": {"type": "string"}},
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
        "required": ["draft", "rationale"],
        "additionalProperties": False,
    }


def suggest_lore_options(
    *,
    provider: LlmProvider,
    entry: dict[str, Any],
    type_pool: list[str],
    direction: str | None = None,
    kept_types: list[str] | None = None,
    kept_abilities: dict[str, Any] | None = None,
    lore_mode: str = "off",
    lore_provider: LoreProvider | None = None,
) -> dict[str, Any]:
    """Propose 2-3 lore-grounded typing+role makeover directions; never writes.

    Assembles the same species context as typing suggest, runs a bounded Port call
    (with one self-repair retry via :func:`propose_with_repair`), then validates
    each option's types against the real pool — a hallucinated type DROPS that
    option. À la carte KEPT facets constrain the options: a KEPT typing forces
    every option to keep the current typing verbatim (options differ by role), and
    an option that changes a kept facet is dropped. Returns ``{draft: {options:
    [...]}, rationale, alternatives}``, plus a ``lore`` provenance object.

    This capability's whole premise is the creature's lore, so it is the surface
    where researched sources matter most — but the fetch is still opt-in, and off
    leaves the prompt exactly as it was.
    """
    if not type_pool:
        raise SuggestError("No types are available to suggest from.")

    injection = build_lore_injection(
        entry=entry,
        lore_mode=lore_mode,
        lore_provider=lore_provider,
        provider=provider,
    )
    cached_context = "Type pool (pick only from these):\n" + _format_type_pool(type_pool)
    return {
        **propose_with_repair(
            provider=provider,
            system=_with_lore_note(
                _build_lore_options_rubric(kept_types, kept_abilities), injection
            ),
            cached_context=cached_context,
            user=_build_typing_user_context(entry, direction, injection.block),
            schema=_lore_options_draft_schema(),
            max_tokens=DEFAULT_MAX_TOKENS,
            validate=lambda draft: _validate_lore_options_result(
                draft, type_pool, kept_types=kept_types
            ),
        ),
        "lore": dict(injection.provenance),
    }


def _validate_lore_options_result(
    result: dict[str, Any],
    type_pool: list[str],
    kept_types: list[str] | None = None,
) -> dict[str, Any]:
    """Shape-, pool-, and kept-facet check on the lore-options draft (never trusted).

    Keeps only options whose every type is a real pool member (a hallucinated type
    drops that one option). When ``kept_types`` is set, an option whose typing
    differs from the kept typing is ALSO dropped, and at least TWO options must
    survive (fewer → a :class:`SuggestError` naming the violation, which
    :func:`propose_with_repair` retries once before failing honestly). Otherwise at
    least one option must survive. Returns the reusable envelope.
    """
    if not isinstance(result, dict):
        raise SuggestError("The suggestion came back in an unexpected shape.")

    draft = result.get("draft")
    if not isinstance(draft, dict) or not isinstance(draft.get("options"), list):
        raise SuggestError("The suggestion was missing a draft options list.")

    known = {t.strip().casefold() for t in type_pool}
    kept_key = {t.strip().casefold() for t in kept_types} if kept_types else None
    options: list[dict[str, Any]] = []
    for opt in draft["options"]:
        if not isinstance(opt, dict):
            continue
        raw_types = opt.get("types")
        if not isinstance(raw_types, list):
            continue
        types = [t for t in raw_types if isinstance(t, str) and t.strip()]
        if not types or len(types) > 2:
            continue
        if any(t.strip().casefold() not in known for t in types):
            # Drop an option with a hallucinated type rather than failing the run.
            continue
        if kept_key is not None and {t.strip().casefold() for t in types} != kept_key:
            # A KEPT typing was violated — drop this option (the retry names it).
            continue
        # Flavor coverage types: pool-checked like the typing, but forgiving —
        # a bad flavor type is dropped alone, never the whole option. Types
        # already in the option's typing are redundant as flavor and dropped.
        raw_flavor = opt.get("flavor_types")
        type_key = {t.strip().casefold() for t in types}
        flavor = [
            t.strip() for t in (raw_flavor if isinstance(raw_flavor, list) else [])
            if isinstance(t, str)
            and t.strip().casefold() in known
            and t.strip().casefold() not in type_key
        ][:2]
        options.append(
            {
                "types": list(kept_types) if kept_types else types,
                "role": str(opt.get("role", "")).strip(),
                "flavor_types": flavor,
                "rationale": str(opt.get("rationale", "")).strip(),
            }
        )

    if kept_types is not None and len(options) < 2:
        raise SuggestError(
            f"Fewer than 2 options kept the fixed typing {'/'.join(kept_types)}; "
            "every option must keep the current typing and differ only by role."
        )
    if not options:
        raise SuggestError("The suggestion did not propose any valid direction.")

    rationale_text = _rationale_map(result, "options").get("options")
    rationale = {"options": rationale_text} if isinstance(rationale_text, str) else {}

    return {"draft": {"options": options}, "rationale": rationale, "alternatives": []}


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
    return propose_with_repair(
        provider=provider,
        system=_build_stats_rubric(),
        cached_context=(
            f"Valid stat keys: {', '.join(_STAT_KEYS)}. "
            "All values must be integers in the range [1, 255]."
        ),
        user=_build_stats_user_context(entry, direction),
        schema=_stats_draft_schema(),
        max_tokens=DEFAULT_MAX_TOKENS,
        validate=_validate_stats_result,
    )


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

    rationale_text = _rationale_map(result, "stats").get("stats")
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

    Also states the learnset shape bounds (size range, level ceiling, early-level
    caps — the ``LEARNSET_*`` constants) so drafts land inside them on the first
    try; ``_validate_learnset_result`` is the enforcement gate.
    """
    return (
        "You are a Pokémon game-design assistant. Given one species and the full "
        "move pool, design a complete level-up learnset. Each row is "
        "{level, move, reasoning}. Level 0 means 'learned on evolution'. "
        "You MUST pick only moves from the provided move pool — never invent a "
        "move name. In FULL mode a SLOT SKELETON is provided below: the levels "
        "and the allowed moves per slot are FIXED — emit EXACTLY one row per "
        "slot, at the slot's stated level, choosing from that slot's allowed "
        "moves. Your judgment lives in WHICH allowed move each slot gets and in "
        "the reasoning. Design the learnset to:\n"
        "- Provide STAB on the species' types wherever possible.\n"
        "- Match move category to the base stats — this is a HARD rule, not a "
        "lean. If Atk > SpA the attacking moves must be predominantly PHYSICAL; if "
        "SpA > Atk they must be predominantly SPECIAL; only a genuine tie is a "
        "mix. Never load a special attacker with physical attacks (or vice versa) "
        "— use the off-stat category solely for coverage the on-stat movepool "
        "lacks. A loud OFFENSIVE BIAS line below states the species' side; obey "
        "it, and it governs ability-fuel moves too.\n"
        "- Treat the species' ability descriptions (provided below) as DESIGN "
        "CONSTRAINTS, not flavor. For EACH ability, work out which moves it "
        "rewards or requires and deliberately bias the learnset toward them. The "
        "reasoning generalizes — reason from the actual description text, these "
        "are only examples: a Normal-conversion ability (turns Normal moves into "
        "another type) NEEDS Normal-type attacking moves or it does nothing; a "
        "punch/bite/kick booster wants those moves; Sheer Force wants moves with "
        "secondary effects; an ability that rewards using status moves wants good "
        "status moves; an ability that cancels a move's drawback (e.g. accuracy) "
        "makes that move worth teaching. A loud ABILITY-DRIVEN MOVE REQUIREMENT "
        "line may appear below with an exact candidate shortlist — obey it.\n"
        "- Maintain a sensible level progression: weaker/basic moves early, "
        "stronger/signature moves late.\n"
        f"- Size: {LEARNSET_SIZE_MIN}–{LEARNSET_SIZE_MAX} rows total "
        f"(aim for about {(LEARNSET_SIZE_MIN + LEARNSET_SIZE_MAX) // 2}).\n"
        f"- No move may be learned above level {LEARNSET_MAX_LEVEL}.\n"
        f"- Keep early levels lean: at most {LEARNSET_MAX_MOVES_THROUGH_L5} rows "
        f"at level 5 or below (counting the L0/L1 starting kit) and at most "
        f"{LEARNSET_MAX_MOVES_THROUGH_L10} at level 10 or below.\n"
        "- Moves tagged [CUSTOM] are bespoke to this game — invented for this "
        "dex, never seen in the base games. Actively weigh them: when a [CUSTOM] "
        "move fits the species' type, stats, or identity as well as a canon "
        "pick, prefer the [CUSTOM] move. They are especially strong candidates "
        "for the L0 evolution reward and late signature slots. Judge them by "
        "their listed type/category/power/effect, not familiarity.\n"
        f"- Pace attacking-move power to the level bands: {_format_pacing_bands()}. "
        "L0 rows (on-evolution rewards) and status moves are exempt.\n"
        "- For evolved forms (when 'Evolved from' is shown): place an "
        "evolution-reward move at level 0 ('learned on evolution').\n"
        "- For pre-evolutionary forms (when 'Evolves into' at a specific level is "
        "shown): place a reward move near that evo level.\n"
        "- The L0 reward is learned AT the evolution level — count it as that "
        "level's ramp step when judging a ladder's pacing (a type whose L0 "
        "reward covers a band needs no duplicate rung there).\n"
        "- When the user's direction names specific moves, those exact moves "
        "are the mandate — place them in fitting slots; never substitute "
        "generic coverage of their types.\n"
        "- In SURGICAL mode: change ONLY what the instruction names. Return the "
        "FULL learnset with every other row byte-identical to the current learnset. "
        "Do not reorder, rename, or adjust any row not targeted by the instruction.\n"
        "Emit the full learnset in `draft.learnset`, a rationale string explaining "
        "the overall design in `rationale.learnset`, and up to three alternative "
        "move suggestions (each as a short 'Move @ Lvel — reason' string) in "
        "`alternatives`. Every move name you emit must appear in the move pool."
    )


def _format_move_pool(pool: list[dict[str, Any]]) -> str:
    """Render the move pool as a compact, cache-stable text block.

    Net-new created moves get a ``[CUSTOM]`` tag — the model has no training
    prior pulling toward them (canon learnsets dominate what it "knows"), so
    without the tag they read as noise among ~900 canon names and go unpicked.
    """
    lines = []
    for row in pool:
        pwr = f" {row['power']}bp" if row.get("power") is not None else ""
        eff = learnset_skeleton.effective_power(row)
        if isinstance(eff, int) and eff != row.get("power"):
            pwr = f" {row['power']}bp (≈{eff}bp across hits)"
        tag = " [CUSTOM]" if row.get("custom") else ""
        lines.append(
            f"- {row['move']} ({row['type']} {row['category']}{pwr}; {row['effect']})"
            f"{tag}"
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


# Ability→move synergy. The GENERAL engine is the rubric, which makes the model
# reason move-relevance from each ability's description (all of them are already
# in the prompt). This table is only the extra push for cases where the pool can
# be QUERIED by a rock-solid STRUCTURED filter — no per-ability name-hacking — so
# the model gets a concrete candidate shortlist, not just a nudge. Append a row
# to cover a new case; never a bespoke detector per ability.
#
# Each rule: a description regex, and a builder(name, match, pool) → directive.
# The -ate case is the only HARD requirement (the ability is null without Normal
# moves); the rest are "lean toward". Everything not in this table is still
# handled — by the model reasoning over the description, per the rubric.
_ATE_RE = re.compile(
    r"normal(?:-type)? moves become (?:the )?([A-Za-z]+)", re.IGNORECASE
)
_STATUS_SYNERGY_RE = re.compile(r"status move", re.IGNORECASE)

# How many ability-relevant candidate moves to surface. Enough to choose from,
# few enough to stay a nudge rather than a second pool dump.
_ABILITY_SHORTLIST_SIZE = 10

# Shortlist power ceiling: a proxy to keep gimmick nukes (Explosion 250, Z-moves,
# Hyper/Giga Impact) out of the "strong attacker" shortlist — the pool rows carry
# no self-KO/recharge/Z flag to filter on directly. Boomburst (140) still makes
# it; nothing above is a real level-up teach. ponytail: power proxy, swap for a
# real eligibility flag if the pool ever carries move flags.
_SHORTLIST_POWER_CEILING = 140

# Signature / species-locked moves kept OUT of the candidate shortlist — the
# set now lives in learnset_skeleton (the slot builder excludes them too);
# this alias keeps the existing call sites.
_SIGNATURE_MOVES = learnset_skeleton.SIGNATURE_MOVES


# Compares Atk vs SpA; a tie (or missing stats) is mixed. Drives the -ate fuel
# category, the loud offensive-bias line, and the skeleton's on_stat filters —
# one implementation, shared with the slot builder.
_offensive_bias = learnset_skeleton.offensive_bias


def _ate_directive(
    name: str, match: re.Match[str], pool: list[dict[str, Any]], stats: dict[str, Any]
) -> str:
    converted = match.group(1).capitalize()
    bias = _offensive_bias(stats)
    # A special attacker's Normal fuel must be SPECIAL Normal moves (Boomburst,
    # Hyper Voice), not physical (Double-Edge) — that mismatch is exactly the bug
    # this fixes. Mixed → offer both.
    cat_word = f"{bias.upper()} " if bias else ""
    shortlist = _shortlist(pool, move_type="Normal", category=bias, attacking=True)
    candidates = (
        f" Strong {cat_word}Normal-type attackers in the pool: {shortlist}."
        if shortlist
        else ""
    )
    return (
        f"{name} converts this species' Normal-type moves into {converted}-type "
        f"with a power boost. You MUST include at least 2-3 strong {cat_word}"
        f"Normal-type ATTACKING moves — the ability is dead weight otherwise. They "
        f"function as boosted {converted}-type STAB, so treat them as primary "
        f"offense, not filler.{candidates}"
    )


def _status_synergy_directive(
    name: str, _match: re.Match[str], pool: list[dict[str, Any]], _stats: dict[str, Any]
) -> str:
    shortlist = _shortlist(pool, category="status")
    candidates = f" Status moves in the pool: {shortlist}." if shortlist else ""
    return (
        f"{name} rewards using STATUS moves (see its effect). Lean the learnset "
        f"toward several useful status moves so the ability pays off.{candidates}"
    )


# (pattern, builder). Ordered; a builder fires once per matching ability.
# builder(name, match, pool, stats) → directive.
_SYNERGY_RULES: tuple[tuple[re.Pattern[str], Any], ...] = (
    (_ATE_RE, _ate_directive),
    (_STATUS_SYNERGY_RE, _status_synergy_directive),
)


def _ability_move_requirements(
    ability_slots: dict[str, Any],
    all_abilities: list[dict[str, Any]],
    move_pool: list[dict[str, Any]],
    stats: dict[str, Any],
) -> str:
    """Per-species move directives implied by the species' abilities.

    Runs the structured-filter synergy table over each ability's description and
    QUERIES the move pool for relevant candidates — the in-process relevance
    lookup, no agentic tool round-trip. Candidate shortlists honor the species'
    offensive bias (a special attacker gets special fuel). Returns a directive
    string, or "" when no tabled ability applies (the rubric still drives general
    per-ability reasoning).
    """
    ability_by_name: dict[str, str] = {
        entry["name"].strip().casefold(): entry.get("description", "")
        for entry in all_abilities
        if entry.get("name")
    }
    directives: list[str] = []
    for slot in _ABILITY_SLOTS:
        name = ability_slots.get(slot)
        if not name:
            continue
        desc = ability_by_name.get(name.strip().casefold(), "")
        for pattern, builder in _SYNERGY_RULES:
            match = pattern.search(desc)
            if match:
                directives.append(builder(name, match, move_pool, stats))
    return " ".join(directives)


def _shortlist(
    move_pool: list[dict[str, Any]],
    *,
    move_type: str | None = None,
    category: str | None = None,
    attacking: bool = False,
) -> str:
    """Matching pool moves as a compact list — the ability-relevance query.

    Filters the already-loaded pool by structured fields only (type, category).
    Attacking matches sort by power and show ``Name (Npbp)``; status matches keep
    pool (name) order and show just the name. Capped at ``_ABILITY_SHORTLIST_SIZE``.
    """
    def keep(row: dict[str, Any]) -> bool:
        cat = (row.get("category") or "").casefold()
        if (row.get("move") or "").strip().casefold() in _SIGNATURE_MOVES:
            return False
        if move_type is not None and (row.get("type") or "").casefold() != move_type.casefold():
            return False
        if category is not None and cat != category.casefold():
            return False
        if attacking and cat == "status":
            return False
        return True

    matches = [row for row in move_pool if keep(row)]
    if attacking:
        matches = [
            r for r in matches
            if isinstance(r.get("power"), int)
            and 1 < r["power"] <= _SHORTLIST_POWER_CEILING
        ]
        matches.sort(key=lambda r: r["power"], reverse=True)
        top = matches[:_ABILITY_SHORTLIST_SIZE]
        return ", ".join(f"{r['move']} ({r['power']}bp)" for r in top)
    top = matches[:_ABILITY_SHORTLIST_SIZE]
    return ", ".join(r["move"] for r in top)


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
    move_pool: list[dict[str, Any]],
    mode: str,
    instruction: str | None,
    direction: str | None,
    anchors: list[str] | None = None,
) -> str:
    """The fresh per-species delta for learnset suggest.

    Extends `_build_user_context` with ability-effect text + evo context (D3).
    The ability descriptions come from the merged abilities pool so a Ruleset
    retune of an ability shifts move picks (not names-only like the base context).
    When an ability imposes a hard move requirement (an -ate conversion), a loud
    per-species directive plus a pool-queried candidate shortlist is added on its
    own line so the model can't skim past it.
    """
    stats = entry.get("stats", {})
    stat_line = " ".join(
        f"{key.upper()} {stats[key]}" for key in _STAT_KEYS if key in stats
    ) or "(unknown)"
    ability_slots = entry.get("abilities", {})
    current_learnset = entry.get("learnset", [])
    # FULL mode is a redesign: by this stage the entry already carries the NEW
    # typing/stats/abilities (locked in earlier), so the OLD learnset is stale —
    # showing its exact level placement just anchors the model into copying it and
    # inheriting its early-level packing (the reported symptom). Present the moves
    # as prior-art names only, pacing to be rebuilt fresh under the caps. Surgical
    # mode edits in place, so it MUST see the exact L<level> rows.
    if mode == "full":
        learnset_line = (
            "Current learnset (PRIOR ART — the moves this line has historically "
            "learned, NOT a template. Rebuild the LEVEL PACING from scratch under "
            "the size and early-level caps above; do NOT copy the current level "
            "placement, which may over-pack the early levels): "
            f"{_format_move_names(current_learnset)}"
        )
    else:
        learnset_line = f"Current learnset: {_format_learnset(current_learnset)}"
    lines = [
        f"Species: {entry.get('name', entry['chrooked_id'])}",
        f"Types: {', '.join(entry.get('types', [])) or '(unknown)'}",
        f"Base stats: {stat_line}",
        f"Current abilities (with effects): "
        f"{_format_abilities_with_effects(ability_slots, all_abilities)}",
        learnset_line,
        f"Evolution: {_format_evo_context(entry)}",
        f"Mode: {mode.upper()}",
    ]
    bias = _offensive_bias(stats)
    if bias:
        atk, spa = stats.get("atk"), stats.get("spa")
        lines.append(
            f"OFFENSIVE BIAS: {'SpA' if bias == 'special' else 'Atk'} "
            f"({spa if bias == 'special' else atk}) exceeds "
            f"{'Atk' if bias == 'special' else 'SpA'} "
            f"({atk if bias == 'special' else spa}) — its ATTACKING moves must be "
            f"predominantly {bias.upper()}. Use the off-stat category only for "
            f"coverage the {bias} movepool genuinely lacks."
        )
    requirements = _ability_move_requirements(
        ability_slots, all_abilities, move_pool, stats
    )
    if requirements:
        lines.append(f"ABILITY-DRIVEN MOVE REQUIREMENT: {requirements}")
    if instruction and instruction.strip():
        lines.append(f"Surgical instruction: {instruction.strip()}")
    if direction and direction.strip():
        lines.append(f"Direction from the user: {direction.strip()}")
    # Last line in the block, so it abuts the SLOT SKELETON appended after this
    # context — it reads as the bridge into the ANCHOR slots rather than as one
    # more clause the direction prose can swallow.
    if anchors:
        lines.append(
            "MOVES THE USER NAMED (non-negotiable): "
            + ", ".join(anchors)
            + " — each has its own ANCHOR slot in the skeleton below. "
            "Place every one."
        )
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


def _resolve_anchors(
    anchors: list[str] | None,
    move_pool: list[dict[str, Any]],
    mode: str,
) -> list[str]:
    """Canonicalize and bound the user's anchor moves, or raise.

    Every failure here is a :class:`SuggestError` without salvage, which the
    route turns into a 422 — and every one is raised before the Port call, so a
    bad request never costs a round-trip.
    """
    if not anchors:
        return []
    if mode != "full":
        raise SuggestError(
            "Anchor moves are a full-mode field; in surgical mode name the "
            "move in the instruction instead."
        )
    known = _pool_move_names(move_pool)
    resolved: list[str] = []
    for raw in anchors:
        name = str(raw).strip()
        canon = known.get(name.casefold()) if name else None
        if canon is None:
            raise SuggestError(
                f"Anchor move {name!r} is not in this species' move pool."
            )
        if canon not in resolved:
            resolved.append(canon)
    if len(resolved) > LEARNSET_ANCHOR_MAX:
        raise SuggestError(
            f"{len(resolved)} anchor moves is more than the {LEARNSET_ANCHOR_MAX} "
            "the slot skeleton can seat without erasing the generated ladder — "
            "keep the most important ones and put the rest in the direction."
        )
    return resolved


def _validate_learnset_result(
    result: dict[str, Any],
    move_pool: list[dict[str, Any]],
    *,
    mode: str,
    current_learnset: list[dict[str, Any]],
    instruction: str | None = None,
    skeleton: dict[str, Any] | None = None,
    anchors: list[str] | None = None,
) -> dict[str, Any]:
    """Shape, pool, level, and repeat-move checks on the learnset draft.

    Steps (in order):
    1. Shape: result must carry the contract keys and a non-empty learnset list.
    2. Pool (AC3): every `move` in the draft must exist in the merged move pool
       (case-insensitive); a miss is a SuggestError. Normalize to canonical name.
    3. Level (AC5/D4): each level must be an int in [0, LEARNSET_MAX_LEVEL] in
       full mode ([0, 100] in surgical mode — base learnsets legitimately exceed
       the ceiling and untouched rows must survive).
    4. Repeat-move B rule (AC5/D4): a move may appear at most once at a non-zero
       level, and optionally once at L0. Two non-zero levels, >2 rows, or a
       duplicated L0 are rejected.
    5. Dedup exact (level, move) pairs silently.
    6. Sort by (level, name) — normalizes storage order.
    7. Shape bounds (full mode only): row count inside
       [min(LEARNSET_SIZE_MIN, pool size), LEARNSET_SIZE_MAX] and the early-level
       packing caps (LEARNSET_MAX_MOVES_THROUGH_L5/_L10). Not deterministically
       repairable (no principled way to invent or cut rows), so a violation
       raises and rides the eager retry loop. Plus the ADVISORY pacing check:
       an attacking move over its level band's BP cap (shared band Contract,
       learnset_rubric.json) warns — never rejects.
    8. Surgical untouched-rows guard (AC2/D1): every (level, move) row NOT
       implicated by the instruction must be byte-identical to current_learnset.
    9. Alternatives: drop hallucinated move names; keep valid ones.

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

    # Chris's ruling: learnset suggestion is especially risk-tolerant. Mechanical
    # defects the server can fix deterministically (unknown-move rows, duplicate
    # levels) are REPAIRED with a visible warning, not rejected — a repair costs
    # no retry. Only a draft too broken to salvage (empty, or below the row floor
    # after dropping junk) raises a SuggestError, which the eager retry loop feeds
    # back to the model.
    warnings: list[str] = []

    # Step 2+3: pool check + level range + normalize move name. A row whose move
    # isn't in the pool, or whose level is malformed, is DROPPED with a warning
    # (rather than sinking the whole draft) as long as the list stays viable.
    max_level = LEARNSET_MAX_LEVEL if mode == "full" else 100
    validated_rows: list[dict[str, Any]] = []
    for row in raw_rows:
        if not isinstance(row, dict):
            warnings.append("dropped a learnset row that was not an object")
            continue
        move_raw = row.get("move")
        if not isinstance(move_raw, str) or not move_raw.strip():
            warnings.append("dropped a learnset row with no move name")
            continue
        canonical = known_moves.get(move_raw.strip().casefold())
        if canonical is None:
            warnings.append(
                f"dropped {move_raw.strip()!r} — not a known move in the pool"
            )
            continue
        level = row.get("level")
        if not isinstance(level, int) or isinstance(level, bool):
            warnings.append(
                f"dropped {canonical} — its level {level!r} was not an integer"
            )
            continue
        if not (0 <= level <= max_level):
            warnings.append(
                f"dropped {canonical} — its level {level} is outside [0, {max_level}]"
            )
            continue
        validated_rows.append(
            {
                "level": level,
                "move": canonical,
                "reasoning": str(row.get("reasoning", "")),
            }
        )

    # If dropping junk left nothing, the draft was unusable — raise (retryable),
    # don't return an empty learnset. A short-but-nonempty list is respected; its
    # warnings make the drops visible and the user can retry or accept.
    if not validated_rows:
        raise SuggestError(
            "No usable learnset rows survived validation; every proposed row was "
            "dropped (unknown move or invalid level)."
        )

    # Step 4: repeat-move rule — repair, don't reject. Dedupe exact (level, move)
    # pairs, then for each move keep at most one non-zero level (the LOWEST) plus
    # at most one L0, dropping the rest with a warning.
    seen_pairs: set[tuple[int, str]] = set()
    deduped: list[dict[str, Any]] = []
    for row in validated_rows:
        pair = (row["level"], row["move"])
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            deduped.append(row)

    kept_nonzero: dict[str, int] = {}
    kept_zero: set[str] = set()
    repaired: list[dict[str, Any]] = []
    for row in sorted(deduped, key=lambda r: (r["level"], r["move"])):
        move_name = row["move"]
        if row["level"] == 0:
            if move_name in kept_zero:
                warnings.append(f"dropped duplicate {move_name} @L0")
                continue
            kept_zero.add(move_name)
        else:
            if move_name in kept_nonzero:
                warnings.append(
                    f"dropped duplicate {move_name} @{row['level']} "
                    f"— kept @{kept_nonzero[move_name]}"
                )
                continue
            kept_nonzero[move_name] = row["level"]
        repaired.append(row)
    deduped = repaired

    # Step 6: sort by (level, move name).
    deduped.sort(key=lambda r: (r["level"], r["move"]))

    # Step 6.5: the SLOT SKELETON gate (full mode with a skeleton). Every slot
    # must be filled at its level from its candidate list — a band or fuel
    # violation is a HARD retryable failure here, never an advisory warning.
    if mode == "full" and skeleton is not None:
        slot_errors = learnset_skeleton.validate_against_skeleton(deduped, skeleton)
        if slot_errors:
            raise _flagged_learnset(
                "The draft does not fill the slot skeleton: "
                + " | ".join(slot_errors)
                + " — re-emit the learnset with EXACTLY one row per skeleton "
                "slot, at the stated level, from that slot's allowed moves.",
                deduped,
                result,
                warnings,
            )

    # Step 6.6: the dropped-anchor diff. Warn-only by design — the skeleton
    # already makes an anchor a hard requirement, so this is the backstop for the
    # paths where no skeleton ran or a slot could not be seated. Reads `deduped`
    # so the names are already canonicalized to the pool's casing.
    if anchors:
        placed = {row["move"].casefold() for row in deduped}
        for anchor in anchors:
            if anchor.casefold() not in placed:
                warnings.append(
                    f"anchor: {anchor} is not in the proposed learnset — "
                    "the draft dropped a move you named"
                )

    # Step 7: shape bounds, full mode only. Skipped when a skeleton ran — the
    # skeleton fixes the exact row count and levels by construction, and a
    # small-pool skeleton may legitimately sit under the generic size floor.
    if mode == "full" and skeleton is None:
        size_min = min(LEARNSET_SIZE_MIN, len(move_pool))
        count = len(deduped)
        if not (size_min <= count <= LEARNSET_SIZE_MAX):
            # The rows are fully normalized — only the size bound failed, so the
            # draft is still editable. Carry it as salvage for hand-editing.
            raise _flagged_learnset(
                f"The learnset has {count} rows after validation; propose "
                f"between {size_min} and {LEARNSET_SIZE_MAX}.",
                deduped,
                result,
                warnings,
            )
        early_caps = (
            (5, LEARNSET_MAX_MOVES_THROUGH_L5),
            (10, LEARNSET_MAX_MOVES_THROUGH_L10),
        )
        for cutoff, cap in early_caps:
            early = sum(1 for row in deduped if row["level"] <= cutoff)
            if early > cap:
                raise _flagged_learnset(
                    f"{early} moves are learned at level {cutoff} or below; at "
                    f"most {cap} are allowed — move the rest to later levels.",
                    deduped,
                    result,
                    warnings,
                )

        # Pacing check (ADVISORY — mirrors the workbench Signifier, never a
        # rejection: 32% of curated attack rows sit over these caps, so a hard
        # fail would fight Chris's own practice). An attacking move whose BP
        # exceeds its level band's cap gets a visible warning.
        # Effective power (multi-hit = BP × avg hits) so a Bullet Seed-class
        # mover is judged by what it actually deals, not its per-hit BP.
        power_by_move = {
            row["move"]: learnset_skeleton.effective_power(row)
            for row in move_pool
        }
        bands = _pacing_bands()
        for row in deduped:
            if row["level"] == 0:
                continue
            power = power_by_move.get(row["move"])
            if not isinstance(power, int) or power <= 1:
                continue
            band = next(
                (
                    b for b in bands
                    if b["level_min"] <= row["level"] <= b["level_max"]
                ),
                None,
            )
            band_cap = band.get("bp_max") if band else None
            if band_cap is not None and power > band_cap:
                warnings.append(
                    f"pacing: {row['move']} @L{row['level']} is {power}bp — "
                    f"over that level band's {band['label']} cap"
                )

    # Step 8: surgical untouched-rows guard.
    if mode == "surgical":
        _check_untouched_rows(deduped, current_learnset, instruction)

    # Step 9: assemble the reusable contract from the normalized rows.
    return _assemble_learnset_contract(deduped, result, warnings)


def _assemble_learnset_contract(
    deduped: list[dict[str, Any]],
    result: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """The ``{draft, rationale, alternatives, warnings?}`` contract from the
    already-normalized rows. Shared by the success return and the salvage payload
    a shape-bound failure carries, so a flagged-but-editable draft is shaped
    identically to an accepted one."""
    # Alternatives are free-text like "Aqua Jet @ L24 — priority STAB option";
    # they're advisory, so keep any well-shaped entry as-is.
    alternatives = []
    for alt in result.get("alternatives") or []:
        if not isinstance(alt, dict):
            continue
        value = alt.get("value")
        if not value or not isinstance(value, str):
            continue
        alternatives.append({"value": value, "rationale": alt.get("rationale", "")})

    rationale_text = _rationale_map(result, "learnset").get("learnset")
    rationale = (
        {"learnset": rationale_text} if isinstance(rationale_text, str) else {}
    )

    contract: dict[str, Any] = {
        "draft": {"learnset": deduped},
        "rationale": rationale,
        "alternatives": alternatives,
    }
    if warnings:
        contract["warnings"] = warnings
    return contract


def _flagged_learnset(
    message: str,
    deduped: list[dict[str, Any]],
    result: dict[str, Any],
    warnings: list[str],
) -> SuggestError:
    """A shape-bound ``SuggestError`` that still carries the normalized draft as
    salvage (with the reason under ``error``) so the web layer can hand it back
    for hand-editing rather than only naming the failure."""
    salvage = _assemble_learnset_contract(deduped, result, warnings)
    salvage["error"] = message
    return SuggestError(message, salvage=salvage)


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
    anchors: list[str] | None = None,
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

    Z-moves and Dynamax/G-Max moves are stripped here, once, so the prompt text,
    the slot skeleton, and the draft validator all work from the same trimmed
    pool — see ``learnset_skeleton.is_battle_gimmick``.
    """
    if not move_pool:
        raise SuggestError("No moves are available to suggest from.")
    move_pool = [
        row for row in move_pool if not learnset_skeleton.is_battle_gimmick(row)
    ]
    if not move_pool:
        raise SuggestError("No moves are available to suggest from.")

    if mode == "surgical" and not (instruction and instruction.strip()):
        raise SuggestError(
            "Surgical mode requires an instruction describing which move(s) to change."
        )

    # Anchors are user input at a trust boundary, not model output — so unlike a
    # bad row in a draft (dropped with a warning), a bad anchor fails loud and
    # before the Port call. A typo silently vanishing is the exact bug anchors
    # exist to kill.
    resolved_anchors = _resolve_anchors(anchors, move_pool, mode)

    cached_context = (
        "Move pool (pick ONLY from these moves):\n" + _format_move_pool(move_pool)
    )
    user_context = _build_learnset_user_context(
        entry, abilities, move_pool, mode, instruction, direction, resolved_anchors
    )
    current_learnset = list(entry.get("learnset") or [])

    # FULL mode: code owns placement. The deterministic slot skeleton fixes the
    # levels, band windows, and per-slot candidates (STAB ladders, ability fuel,
    # flavor coverage, status); the model only picks a move per slot and writes
    # the reasoning. Surgical mode edits in place and gets no skeleton.
    skeleton = None
    if mode == "full":
        skeleton = learnset_skeleton.build_skeleton(
            entry, abilities, move_pool, direction=direction, anchors=resolved_anchors
        )
        user_context += "\n" + learnset_skeleton.format_skeleton(skeleton)

    try:
        return propose_with_repair(
            provider=provider,
            system=_build_learnset_rubric(),
            cached_context=cached_context,
            user=user_context,
            schema=_learnset_draft_schema(),
            max_tokens=LEARNSET_MAX_TOKENS,
            validate=lambda draft: _validate_learnset_result(
                draft,
                move_pool,
                mode=mode,
                current_learnset=current_learnset,
                instruction=instruction,
                skeleton=skeleton,
                anchors=resolved_anchors,
            ),
            max_retries=_LEARNSET_MAX_RETRIES,
        )
    except SuggestError as error:
        # Auto-repair backstop: when the retries exhaust with the model still
        # misplacing a row or two, the server finishes the draft itself —
        # deterministically seating each unfilled slot — rather than handing
        # back a salvage banner. Only a clean re-validation uses the result.
        salvage = getattr(error, "salvage", None)
        if skeleton is None or not salvage:
            raise
        rows, notes = learnset_skeleton.autofill(
            salvage["draft"]["learnset"], skeleton
        )
        if learnset_skeleton.validate_against_skeleton(rows, skeleton):
            raise  # auto-repair could not finish either — stay honest
        repaired = dict(salvage)
        repaired["draft"] = {**salvage["draft"], "learnset": rows}
        repaired["warnings"] = list(salvage.get("warnings") or []) + notes
        repaired.pop("error", None)
        return repaired


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
        "- `ability`: a `name` (Title Case) and a `description` of the mechanic — "
        "ONE or TWO short sentences, ~25 words max, matching the terse style of the "
        "existing ability pool (e.g. 'Normal moves become Ghost-type. +20% power.'). "
        "State the effect plainly; no flavor prose, no restating the numbers twice.\n"
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

    rationale_raw = _rationale_map(result, "ability")
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
    from chrooked_pokedex.model.schema import MOVE_TARGETS

    triggers = ", ".join(sorted(_NEUTRAL_TRIGGERS))
    flags_list = (
        "contact, punching, biting, sound, slicing, wind, wing, "
        "kicking, piercing, bone, hammer, ballistic"
    )
    categories = "physical, special, status"
    targets_list = ", ".join(sorted(MOVE_TARGETS))
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
            f"- `target` (usually 'selected'; one of: {targets_list})\n"
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
    from chrooked_pokedex.model.schema import MOVE_TARGETS

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
            "target": {"type": "string", "enum": sorted(MOVE_TARGETS)},
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
    from chrooked_pokedex.model.schema import MOVE_FLAGS, MOVE_TARGETS

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

    # target — the JSON-schema enum (D2) should already constrain this, but a
    # provider can still hand back free text; normalize separators/case, then
    # fall back to "selected" rather than let an out-of-vocabulary target
    # reach the writer (the loader would reject it after a would-be write).
    if "target" in move_draft:
        raw_target = str(move_draft["target"])
        normalized = raw_target.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized not in MOVE_TARGETS:
            warnings.append(
                f"Unknown target {raw_target!r}; falling back to 'selected'. "
                f"Allowed: {', '.join(sorted(MOVE_TARGETS))}."
            )
            normalized = "selected"
        validated["target"] = normalized

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
    rationale_raw = _rationale_map(result, "move")
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


# --------------------------------------------------------------------------- #
# Move-distribution: semantic recipient selection (the prompt mode).
#
# The deterministic engine (chrooked_pokedex.distribute) picks recipients by
# type + attack split. A freeform prompt, though, may be *thematic* ("Pokémon
# that could cut with sharp claws / scythes") and span many types. So this
# capability uses the Port for ONE job only: choose WHICH species fit the prompt
# from the real roster. Level placement stays deterministic in the engine — the
# LLM never decides levels. The endpoint feeds these ids to engine.distribute().
# --------------------------------------------------------------------------- #

# A thematic pick can be broad. With the output trimmed to a flat id list (no
# per-species prose), even a wide "common" pick of a few hundred ids fits — this
# headroom is the safety margin, not the expected size.
DISTRIBUTE_MAX_TOKENS = 8192

# Distribution size budget, in evolution FAMILIES, chosen BEFORE the request. A
# broad ability used to return ~150 mons (slow + a truncated response); bounding
# the ask to the best-fitting N families is the real cure. Default when the caller
# omits it — an unbounded request is the bug this fixes, so never fall back to
# "no limit".
DEFAULT_DISTRIBUTION_LIMIT = 12
MIN_DISTRIBUTION_LIMIT = 1
MAX_DISTRIBUTION_LIMIT = 40


def clamp_distribution_limit(value: Any) -> int:
    """Clamp a requested family budget into ``[MIN, MAX]``; default when unset/invalid.

    A missing, non-int, or bool ``value`` yields :data:`DEFAULT_DISTRIBUTION_LIMIT`
    (bool is guarded because ``bool`` is an ``int`` subclass). Values outside the
    range are clamped, not rejected.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        return DEFAULT_DISTRIBUTION_LIMIT
    return max(MIN_DISTRIBUTION_LIMIT, min(MAX_DISTRIBUTION_LIMIT, value))


def format_species_pool(species: list[dict[str, Any]]) -> str:
    """Compact, cache-stable roster block: ``id  Name  Type[/Type]`` per line.

    Built from the merged dex so it is the real, current roster (base ⊕ Ruleset).
    Only the fields the model needs to choose by concept — id (what it must emit),
    name, and types — so the cached prefix stays lean over ~1.5k species."""
    lines = []
    for entry in species:
        cid = entry.get("chrooked_id")
        if not cid:
            continue
        types = "/".join(entry.get("types") or []) or "?"
        lines.append(f"{cid}\t{entry.get('name', cid)}\t{types}")
    return "\n".join(sorted(lines))


def _distribute_rubric() -> str:
    return (
        "You are a Pokémon game-design assistant. Given one move (its name and "
        "description) and the full species roster, choose every species that "
        "should learn this move under the user's instruction. The instruction may "
        "be MECHANICAL (a type and an attack split) or THEMATIC (a concept from "
        "the move's flavor, e.g. 'could plausibly cut with sharp claws, scythes, "
        "or blades'). For a thematic instruction, include both obvious fits and "
        "well-justified less-obvious ones, but stay faithful to the concept — do "
        "not pad the list. You choose only WHICH species (the recipients); a "
        "separate deterministic step decides at what level each learns it, so do "
        "NOT propose levels. Emit each recipient's chrooked_id EXACTLY as it "
        "appears in the roster. Put the recipient chrooked_ids in `species` (a "
        "flat list of id strings — no per-species prose) and a one-line overall "
        "summary in `rationale`."
    )


# How broad the recipient list should be, by rarity tier — the LLM owns breadth
# in prompt mode (deterministic preset mode narrows by BST instead).
_RARITY_GUIDANCE = {
    "common": "Breadth COMMON: include everyone plausible for the concept.",
    "uncommon": "Breadth UNCOMMON: skip the weakest or most tenuous fits; keep the solid majority.",
    "rare": "Breadth RARE: only strong or notable users — a focused list, not everyone.",
    "signature": "Breadth SIGNATURE: only the few most iconic, defining users (a handful at most).",
}


def _distribute_user_context(
    move: dict[str, Any],
    prompt: str,
    rarity: str,
    constraint: str = "",
    limit: int = DEFAULT_DISTRIBUTION_LIMIT,
) -> str:
    lines = [
        f"Move: {move.get('name', move.get('chrooked_id', '?'))}",
        f"Type: {move.get('type', '?')}   Category: {move.get('category', '?')}",
        f"Description: {move.get('description', '') or '(none)'}",
        f"Instruction from the user: {prompt.strip()}",
        _RARITY_GUIDANCE.get(rarity, _RARITY_GUIDANCE["common"]),
        # The size budget lives in the per-call user message (not the cached system
        # rubric) so the cached prefix stays stable across different budgets.
        f"Choose AT MOST {limit} evolution lines (families), ranked BEST-FIRST; "
        "list each chosen family's roster members. Fewer is fine — do NOT pad.",
    ]
    if constraint:
        lines.append(constraint)
    return "\n".join(lines)


def _distribute_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            # A flat list of chrooked_id strings — no per-species prose, so a
            # broad pick can't blow the token budget on reasoning strings.
            "species": {
                "type": "array",
                "items": {"type": "string"},
            },
            "rationale": {"type": "string"},
        },
        "required": ["species", "rationale"],
        "additionalProperties": False,
    }


def suggest_distribution_species(
    *,
    provider: LlmProvider,
    move: dict[str, Any],
    species: list[dict[str, Any]],
    prompt: str,
    rarity: str = "common",
    constraint: str = "",
    limit: int = DEFAULT_DISTRIBUTION_LIMIT,
) -> dict[str, Any]:
    """Choose recipient species for a move from a freeform prompt; never writes.

    Returns ``{ids, rationale, warnings}``: ``ids`` is the validated recipient
    list (every id confirmed to be a real species), ``warnings`` collects any
    hallucinated ids the model emitted (dropped, never guessed-at). The caller
    feeds ``ids`` to the deterministic placement engine.
    """
    if not prompt or not prompt.strip():
        raise SuggestError("A prompt is required to choose recipients.")
    pool = [e for e in species if e.get("chrooked_id")]
    if not pool:
        raise SuggestError("No species are available to distribute to.")

    known = {e["chrooked_id"] for e in pool}
    result = provider.propose(
        system=_distribute_rubric(),
        cached_context="Species roster (emit chrooked_id exactly):\n"
        + format_species_pool(pool),
        user=_distribute_user_context(move, prompt, rarity, constraint, limit),
        schema=_distribute_schema(),
        max_tokens=DISTRIBUTE_MAX_TOKENS,
    )

    if not isinstance(result, dict) or not isinstance(result.get("species"), list):
        raise SuggestError("The suggestion came back in an unexpected shape.")

    ids: list[str] = []
    seen: set[str] = set()
    warnings: list[str] = []
    for item in result["species"]:
        # The schema is a flat id list; tolerate a stray {"id": ...} object too.
        cid = item.get("id") if isinstance(item, dict) else item
        if not isinstance(cid, str):
            continue
        if cid not in known:
            warnings.append(f"Dropped unknown species id {cid!r} from the suggestion.")
            continue
        if cid not in seen:
            seen.add(cid)
            ids.append(cid)

    if not ids:
        raise SuggestError("The suggestion did not name any known species.")

    rationale = result.get("rationale")
    return {
        "ids": ids,
        "rationale": rationale if isinstance(rationale, str) else "",
        "warnings": warnings,
    }


# =========================================================================== #
# Ability distribution — propose recipients + SLOTS for an EXISTING ability.
# The distribution twin of `suggest_ability_creation`: it reuses that flow's
# distribution rubric shape AND its `_validate_distribution` (species resolved BY
# NAME, invalid rows DROPPED with warnings), but designs no ability — the ability
# already exists. Never writes; the accept path is the species CRUD.
# =========================================================================== #


def _build_ability_distribution_rubric(
    limit: int = DEFAULT_DISTRIBUTION_LIMIT,
) -> str:
    """System rubric for spreading an EXISTING ability onto fitting species.

    The distribution half of the ability-creation contract, on its own: pick
    recipient species (BY NAME, from the roster only) and a slot each, bounded to
    the best-fitting ``limit`` evolution families. The model never invents species;
    a hallucinated pick is dropped downstream.
    """
    return (
        "You are a Pokémon game-design assistant. Given an EXISTING ability and an "
        "instruction, choose which species should have it and in which slot. "
        f"Choose AT MOST {limit} of the BEST-FITTING evolution families (ranked "
        "best-first); for each chosen family list its in-roster members, each with "
        "a slot. Fewer is fine; do NOT pad. "
        "Produce `distribution`: a compact list where each row is ONLY {species "
        "(real Pokémon NAME), slot (one of primary/secondary/hidden)} — do NOT emit "
        "per-row reasoning (it wastes the budget and is discarded). Choose species "
        "ONLY from the provided roster; do NOT name any species not listed (this "
        "dex is a subset of all Pokémon). Prefer the hidden slot unless the ability "
        "defines the species. It is fine to propose ZERO species. Put the list in "
        "`draft.distribution` and a one-line summary in `rationale.distribution`."
    )


def _ability_distribution_schema() -> dict[str, Any]:
    """JSON schema for the ability-distribution draft: ``{draft:{distribution:[]}}``."""
    return {
        "type": "object",
        "properties": {
            "draft": {
                "type": "object",
                "properties": {
                    "distribution": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "species": {"type": "string"},
                                "slot": {"type": "string"},
                            },
                            "required": ["species", "slot"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["distribution"],
                "additionalProperties": False,
            },
            "rationale": {
                "type": "object",
                "properties": {"distribution": {"type": "string"}},
                "additionalProperties": False,
            },
        },
        "required": ["draft"],
        "additionalProperties": False,
    }


def suggest_ability_distribution(
    *,
    provider: LlmProvider,
    ability: dict[str, Any],
    dex_lookup: dict[str, dict[str, Any]],
    roster: list[str],
    prompt: str,
    rarity: str = "common",
    limit: int = DEFAULT_DISTRIBUTION_LIMIT,
) -> dict[str, Any]:
    """Propose recipient species + slots for an EXISTING ability; never writes.

    Reuses the ability-creation distribution rubric shape and the shared
    :func:`_validate_distribution` (species resolved BY NAME via ``dex_lookup``;
    a row naming an out-of-dex species or an invalid slot is DROPPED into
    ``warnings`` rather than failing the proposal). Returns
    ``{rows, rationale, warnings}`` where each row is ``{species (chrooked_id),
    slot, replaces, reasoning}``.

    ``prompt`` is the instruction (the route passes the ability's own description
    when the user gives none); an empty prompt is guarded. ``roster`` is the sorted
    in-dex species NAME list fed to the model so its picks stay in-dex.
    """
    if not prompt or not prompt.strip():
        raise SuggestError("A prompt is required to choose recipients.")
    name = ability.get("name") or ability.get("chrooked_id") or "?"
    cached_context = (
        "Species roster (choose distribution species ONLY from these — this dex is "
        "a subset of all Pokémon; do NOT name any species not listed):\n"
        + (_format_roster(roster) or "(none)")
    )
    user = (
        f"Existing ability: {name}\n"
        f"Description: {ability.get('description', '') or '(none)'}\n"
        f"Instruction from the user: {prompt.strip()}\n"
        + _RARITY_GUIDANCE.get(rarity, _RARITY_GUIDANCE["common"])
    )
    result = provider.propose(
        system=_build_ability_distribution_rubric(limit),
        cached_context=cached_context,
        user=user,
        schema=_ability_distribution_schema(),
        max_tokens=DISTRIBUTE_MAX_TOKENS,
    )
    if not isinstance(result, dict):
        raise SuggestError("The suggestion came back in an unexpected shape.")
    draft = result.get("draft")
    if not isinstance(draft, dict):
        raise SuggestError("The suggestion was missing a draft object.")
    rows, warnings = _validate_distribution(draft.get("distribution"), dex_lookup)
    summary = _rationale_map(result, "distribution").get("distribution")
    return {
        "rows": rows,
        "rationale": summary if isinstance(summary, str) else "",
        "warnings": warnings,
    }
