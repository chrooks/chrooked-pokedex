"""Rule-based move distribution: pick recipients, gap-place a level per species.

The shared engine behind the `move-distribute` skill (CLI) and the web
distributor endpoint. It is deliberately data-source-agnostic: callers build
:class:`SpeciesRecord`s (from the base snapshot, or from the merged dex so
Ruleset edits are reflected) and an evolution index, then call this module. That
keeps the two front doors on one Seam, the way ``dispatch.py`` does for apply.

Two concerns, kept separate so a semantic (LLM-picked) recipient set composes
with deterministic placement:

* **Who** — :func:`select_by_rule` (type + attack split) or any externally
  supplied id set (e.g. an LLM's thematic pick).
* **When** — :func:`best_level` drops the move into the widest gap of a level
  window, so it never lands on an occupied level and keeps spacing.

Distribution is append-only by contract: a row only ever *adds* the move to a
species; callers must never use a row to drop an existing move.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

# Named windows expand to (min, max) level ranges; callers may override with
# explicit numbers. Level numbers are the real metric, presets are shorthand.
PRESETS: dict[str, tuple[int, int]] = {
    "start": (1, 5),
    "early": (6, 15),
    "mid": (16, 35),
    "late": (36, 48),
    "end": (48, 64),
}

# Rarity tiers (run-scoped). `keep` is the fraction of preset-matched recipients
# to retain, ranked by BST (rare = only the strong few); in prompt mode the tier
# steers the LLM instead. `bias` is the preferred position in the level window
# [0=earliest, 1=latest] — a gentle tie-break so rarer moves land later without
# ever colliding (gap placement still dominates).
RARITY: dict[str, dict[str, float]] = {
    "common": {"keep": 1.0, "bias": 0.0},
    "uncommon": {"keep": 0.75, "bias": 0.34},
    "rare": {"keep": 0.5, "bias": 0.67},
    "signature": {"keep": 0.2, "bias": 1.0},
}

# Attack-split predicates over base (atk, spa).
SPLITS: dict[str, Callable[[int, int], bool]] = {
    "physical": lambda atk, spa: atk >= spa,
    "special": lambda atk, spa: spa >= atk,
    "strong-physical": lambda atk, spa: atk > spa,
    "strong-special": lambda atk, spa: spa > atk,
    "any": lambda atk, spa: True,
}

# Legendaries / mythicals / paradox / ultra beasts by national dex number,
# excluded by default. Curated best-effort; callers print/show what was included
# so stragglers are visible. See the move-distribute skill for the rationale.
LEGENDARY_DEX: frozenset[int] = frozenset(
    {144, 145, 146, 150, 151}
    | {243, 244, 245, 249, 250, 251}
    | set(range(377, 387))
    | set(range(480, 494))
    | {494}
    | set(range(638, 650))
    | set(range(716, 722))
    | {772, 773}
    | set(range(785, 810))
    | set(range(888, 899))
    | {905}
    | set(range(984, 996))
    | set(range(1001, 1026))
)


@dataclass(frozen=True)
class SpeciesRecord:
    """One species as the engine needs it. Built by the caller from whatever data
    source (base snapshot, or merged dex). ``levels`` is the species' current
    learnset levels; ``has_move`` is whether it already learns the target move."""

    chrooked_id: str
    name: str
    dex: int | None
    types: tuple[str, ...]
    atk: int
    spa: int
    levels: tuple[int, ...]
    bst: int = 0
    has_move: bool = False


@dataclass(frozen=True)
class DistributionRow:
    """One proposed learnset insertion. Append-only: it adds ``move`` at ``level``
    to ``chrooked_id``. ``matched`` marks a direct rule/prompt hit; line relatives
    pulled in by evolution expansion are ``matched=False``."""

    chrooked_id: str
    name: str
    dex: int | None
    level: int
    stage: str  # "first" | "evolved"
    line_id: str
    matched: bool
    already_has: bool


def parse_window(*, preset: str | None = None,
                 levels: tuple[int, int] | None = None) -> tuple[int, int]:
    """Resolve a level window from explicit numbers (wins) or a named preset."""
    if levels is not None:
        lo, hi = levels
        if lo > hi:
            lo, hi = hi, lo
        return max(1, lo), max(1, hi)
    return PRESETS[preset or "early"]


def is_alt_battle_form(name: str) -> bool:
    """Mega / Primal forms share the base species' learnset, so distributing onto
    them is redundant. Detected by display name so it needs no curated list."""
    n = name.lower()
    return "mega" in n or "primal" in n


def best_level(existing_levels: Iterable[int], lo: int, hi: int,
               bias: float = 0.0) -> int:
    """The widest-gap level in [lo, hi] (so the move never collides), breaking
    ties toward ``bias``'s preferred position (0 = earliest, 1 = latest). Gap is
    always primary, so the bias only nudges among equally-spaced slots."""
    existing = sorted(set(existing_levels))
    preferred = lo + bias * (hi - lo)
    best_level_, best_key = lo, None
    for level in range(lo, hi + 1):
        gap = min((abs(level - e) for e in existing), default=99)
        # Maximize gap first, then minimize distance to the preferred position.
        key = (gap, -abs(level - preferred))
        if best_key is None or key > best_key:
            best_level_, best_key = level, key
    return best_level_


def apply_breadth(records_by_id: Mapping[str, "SpeciesRecord"],
                  matched_ids: Iterable[str], rarity: str) -> list[str]:
    """Narrow a preset-matched recipient set to a rarity tier: keep the top
    ``RARITY[rarity]['keep']`` fraction ranked by BST (rarer = the strong few).
    Common keeps everyone. Always keeps at least one. Prompt mode does NOT use
    this — there the LLM owns breadth via the rubric."""
    ids = list(matched_ids)
    keep = RARITY.get(rarity, RARITY["common"])["keep"]
    if keep >= 1.0 or len(ids) <= 1:
        return ids
    ranked = sorted(
        ids,
        key=lambda cid: (-(records_by_id[cid].bst if cid in records_by_id else 0),
                         records_by_id[cid].dex if cid in records_by_id and
                         records_by_id[cid].dex is not None else 10**6),
    )
    keep_n = max(1, math.ceil(len(ranked) * keep))
    return ranked[:keep_n]


# --------------------------------------------------------------------------- #
# Evolution index: connected components over forward (evolves_into) edges.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EvolutionIndex:
    """Pre-computed evolution topology. ``line_of`` maps a species to its line id
    (the lowest-dex member); ``members`` maps a line id to its full member set;
    ``evolved`` is every species that is some other species' evolution target."""

    line_of: Mapping[str, str]
    members: Mapping[str, frozenset[str]]
    evolved: frozenset[str]

    def line_members(self, chrooked_id: str) -> frozenset[str]:
        line = self.line_of.get(chrooked_id)
        return self.members.get(line, frozenset({chrooked_id})) if line else frozenset({chrooked_id})


