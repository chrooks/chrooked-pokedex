"""Compose a base Ruleset with a Target Override overlay into one effective Ruleset.

A Target can re-theme an entry the base Ruleset already owns — Africanvs's
Kricketune is the one KRICKETUNE slot wearing Gaul flavor, not a second creature.
The overlay (loaded from `ruleset/targets/<slug>/`) is layered on top of the base,
last-wins per field, and the result is a plain `Ruleset` the existing dex-merge and
appliers consume unchanged.

Per-collection composition rules:

- species: field-level merge (overrides are partial). See `compose_species_override`.
- moves / abilities / behaviors: whole-entity — the overlay entry replaces the base
  entry for that `chrooked_id`. These are stored whole in the Ruleset, not field-diffed.
- type_chart: merge by `(attacker, defender)` cell; the overlay cell wins.
- meta / base_species: kept from the base; the overlay's are namespace bookkeeping.
"""

from __future__ import annotations

from typing import Mapping, Optional

from .ruleset import Ruleset
from .schema import (
    AbilitiesOverride,
    SpeciesOverride,
    TypeChartOverride,
)


def compose_ruleset(base: Ruleset, overlay: Optional[Ruleset]) -> Ruleset:
    """Return base with overlay layered on top. An empty/None overlay returns base.

    The result is a new frozen `Ruleset`; neither input is mutated.
    """
    if overlay is None:
        return base

    species = dict(base.species)
    for chrooked_id, over in overlay.species.items():
        species[chrooked_id] = compose_species_override(base.species.get(chrooked_id), over)

    moves = {**base.moves, **overlay.moves}
    abilities = {**base.abilities, **overlay.abilities}
    behaviors = {**base.behaviors, **overlay.behaviors}
    type_chart = _compose_type_chart(base.type_chart, overlay.type_chart)

    return Ruleset(
        species=species,
        moves=moves,
        abilities=abilities,
        type_chart=type_chart,
        behaviors=behaviors,
        meta=base.meta,
        base_species=base.base_species,
    )


def compose_species_override(
    base: Optional[SpeciesOverride], overlay: SpeciesOverride
) -> SpeciesOverride:
    """Layer an overlay species override on top of a base one, per field.

    A field set on the overlay (not None) wins; otherwise the base's value
    survives. `stats` is merged key-wise (partial dict spread, like the dex merge);
    `abilities` is merged slot-by-slot; `types`, `learnset`, and `evolution` are
    whole-field replaces. When `base` is None the overlay stands alone.
    """
    if base is None:
        return overlay

    return SpeciesOverride(
        name=overlay.name,
        chrooked_id=overlay.chrooked_id,
        aka={**dict(base.aka), **dict(overlay.aka)},
        types=overlay.types if overlay.types is not None else base.types,
        abilities=_compose_abilities(base.abilities, overlay.abilities),
        stats=_compose_stats(base.stats, overlay.stats),
        learnset=overlay.learnset if overlay.learnset is not None else base.learnset,
        evolution=overlay.evolution if overlay.evolution is not None else base.evolution,
    )


def overlay_touched_fields(overlay: SpeciesOverride) -> set[str]:
    """The set of species fields this overlay actually sets (for the target badge).

    Used by the dex read to mark which merged fields came from the Target Override
    layer versus the base. `name` is excluded — it is always present and never
    flagged as an override in the dex.
    """
    touched: set[str] = set()
    if overlay.types is not None:
        touched.add("types")
    if overlay.abilities is not None:
        touched.add("abilities")
    if overlay.stats is not None:
        touched.add("stats")
    if overlay.learnset is not None:
        touched.add("learnset")
    if overlay.evolution is not None:
        touched.add("evolution")
    return touched


def _compose_abilities(
    base: Optional[AbilitiesOverride], overlay: Optional[AbilitiesOverride]
) -> Optional[AbilitiesOverride]:
    if overlay is None:
        return base
    if base is None:
        return overlay
    return AbilitiesOverride(
        primary=overlay.primary if overlay.primary is not None else base.primary,
        secondary=overlay.secondary if overlay.secondary is not None else base.secondary,
        hidden=overlay.hidden if overlay.hidden is not None else base.hidden,
    )


def _compose_stats(
    base: Optional[Mapping[str, int]], overlay: Optional[Mapping[str, int]]
) -> Optional[Mapping[str, int]]:
    if base is None and overlay is None:
        return None
    return {**dict(base or {}), **dict(overlay or {})}


def _compose_type_chart(
    base: tuple[TypeChartOverride, ...], overlay: tuple[TypeChartOverride, ...]
) -> tuple[TypeChartOverride, ...]:
    by_key: dict[tuple[str, str], TypeChartOverride] = {
        (cell.attacker, cell.defender): cell for cell in base
    }
    for cell in overlay:
        by_key[(cell.attacker, cell.defender)] = cell
    return tuple(by_key.values())
