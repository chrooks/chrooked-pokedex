"""Parse `ruleset/QUEUE.md` rows and resolve them to final-stage design records.

The queue is Chris's capture Surface: freeform rows typed while playing
(`Krabby & Corphish lines`, `Absol - 540 BST`, `Alakazam mirroed BST w Gengar`).
Nothing here does I/O; the router reads the file and hands the text in.

Row grammar (`SUBJECTS [SEPARATOR STEER]`):

- SUBJECTS is the leading run of species names joined by `&` or `and`; the
  words `line`, `lines`, `the` are dropped; `Alolan X` -> `X Alola` (and
  Galarian/Hisuian/Paldean likewise) so the queue reads like Chris talks.
- The run ends at the first `,`, at ` - `, or at the first word that is not a
  species name. Everything from there on is the steer, verbatim.
- Each subject resolves to the FINAL stage of its line (walk `evolves_into`).
  A pre-evo on a branching line is rejected with the branch finals named —
  guessing a branch would design the wrong creature silently.
- Species names inside the steer become `references` (ids as named, not
  walked), so the packet can carry their stats as numbers only.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any
from .lore_text import PUNCTUATED_NAMES

REGIONAL_PREFIXES = {
    "alolan": "Alola",
    "galarian": "Galar",
    "hisuian": "Hisui",
    "paldean": "Paldea",
}
_DROPPED_WORDS = {"line", "lines", "the"}
_JOINERS = {"&", "and"}
_MAX_NAME_WORDS = 4  # "Alcremie Berry Caramel Swirl"
_SEPARATOR = re.compile(r",| - ")
_TOKEN = re.compile(r"\S+")


@dataclass(frozen=True)
class ParsedRow:
    subjects: tuple[str, ...]  # display names as written (regional prefix rewritten)
    steer: str
    raw: str
    line_no: int


@dataclass(frozen=True)
class ResolvedRow:
    id: str
    line: list[str]
    forms: list[str]
    group: str | None
    steer: str
    references: list[str]
    raw: str


@dataclass(frozen=True)
class Unresolved:
    row: str
    reason: str


def display_names(snapshot: dict[str, Any]) -> dict[str, str]:
    """Lower-cased display name -> chrooked_id, the lookup every step below uses.

    Canon punctuated spellings ("Farfetch'd", "Kommo-o") resolve too: the dex
    strips the punctuation, but a queue row is written the way the game spells it.
    """
    names = {base["name"].lower(): cid for cid, base in snapshot["species"].items()}
    for dex_name, canon in PUNCTUATED_NAMES.items():
        if dex_name.lower() in names:
            names[canon.lower()] = names[dex_name.lower()]
    return names


def _clean(token: str) -> str:
    """Strip punctuation and a possessive so `Mawile's` and `(Golem)` match."""
    token = re.sub(r"[^\w\s'.-]", "", token)
    if token.lower().endswith("'s"):
        token = token[:-2]
    return token.strip("'.-")


def _match_name(
    tokens: list[str], start: int, names: dict[str, str]
) -> tuple[str, int] | None:
    """Longest species name starting at `tokens[start]`; returns (name, words used)."""
    head = _clean(tokens[start])
    if head.lower() in REGIONAL_PREFIXES and start + 1 < len(tokens):
        candidate = f"{_clean(tokens[start + 1])} {REGIONAL_PREFIXES[head.lower()]}"
        if candidate.lower() in names:
            return candidate, 2
    for width in range(min(_MAX_NAME_WORDS, len(tokens) - start), 0, -1):
        candidate = " ".join(_clean(t) for t in tokens[start : start + width])
        if candidate.lower() in names:
            return candidate, width
    return None


def parse_rows(text: str, names: dict[str, str]) -> list[ParsedRow]:
    """Split queue text into rows of (subjects, steer). Blank and `#` rows are skipped.

    `names` is `display_names(snapshot)`; the grammar needs it because the
    subject run ends at the first word that is not a species name.
    """
    rows: list[ParsedRow] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        row = raw.strip()
        if not row or row.startswith("#"):
            continue
        sep = _SEPARATOR.search(row)
        head_end = sep.start() if sep else len(row)
        head = row[:head_end]
        matches = list(_TOKEN.finditer(head))
        tokens = [m.group() for m in matches]
        subjects: list[str] = []
        i = 0
        steer_start: int | None = None
        while i < len(tokens):
            word = tokens[i].lower()
            if word in _DROPPED_WORDS or word in _JOINERS:
                i += 1
                continue
            found = _match_name(tokens, i, names)
            if found is None:
                steer_start = matches[i].start()
                break
            subjects.append(found[0])
            i += found[1]
        if steer_start is not None:
            steer = row[steer_start:].strip()
        elif sep:
            steer = row[sep.end():].strip()
        else:
            steer = ""
        rows.append(ParsedRow(tuple(subjects), steer, row, line_no))
    return rows


def _evolves_to(snapshot: dict[str, Any], cid: str) -> list[str]:
    seen: list[str] = []
    for edge in snapshot["species"][cid].get("evolves_into") or []:
        if edge["to"] not in seen and edge["to"] in snapshot["species"]:
            seen.append(edge["to"])
    return seen


def _finals_under(snapshot: dict[str, Any], cid: str, visited: frozenset[str] = frozenset()) -> list[str]:
    nexts = [n for n in _evolves_to(snapshot, cid) if n not in visited]
    if not nexts:
        return [cid]
    out: list[str] = []
    for n in nexts:
        out.extend(f for f in _finals_under(snapshot, n, visited | {cid}) if f not in out)
    return out


def _walk_to_final(snapshot: dict[str, Any], cid: str) -> str | list[str]:
    """The final-stage id, or the list of branch finals when the line forks ahead."""
    visited: set[str] = set()
    while True:
        nexts = _evolves_to(snapshot, cid)
        if not nexts or cid in visited:
            return cid
        if len(nexts) > 1:
            return _finals_under(snapshot, cid)
        visited.add(cid)
        cid = nexts[0]


def _line_of(snapshot: dict[str, Any], final: str) -> list[str]:
    line = [final]
    cid = final
    while True:
        evo = snapshot["species"][cid].get("evolution") or {}
        prev = evo.get("from")
        if not prev or prev not in snapshot["species"] or prev in line:
            return line
        line.insert(0, prev)
        cid = prev


def _forms_of(snapshot: dict[str, Any], final: str) -> list[str]:
    return [
        cid
        for cid in snapshot["species"]
        if cid != final
        and cid.startswith(final)
        and ("mega" in cid[len(final):] or "gmax" in cid[len(final):])
    ]


def _references(steer: str, names: dict[str, str]) -> list[str]:
    tokens = _TOKEN.findall(steer)
    refs: list[str] = []
    i = 0
    while i < len(tokens):
        found = _match_name(tokens, i, names)
        if found is None:
            i += 1
            continue
        cid = names[found[0].lower()]
        if cid not in refs:
            refs.append(cid)
        i += found[1]
    return refs


def resolve_row(
    row: ParsedRow, snapshot: dict[str, Any], names: dict[str, str]
) -> list[ResolvedRow] | Unresolved:
    """Resolve every subject to its final stage, or reject the whole row honestly."""
    if not row.subjects:
        first = _clean(row.raw.split()[0])
        hint = difflib.get_close_matches(first.lower(), list(names), n=1, cutoff=0.8)
        suggestion = (
            f"; did you mean {snapshot['species'][names[hint[0]]]['name']!r}?" if hint else ""
        )
        return Unresolved(
            row.raw, f"no species name recognised at the start of the row{suggestion}"
        )
    finals: list[str] = []
    for subject in row.subjects:
        cid = names.get(subject.lower())
        if cid is None:
            return Unresolved(row.raw, f"unknown species {subject!r}")
        final = _walk_to_final(snapshot, cid)
        if isinstance(final, list):
            branch_names = ", ".join(snapshot["species"][f]["name"] for f in final)
            return Unresolved(
                row.raw,
                f"{subject!r} is a pre-evo on a branching line; name one final: {branch_names}",
            )
        if final not in finals:
            finals.append(final)
    group = "+".join(finals) if len(finals) > 1 else None
    references = _references(row.steer, names)
    return [
        ResolvedRow(
            id=final,
            line=_line_of(snapshot, final),
            forms=_forms_of(snapshot, final),
            group=group,
            steer=row.steer,
            references=references,
            raw=row.raw,
        )
        for final in finals
    ]