def build_evolution_index(species: Mapping[str, Mapping]) -> EvolutionIndex:
    """Build the evolution index from snapshot species (each carrying
    ``evolves_into`` forward edges and a ``dex``). Components are undirected over
    those edges; the line id is the member with the smallest dex."""
    # Union-find over forward edges.
    parent: dict[str, str] = {cid: cid for cid in species}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    evolved: set[str] = set()
    for cid, v in species.items():
        for edge in (v.get("evolves_into") or []):
            to = edge.get("to")
            if to in parent:
                union(cid, to)
                evolved.add(to)

    # Group members by component, then name each line by its lowest-dex member.
    comp: dict[str, set[str]] = {}
    for cid in species:
        comp.setdefault(find(cid), set()).add(cid)

    def dex_of(cid: str) -> int:
        d = species[cid].get("dex")
        return d if isinstance(d, int) else 10**6

    line_of: dict[str, str] = {}
    members: dict[str, frozenset[str]] = {}
    for group in comp.values():
        line_id = min(group, key=lambda c: (dex_of(c), c))
        frozen = frozenset(group)
        members[line_id] = frozen
        for cid in group:
            line_of[cid] = line_id
    return EvolutionIndex(line_of=line_of, members=members, evolved=frozenset(evolved))


# --------------------------------------------------------------------------- #
# Selection + placement
# --------------------------------------------------------------------------- #


def select_by_rule(records: Iterable[SpeciesRecord], *, types: set[str], split: str,
                   include_legendaries: bool = False,
                   include_megas: bool = False) -> list[str]:
    """Deterministic recipient ids: any matching type AND the split predicate,
    excluding legendaries and Mega/Primal forms unless asked to keep them."""
    pred = SPLITS[split]
    out: list[str] = []
    for r in records:
        if types and not (set(r.types) & types):
            continue
        if not pred(r.atk, r.spa):
            continue
        if not include_legendaries and r.dex in LEGENDARY_DEX:
            continue
        if not include_megas and is_alt_battle_form(r.name):
            continue
        out.append(r.chrooked_id)
    return out


def distribute(records_by_id: Mapping[str, SpeciesRecord], evo: EvolutionIndex, *,
               matched_ids: Iterable[str], window: tuple[int, int],
               include_evolutions: bool = True,
               evolved_at_1: bool = False,
               level_bias: float = 0.0) -> list[DistributionRow]:
    """Build the full row set for a matched recipient set.

    Each matched species becomes a ``matched=True`` row; with ``include_evolutions``
    its whole evolution line is pulled in (relatives as ``matched=False`` rows, all
    levels pre-computed up front so the UI can toggle a line without another call).
    Every species' level is gap-placed in ``window`` independently, except evolved
    forms when ``evolved_at_1`` parks them at level 1 (Move Reminder access)."""
    lo, hi = window
    matched = set(matched_ids)

    # Expand to the full id set, remembering which were direct hits.
    target_ids: dict[str, bool] = {}
    for cid in matched:
        if cid not in records_by_id:
            continue
        target_ids[cid] = True
        if include_evolutions:
            for member in evo.line_members(cid):
                if member in records_by_id:
                    target_ids.setdefault(member, False)

    rows: list[DistributionRow] = []
    for cid, is_matched in target_ids.items():
        rec = records_by_id[cid]
        is_evolved = cid in evo.evolved
        level = (1 if (is_evolved and evolved_at_1)
                 else best_level(rec.levels, lo, hi, level_bias))
        rows.append(DistributionRow(
            chrooked_id=cid,
            name=rec.name,
            dex=rec.dex,
            level=level,
            stage="evolved" if is_evolved else "first",
            line_id=evo.line_of.get(cid, cid),
            matched=is_matched,
            already_has=rec.has_move,
        ))
    # Stable order: by line (lowest dex), then dex within the line.
    rows.sort(key=lambda r: (records_by_id[r.line_id].dex or 10**6, r.dex or 10**6, r.chrooked_id))
    return rows
