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
from ..model.schema import AbilitiesOverride, AbilityDef, SpeciesOverride

# Top-level species fields the dex flags as overridden, in display order.
_FLAGGABLE_FIELDS = ("types", "abilities", "stats", "learnset", "evolution")

# Ability fields the merge diffs, in display order. `aka` rides along but is not
# a user-facing diff row, so it is not flagged.
_ABILITY_DIFF_FIELDS = ("name", "description")


def build_dex(snapshot: dict[str, Any], ruleset: Ruleset) -> list[dict[str, Any]]:
    """Merge the Ruleset onto every base species, sorted by national dex number."""
    entries = [
        _merge_species(base, ruleset.species.get(chrooked_id))
        for chrooked_id, base in snapshot["species"].items()
    ]
    return sorted(entries, key=_dex_sort_key)


def build_dex_entry(
    snapshot: dict[str, Any], ruleset: Ruleset, chrooked_id: str
) -> dict[str, Any] | None:
    """Merge one species by `chrooked_id`, or None if the base has no such species.

    Backs `GET /api/dex/{chrooked_id}` (the detail panel) without rebuilding the
    whole dex. The id is the snapshot's join key, so a miss means a 404.
    """
    base = snapshot["species"].get(chrooked_id)
    if base is None:
        return None
    return _merge_species(base, ruleset.species.get(chrooked_id))


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
        # A base fact (no outgoing evolution = final form or single-stage); the
        # Ruleset doesn't recompute it. Defaults False for an older snapshot that
        # predates the field. Drives the "Fully Evolved" class.
        "fully_evolved": bool(base.get("fully_evolved", False)),
        "overridden_fields": [],
        # Pre-override values for whatever the Ruleset changed, so the detail
        # ledger can show base -> now. Empty for an untouched species.
        "base": {},
    }
    if override is None:
        return merged

    overridden: list[str] = []
    base_values: dict[str, Any] = {}

    # `name` is always present on an override (schema type `str`, not Optional),
    # but only write it when it actually differs from base — so an override that
    # only touches stats can't silently clobber the display name. Renames are not
    # flagged in `overridden_fields` in M1 (the ledger has no name-diff row yet);
    # surfacing them is deferred to the CRUD slice.
    if override.name != base["name"]:
        merged["name"] = override.name

    if override.types is not None:
        base_values["types"] = list(merged["types"])
        merged["types"] = list(override.types)
        overridden.append("types")

    if override.abilities is not None:
        base_values["abilities"] = dict(merged["abilities"])
        merged["abilities"] = _merge_abilities(merged["abilities"], override.abilities)
        overridden.append("abilities")

    if override.stats is not None:
        base_values["stats"] = dict(merged["stats"])
        merged["stats"] = {**merged["stats"], **dict(override.stats)}
        overridden.append("stats")

    if override.learnset is not None:
        base_values["learnset"] = list(merged["learnset"])
        merged["learnset"] = [
            {"level": m.level, "move": m.move} for m in override.learnset
        ]
        overridden.append("learnset")

    if override.evolution is not None:
        # Base 1.11.2 snapshot carries no evolution, so there is no `was` to show;
        # the ledger renders this as Ruleset-set rather than a diff.
        merged["evolution"] = {
            "from": override.evolution.from_species,
            "method": dict(override.evolution.method),
        }
        overridden.append("evolution")

    merged["overridden_fields"] = [f for f in _FLAGGABLE_FIELDS if f in overridden]
    merged["base"] = {k: base_values[k] for k in _FLAGGABLE_FIELDS if k in base_values}
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


def build_abilities(snapshot: dict[str, Any], ruleset: Ruleset) -> list[dict[str, Any]]:
    """Merge the Ruleset's AbilityDefs onto the full base abilities, sorted by name.

    The abilities tab reaches species parity here: every base ability shows
    through (unflagged unless the Ruleset touches it), each Ruleset AbilityDef
    replaces the matching base entry and flags the changed fields with a base→now
    diff, and a Ruleset id with no base match surfaces as a created ability.
    Mirrors `build_dex` for species.
    """
    base_abilities: dict[str, dict[str, Any]] = snapshot.get("abilities", {})
    entries = [
        _merge_ability(base, ruleset.abilities.get(chrooked_id))
        for chrooked_id, base in base_abilities.items()
    ]
    # Ruleset ids with no base match are created abilities (new content).
    created_ids = set(ruleset.abilities) - set(base_abilities)
    entries.extend(
        _merge_ability(None, ruleset.abilities[chrooked_id])
        for chrooked_id in created_ids
    )
    return sorted(entries, key=lambda e: e["name"])


def _merge_ability(
    base: dict[str, Any] | None, override: AbilityDef | None
) -> dict[str, Any]:
    """One merged AbilityEntry: base ⊕ Ruleset def, with overridden_fields + base diff.

    Three cases:
    - base-only (override is None): pass the base through unflagged.
    - created (base is None): the Ruleset def's fields are all "provided"; there
      is nothing to diff against, so `base` stays empty.
    - overridden: the Ruleset def replaces the base entry; flag every field whose
      value actually differs, carrying the pre-override base value for the diff.
    """
    if override is None:
        # base is guaranteed present here (called over snapshot keys).
        assert base is not None
        return {
            "chrooked_id": base["chrooked_id"],
            "name": base["name"],
            "description": base.get("description", ""),
            "aka": dict(base.get("aka", {})),
            "overridden_fields": [],
            "base": {},
        }

    override_values = {"name": override.name, "description": override.description}

    if base is None:
        # Created: no base to diff against; the def provides every non-empty field.
        provided = [f for f in _ABILITY_DIFF_FIELDS if override_values[f] != ""]
        return {
            "chrooked_id": override.chrooked_id,
            "name": override.name,
            "description": override.description,
            "aka": dict(override.aka),
            "overridden_fields": provided,
            "base": {},
        }

    overridden: list[str] = []
    base_values: dict[str, Any] = {}
    for field_name in _ABILITY_DIFF_FIELDS:
        base_value = base.get(field_name, "")
        if override_values[field_name] != base_value:
            overridden.append(field_name)
            base_values[field_name] = base_value

    return {
        "chrooked_id": override.chrooked_id,
        "name": override.name,
        "description": override.description,
        # aka follows the Ruleset def when overridden so an edit round-trips it.
        "aka": dict(override.aka),
        "overridden_fields": overridden,
        "base": base_values,
    }
