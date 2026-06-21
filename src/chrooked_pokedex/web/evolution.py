"""The pure evolution-graph transform for the base snapshot.

`evolution_parser.parse_evolutions` yields the FULL forward graph keyed by
engine symbol: `{SPECIES_BUIZEL: [EvolutionEntry(EVO_LEVEL, "26",
SPECIES_FLOATZEL)]}`. The dex needs that in two directions, keyed by the
snapshot's `chrooked_id` join key:

- forward `evolves_into` — the source's outgoing edges (branching-safe: Eevee
  has many), each `{to, to_name, method}`.
- backward `evolution.from` — the INVERSE: each target's single pre-evolution
  `{from, from_name, method}`. A species has at most one pre-evo in practice;
  if two sources somehow point at the same target, we pick deterministically
  (first by `chrooked_id`) so the snapshot stays byte-stable.

`SPECIES_*` is resolved to `(chrooked_id, display_name)` by a caller-supplied
resolver (`build_snapshot` already has the name maps), keeping this transform
pure and unit-testable with no base checkout.
"""

from __future__ import annotations

from typing import Any, Callable

from ..readers.pokeemerald.evolution_parser import EvolutionEntry

# A resolver maps a `SPECIES_*` symbol to its `(chrooked_id, display_name, dex)`,
# or None when the species is absent from the snapshot (e.g. a dropped Gmax
# form). `dex` lets the UI resolve a cross-link sprite for base species, which
# the sprite-id form map keys only forms; it may be None for a numberless form.
SpeciesResolver = Callable[[str], "tuple[str, str, int | None] | None"]


def method_label(method: str, param: str) -> str:
    """A human-readable evolution method from the engine `(EVO_*, param)` pair.

    Maps the common kinds to a clean label; anything unmodeled falls back to a
    humanized form of the constant plus its param, so no edge ever renders a raw
    `EVO_*` token. Examples:

    - `EVO_LEVEL` / `26`            -> "Level 26"
    - `EVO_ITEM` / `ITEM_FIRE_STONE` -> "Fire Stone"
    - `EVO_FRIENDSHIP` / anything   -> "Friendship"
    - `EVO_TRADE` / anything        -> "Trade"
    - `EVO_LEVEL_NINJASK` / `20`    -> "Level Ninjask 20" (humanized fallback)
    """
    if method == "EVO_LEVEL" and param.isdigit():
        return f"Level {param}"
    if method in _LEVELLESS_LABELS:
        return _LEVELLESS_LABELS[method]
    if method == "EVO_ITEM" or (param.startswith("ITEM_")):
        return _humanize_item(param)
    if method in _PARAM_LABELS:
        return _PARAM_LABELS[method].format(_humanize_param(param))
    return _humanize_fallback(method, param)


# Methods whose param is a sentinel (0/level), so only the kind is meaningful.
_LEVELLESS_LABELS = {
    "EVO_FRIENDSHIP": "Friendship",
    "EVO_FRIENDSHIP_DAY": "Friendship (Day)",
    "EVO_FRIENDSHIP_NIGHT": "Friendship (Night)",
    "EVO_TRADE": "Trade",
    "EVO_LEVEL_DAY": "Level (Day)",
    "EVO_LEVEL_NIGHT": "Level (Night)",
}


# Param-bearing methods that read cleanly with a tailored phrasing — keeps the
# param's own namespace word (Map/Type/Move) from doubling the method label
# (e.g. EVO_SPECIFIC_MAP + MAP_PETALBURG_WOODS must not read "Specific Map Map …").
_PARAM_LABELS = {
    "EVO_SPECIFIC_MAP": "At {}",
    "EVO_MAPSEC": "In {}",
    "EVO_FRIENDSHIP_MOVE_TYPE": "Friendship + {} move",
    "EVO_MOVE_TYPE": "Knows a {} move",
    "EVO_MOVE": "Knows {}",
    "EVO_SPECIFIC_MON_IN_PARTY": "With {} in party",
}

# Param namespaces stripped before humanizing, so a param never echoes a word
# already carried by its method label.
_PARAM_NAMESPACES = ("MAP_", "TYPE_", "MOVE_", "ITEM_", "SPECIES_", "B_")


def _humanize_param(param: str) -> str:
    """`MAP_PETALBURG_WOODS` -> `Petalburg Woods`; `TYPE_FAIRY` -> `Fairy`."""
    cleaned = param
    for namespace in _PARAM_NAMESPACES:
        if cleaned.startswith(namespace):
            cleaned = cleaned.removeprefix(namespace)
            break
    return cleaned.replace("_", " ").title()


def _humanize_item(param: str) -> str:
    """`ITEM_FIRE_STONE` -> `Fire Stone`; a bare param passes through titled."""
    return param.removeprefix("ITEM_").replace("_", " ").title()


def _humanize_fallback(method: str, param: str) -> str:
    """`EVO_LEVEL_NINJASK` + `20` -> `Level Ninjask 20`. No raw token leaks."""
    label = method.removeprefix("EVO_").replace("_", " ").title()
    # A non-sentinel param (a number or symbol) is appended for context, with its
    # namespace prefix stripped so it never doubles a word already in the label.
    if param and param != "0":
        piece = param if param.isdigit() else _humanize_param(param)
        return f"{label} {piece}"
    return label


def build_evolution_graph(
    forward: dict[str, list[EvolutionEntry]],
    resolver: SpeciesResolver,
    labeler: Callable[[str, str], str] = method_label,
) -> dict[str, dict[str, Any]]:
    """Build per-species `evolution` (backward) + `evolves_into` (forward).

    Returns a dict keyed by `chrooked_id`; each value is
    `{"evolution": {from, from_name, method} | None, "evolves_into": [...]}`.
    Only species that participate in some edge appear — `build_snapshot` reads
    these back onto the matching species entries and leaves the rest untouched.
    Targets the resolver can't place are dropped (a half-edge is never emitted).

    `labeler` turns each `(method, param)` pair into a human-readable label. It
    defaults to the pokeemerald `method_label`, so existing callers are
    unchanged; the Essentials path injects `essentials_method_label` because its
    method vocabulary (`Level`/`Item`/…) is not the pokeemerald `EVO_*` one.
    """
    graph: dict[str, dict[str, Any]] = {}

    def slot(chrooked_id: str) -> dict[str, Any]:
        return graph.setdefault(chrooked_id, {"evolution": None, "evolves_into": []})

    # Walk sources sorted so the inverted `from` resolves deterministically when
    # two sources (pathologically) point at one target.
    for source_symbol in sorted(forward):
        source = resolver(source_symbol)
        if source is None:
            continue
        source_id, source_name, source_dex = source

        for entry in forward[source_symbol]:
            target = resolver(entry.target_species)
            if target is None:
                continue
            target_id, target_name, target_dex = target
            label = labeler(entry.method, entry.param)
            detail = {"kind": entry.method, "param": entry.param}

            slot(source_id)["evolves_into"].append(
                {
                    "to": target_id,
                    "to_name": target_name,
                    "to_dex": target_dex,
                    "method": label,
                    "method_detail": detail,
                }
            )

            # Inverse edge: only fill `from` once (first source wins, by sort).
            target_slot = slot(target_id)
            if target_slot["evolution"] is None:
                target_slot["evolution"] = {
                    "from": source_id,
                    "from_name": source_name,
                    "from_dex": source_dex,
                    "method": label,
                    "method_detail": detail,
                }

    return graph
