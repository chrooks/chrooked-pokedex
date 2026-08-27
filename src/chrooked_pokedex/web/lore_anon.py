"""Anonymize researched lore so a suggestion is designed from the creature, not
from what the model already knows the creature learns.

The prior-art trap: a model that recognizes the species reaches for its canon
kit. Stripping the name removes the *reflex*. It does not — and cannot — make
identification impossible: a distinctive design origin still points at one
creature. Proven in practice on the Ariados line, where a blind pass named the
Ariadne myth from an anonymized profile. That is fine. The point is that the
design has to be argued from the lore rather than recalled from a wiki, and
callers must not promise more than that.

Pure text in, pure text out — no network, no model, no Ruleset.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

SUBJECT = "this creature"
OTHER = "another creature"

# "No. 167", "#167", "№ 167" — a dex number is a lookup key, nothing else.
_DEX_NUMBER = re.compile(r"(?:\bNo\.?\s*|#|№\s*)\d{1,4}\b", re.IGNORECASE)
# The franchise's own words, in every casing the dex text uses. "Pokedex" needs
# its own alternative rather than riding on the "Pokemon" one — a real Ariados
# profile leaked "Its Sun Pokedex entry" straight through a Pokemon-only pattern.
_FRANCHISE = re.compile(r"\bPok[eé]dex\b|\bPok[eé]mon\b", re.IGNORECASE)
# Generation names ride along with a dex citation ("Its Sun Pokedex entry"), and
# a game title dates the creature as surely as a number identifies it.
_GAME_CITATION = re.compile(
    r"\b(its)\s+[A-Z][A-Za-z]*(?:\s+and\s+[A-Z][A-Za-z]*)?\s+(?=creature entry\b)",
    re.IGNORECASE,
)
# "Mega Charizard" / "Mega Evolution" — the mechanic names the creature.
_MEGA = re.compile(r"\bMega\b", re.IGNORECASE)


def _name_pattern(names: Iterable[str]) -> re.Pattern[str] | None:
    """A word-boundary alternation over species display names, longest first.

    Case-SENSITIVE on purpose. Species names are capitalized and a few of them
    are ordinary English words (Ditto, Golem). Matching case-sensitively keeps
    "a golem of rock" intact while still catching "Golem" the species. Longest
    first so "Mr. Mime" is redacted before "Mime" can split it.
    """
    cleaned = sorted({n.strip() for n in names if n and len(n.strip()) >= 3}, key=len, reverse=True)
    if not cleaned:
        return None
    return re.compile(r"\b(?:" + "|".join(re.escape(n) for n in cleaned) + r")\b")


def anonymize_text(
    text: str,
    *,
    subject_names: Iterable[str] = (),
    other_names: Iterable[str] = (),
) -> str:
    """Redact species names, dex numbers, and franchise markers from one string."""
    if not text:
        return ""
    out = text
    subject_re = _name_pattern(subject_names)
    if subject_re is not None:
        out = subject_re.sub(SUBJECT, out)
    other_re = _name_pattern(other_names)
    if other_re is not None:
        out = other_re.sub(OTHER, out)
    out = _DEX_NUMBER.sub("", out)
    out = _MEGA.sub("an empowered variant of", out)
    out = _FRANCHISE.sub("creature", out)
    # "Its Sun creature entry ..." -> "Its creature entry ..." — drop the title
    # left stranded once the dex word was genericized.
    out = _GAME_CITATION.sub(lambda m: m.group(1) + " ", out)
    # Redaction leaves doubled spaces and space-before-punctuation behind.
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    return out.strip()


def anonymize_lore(
    *,
    genus: str,
    dex_entries: Iterable[str],
    origin: str,
    subject_names: Iterable[str] = (),
    other_names: Iterable[str] = (),
) -> dict[str, object]:
    """Anonymize a fetched lore profile for a blind design pass.

    Returns the fields :func:`lore_text.render_lore` needs, with `name_origin`
    **dropped entirely** — etymology is the one section whose whole job is to
    name the creature, so there is nothing in it worth keeping.

    `origin` is kept and redacted rather than dropped: the real-world biology and
    the myth behind a design are exactly the material a blind pass reasons from.
    """
    return {
        "genus": anonymize_text(genus, subject_names=subject_names, other_names=other_names),
        "dex_entries": tuple(
            anonymize_text(e, subject_names=subject_names, other_names=other_names)
            for e in dex_entries
            if e
        ),
        "origin": anonymize_text(origin, subject_names=subject_names, other_names=other_names),
        "name_origin": "",
    }
