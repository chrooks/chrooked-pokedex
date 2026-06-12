"""The Canon dex merge: base snapshot ⊕ Ruleset overrides.

`build_dex` walks the full national dex from the snapshot and overlays each
matching `SpeciesOverride`, producing one merged entry per species plus an
`overridden_fields` list naming what the Ruleset changed. This merge is the
spine the read-only dex (Slice 1) and later the CRUD detail panel hang off.

Override semantics follow the schema:
- `types` and `learnset` are *whole-list* overrides — present means replace.
- `abilities` and `stats` are *partial* — changed slots/keys win, the rest of
  the base value shows through.
- `evolution` replaces the displayed evolution when present.
"""

from __future__ import annotations

from typing import Any

from ..model import Ruleset
from ..model.schema import AbilitiesOverride, SpeciesOverride

# Top-level species fields the dex flags as overridden, in display order.
_FLAGGABLE_FIELDS = ("types", "abilities", "stats", "learnset", "evolution")


def build_dex(snapshot: dict[str, Any], ruleset: Ruleset) -> list[dict[str, Any]]:
    """Merge the Ruleset onto every base species, sorted by national dex number."""
    entries = [
        _merge_species(base, ruleset.species.get(chrooked_id))
        for chrooked_id, base in snapshot["species"].items()
    ]
    return sorted(entries, key=_dex_sort_key)


def _dex_sort_key(entry: dict[str, Any]) -> tuple[int, str]:
    # National dex order; species without a number sort last, then by id for stability.
    dex = entry.get("dex")
    return (dex if dex is not None else 10**9, entry["chrooked_id"])


def _merge_species(
    base: dict[str, Any], override: SpeciesOverride | None
) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "dex": base.get("dex"),
        "chrooked_id": base["chrooked_id"],
        "name": base["name"],
        "types": list(base.get("types", [])),
        "abilities": dict(base.get("abilities", {})),
        "stats": dict(base.get("stats", {})),
        "learnset": list(base.get("learnset", [])),
        "evolution": None,
        "overridden_fields": [],
    }
    if override is None:
        return merged

    overridden: list[str] = []

    # `name` is always present on an override (schema type `str`, not Optional);
    # a rename simply replaces the base display name.
    merged["name"] = override.name

    if override.types is not None:
        merged["types"] = list(override.types)
        overridden.append("types")

    if override.abilities is not None:
        merged["abilities"] = _merge_abilities(merged["abilities"], override.abilities)
        overridden.append("abilities")

    if override.stats is not None:
        merged["stats"] = {**merged["stats"], **dict(override.stats)}
        overridden.append("stats")

    if override.learnset is not None:
        merged["learnset"] = [
            {"level": m.level, "move": m.move} for m in override.learnset
        ]
        overridden.append("learnset")

    if override.evolution is not None:
        merged["evolution"] = {
            "from": override.evolution.from_species,
            "method": dict(override.evolution.method),
        }
        overridden.append("evolution")

    merged["overridden_fields"] = [f for f in _FLAGGABLE_FIELDS if f in overridden]
    return merged


def _merge_abilities(
    base: dict[str, Any], override: AbilitiesOverride
) -> dict[str, str | None]:
    """Overlay only the slots the override actually sets; untouched slots persist."""
    merged = dict(base)
    for slot in ("primary", "secondary", "hidden"):
        value = getattr(override, slot)
        if value is not None:
            merged[slot] = value
    return merged
