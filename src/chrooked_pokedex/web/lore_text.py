"""Pure text functions for the lore lookup — no HTTP, no state, no I/O.

The suggest capabilities that reason about a creature's identity used to answer
from the model's training recall, which produced confident fabrications (a Glalie
ability was justified with "its name derived from *glace*, French for ice"; the
real etymology is glacier + goalie). :mod:`lore` fetches real sources; this module
turns what comes back into prompt-ready prose.

Kept separate from the fetcher so every rule here is testable against a captured
payload with no network in sight. The tests in ``tests/test_lore_text.py`` run
these against real Glalie fixtures under ``tests/fixtures/lore/``.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

# The prompt block is capped so a long encyclopedia page cannot crowd out the
# species facts that follow it. ~4k characters is roughly a page of prose: enough
# for a genus, a dozen dex entries, and an origin section.
DEFAULT_LORE_CAP = 4000

# What the model is told when a species has no findable lore. Fan-made species
# (`palossandicyaevian` is a real Ruleset file) are in no public database. Saying
# nothing is what let the model fill the silence, so the absence is stated
# outright and the instruction is explicit.
NOT_FOUND_BLOCK = (
    "Researched lore: NONE FOUND. No Pokedex entry, origin, or etymology could "
    "be retrieved for this species from any source — it is most likely bespoke "
    "to this game. Do NOT invent dex flavor, etymology, or real-world "
    "inspiration for it. Reason only from the concrete data given above (typing, "
    "stats, learnset, abilities), and say plainly in your rationale that no "
    "published lore was available."
)


def base_species_id(chrooked_id: str, known_species: Iterable[str]) -> str:
    """Map a form id to the base species a dex-text source will recognize.

    PokeAPI keys flavor text on the base species and returns HTTP 404 for every
    form id — ``marowakalola``, ``goodrahisui``, and ``glaliemega`` all miss. The
    Ruleset uses bare concatenated slugs, so the base is a *prefix* of the form.

    Returns the longest known species id that prefixes ``chrooked_id``, or the
    input unchanged when it is itself known or nothing prefixes it. Passing the
    real species set (from the base snapshot) means this never guesses against a
    hardcoded list of form suffixes.

        >>> base_species_id("marowakalola", {"marowak", "marowakalola"})
        'marowakalola'
        >>> base_species_id("marowakalola", {"marowak"})
        'marowak'
    """
    key = chrooked_id.strip().lower()
    known = {s.strip().lower() for s in known_species}
    if key in known:
        return key
    return fallback_base_id(key, known) or key


def fallback_base_id(chrooked_id: str, known_species: Iterable[str]) -> str:
    """The longest known species that is a STRICT prefix of ``chrooked_id``.

    Used after a direct lookup misses. :func:`base_species_id` returns a known id
    unchanged, which is right in the abstract but wrong against this dex: canon
    regional forms like ``marowakalola`` ARE their own species in the base
    snapshot, so "is it known" tells you nothing about whether PokeAPI has a page
    for it — and PokeAPI has none. The upstream 404 is the only honest signal, so
    the caller tries the id first and falls back through here.

    Returns ``""`` when nothing prefixes it, meaning there is no base to try.

        >>> fallback_base_id("marowakalola", {"marowak", "marowakalola"})
        'marowak'
    """
    key = chrooked_id.strip().lower()
    known = {s.strip().lower() for s in known_species}
    prefixes = [s for s in known if key.startswith(s) and s != key]
    if not prefixes:
        return ""
    return max(prefixes, key=len)


_REF_RE = re.compile(r"<ref[^>]*?/>|<ref[^>]*>.*?</ref>", re.S | re.I)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_HEADING_RE = re.compile(r"^\s*=+\s*.*?\s*=+\s*$", re.M)
_TEMPLATE_RE = re.compile(r"\{\{([^{}]*)\}\}")
_PIPED_LINK_RE = re.compile(r"\[\[[^\]|]*\|([^\]]*)\]\]")
_PLAIN_LINK_RE = re.compile(r"\[\[([^\]]*)\]\]")
_EXTERNAL_LINK_RE = re.compile(r"\[https?://\S+\s+([^\]]*)\]")
_BARE_EXTERNAL_RE = re.compile(r"\[https?://\S+\]")
_BOLD_ITALIC_RE = re.compile(r"'{2,5}")
_WS_RE = re.compile(r"[ \t]+")
_BLANKLINE_RE = re.compile(r"\n{3,}")


def clean_wikitext(raw: str) -> str:
    """Turn MediaWiki markup into plain prose, keeping the words that carry meaning.

    THE TRAP THIS FUNCTION EXISTS FOR: dropping ``{{...}}`` templates wholesale
    destroys the sentence. Bulbapedia wraps the very nouns that matter — Glalie's
    real "Name origin" section reads ``a combination of ''{{wp|glacier}}'' and
    ''{{wp|Goaltender|goalie}}''``, and a naive strip turns that into "a
    combination of and". The etymology disappears and the model is handed a
    sentence with a hole in it, which is worse than no lore at all.

    So a template collapses to its LAST pipe-separated argument, which is the
    display text in the ``{{wp|Target|shown}}`` form Bulbapedia uses throughout,
    and the only argument in the ``{{wp|oni}}`` form. Templates are resolved
    innermost-first so nesting unwinds correctly.

    Citations (``<ref>``) go entirely — they are sources, not prose, and their
    URLs would eat the character budget.
    """
    text = _COMMENT_RE.sub("", raw)
    text = _REF_RE.sub("", text)
    text = _HEADING_RE.sub("", text)

    # Innermost-first so nested templates unwind. Bounded: each pass strictly
    # reduces the brace count, and the loop stops when nothing more matches.
    while True:
        collapsed = _TEMPLATE_RE.sub(lambda m: m.group(1).split("|")[-1].strip(), text)
        if collapsed == text:
            break
        text = collapsed

    text = _PIPED_LINK_RE.sub(r"\1", text)
    text = _PLAIN_LINK_RE.sub(r"\1", text)
    text = _EXTERNAL_LINK_RE.sub(r"\1", text)
    text = _BARE_EXTERNAL_RE.sub("", text)
    text = _BOLD_ITALIC_RE.sub("", text)
    text = _TAG_RE.sub("", text)
    text = _WS_RE.sub(" ", text)
    text = _BLANKLINE_RE.sub("\n\n", text)
    return text.strip()


def pokeapi_lore(payload: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    """The English genus and de-duplicated English dex entries from a species payload.

    Flavor text in PokeAPI carries hard line breaks and form feeds from the
    original game text boxes; those become spaces. Entries repeat across game
    versions — Glalie ships 25 English entries that reduce to 15 unique ones — so
    duplicates are dropped while first-seen order is kept.

    A payload missing either field yields empty values rather than raising: a
    thin species page is an ordinary outcome, not an error.
    """
    genus = ""
    for entry in payload.get("genera") or ():
        if isinstance(entry, dict) and (entry.get("language") or {}).get("name") == "en":
            genus = str(entry.get("genus", "")).strip()
            break

    seen: set[str] = set()
    entries: list[str] = []
    for entry in payload.get("flavor_text_entries") or ():
        if not isinstance(entry, dict):
            continue
        if (entry.get("language") or {}).get("name") != "en":
            continue
        text = str(entry.get("flavor_text", ""))
        text = text.replace("\n", " ").replace("\f", " ").replace("­", "")
        text = _WS_RE.sub(" ", text).strip()
        if text and text not in seen:
            seen.add(text)
            entries.append(text)
    return genus, tuple(entries)


def truncate_at_sentence(text: str, cap: int) -> str:
    """Trim to at most ``cap`` characters, preferring the last sentence boundary.

    Cutting mid-sentence hands the model a fragment it may try to complete from
    imagination, which is the failure this whole feature exists to prevent. When
    no boundary sits in the last quarter of the budget, cuts at the cap and marks
    the truncation so the model knows the text was clipped rather than finished.
    """
    if len(text) <= cap:
        return text
    window = text[:cap]
    boundary = max(window.rfind(". "), window.rfind(".\n"), window.rfind("! "))
    if boundary >= cap * 0.75:
        return window[: boundary + 1]
    return window.rstrip() + " […truncated]"


def render_lore(
    *,
    found: bool,
    genus: str,
    dex_entries: Iterable[str],
    origin: str,
    name_origin: str,
    requested_id: str = "",
    base_species: str = "",
    cap: int = DEFAULT_LORE_CAP,
) -> str:
    """Assemble the lore block that gets injected into a suggest prompt.

    Returns :data:`NOT_FOUND_BLOCK` when ``found`` is false. When the lore was
    fetched for a base species rather than the requested form (``marowakalola``
    resolving to ``marowak``), the block opens with a label saying so — the base
    creature's dex text is relevant to a regional form but is not a description
    of it, and the model must not read it as one.
    """
    if not found:
        return NOT_FOUND_BLOCK

    parts: list[str] = ["Researched lore (read this; do not contradict it):"]
    if base_species and requested_id and base_species != requested_id:
        parts.append(
            f"NOTE: this lore describes the BASE species '{base_species}', not the "
            f"form '{requested_id}' being designed. Treat it as background about "
            "the creature's family; the form may differ in body, habitat, and "
            "temperament. Do not state base-species details as facts about this form."
        )
    if genus:
        parts.append(f"Category: {genus}")

    entries = [e for e in dex_entries if e]
    if entries:
        parts.append("Pokedex entries:")
        parts.extend(f"- {entry}" for entry in entries)
    if origin:
        parts.append(f"Design origin: {origin}")
    if name_origin:
        parts.append(f"Name origin: {name_origin}")

    return truncate_at_sentence("\n".join(parts), cap)
