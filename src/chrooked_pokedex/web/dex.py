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
from ..model.schema import (
    AbilitiesOverride,
    AbilityDef,
    MoveDef,
    SpeciesOverride,
    TypeChartOverride,
)

# Top-level species fields the dex flags as overridden, in display order.
_FLAGGABLE_FIELDS = ("types", "abilities", "stats", "learnset", "evolution")

# Ability fields the merge diffs, in display order. `aka` rides along but is not
# a user-facing diff row, so it is not flagged.
_ABILITY_DIFF_FIELDS = ("name", "description")

# Move fields the merge diffs, in display order. These are exactly the Ruleset-
# owned MoveDef fields (the writable set); `aka` rides along like abilities and
# is not a user-facing diff row, so it is not flagged.
_MOVE_DIFF_FIELDS = (
    "name",
    "type",
    "category",
    "power",
    "accuracy",
    "pp",
    "description",
    "effect",
    "argument",
    "additional_effects",
    "flags",
    "priority",
    "target",
)


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


def build_moves(snapshot: dict[str, Any], ruleset: Ruleset) -> list[dict[str, Any]]:
    """Merge the Ruleset's MoveDefs onto the full base moves, sorted by name.

    The moves tab reaches species parity here, exactly like `build_abilities`:
    every base move shows through (unflagged unless the Ruleset touches it), each
    Ruleset MoveDef replaces the matching base entry and flags the changed fields
    with a base→now diff, and a Ruleset id with no base match surfaces as a
    created move. The base values were neutralized in `build_snapshot`, so the
    merged entry is neutral end to end.
    """
    base_moves: dict[str, dict[str, Any]] = snapshot.get("moves", {})
    entries = [
        _merge_move(base, ruleset.moves.get(chrooked_id))
        for chrooked_id, base in base_moves.items()
    ]
    # Ruleset ids with no base match are created moves (new content).
    created_ids = set(ruleset.moves) - set(base_moves)
    entries.extend(
        _merge_move(None, ruleset.moves[chrooked_id]) for chrooked_id in created_ids
    )
    return sorted(entries, key=lambda e: e["name"])


def _move_override_values(override: MoveDef) -> dict[str, Any]:
    """The Ruleset MoveDef as the same JSON shapes the base snapshot stores.

    `argument` is a dict-or-None, `additional_effects` is a list of
    `{effect, chance}`, `flags` is a list — so a field-by-field comparison against
    the base entry is apples-to-apples (no dataclass-vs-dict false diffs).
    """
    return {
        "name": override.name,
        "type": override.type,
        "category": override.category,
        "power": override.power,
        "accuracy": override.accuracy,
        "pp": override.pp,
        "description": override.description,
        "effect": override.effect,
        "argument": dict(override.argument) if override.argument is not None else None,
        "additional_effects": [
            {"effect": ae.effect, "chance": ae.chance}
            for ae in override.additional_effects
        ],
        "flags": list(override.flags),
        "priority": override.priority,
        "target": override.target,
    }


def _move_entry_fields(values: dict[str, Any], chrooked_id: str, aka: dict) -> dict[str, Any]:
    """Assemble the contract MoveEntry body (sans merge fields) from field values."""
    return {
        "chrooked_id": chrooked_id,
        "aka": aka,
        **{field: values.get(field) for field in _MOVE_DIFF_FIELDS},
    }


def _merge_move(
    base: dict[str, Any] | None, override: MoveDef | None
) -> dict[str, Any]:
    """One merged MoveEntry: base ⊕ Ruleset def, with overridden_fields + base diff.

    Mirrors `_merge_ability`, three cases:
    - base-only (override is None): pass the base through unflagged.
    - created (base is None): the Ruleset def provides every field; nothing to
      diff against, so `base` stays empty and `overridden_fields` lists the fields
      the def actually sets (differing from the schema default).
    - overridden: the Ruleset def replaces the base entry; flag every field whose
      value differs, carrying the pre-override base value for the diff.
    """
    if override is None:
        # base is guaranteed present here (called over snapshot keys).
        assert base is not None
        return {
            **_move_entry_fields(base, base["chrooked_id"], dict(base.get("aka", {}))),
            "overridden_fields": [],
            "base": {},
        }

    override_values = _move_override_values(override)
    aka = dict(override.aka)

    if base is None:
        # Created: no base to diff against. Flag the fields the def sets to a
        # non-default value, so an inert created move (numbers only) isn't claimed
        # to override behavior fields it left at the schema default.
        defaults = _move_schema_defaults()
        provided = [
            field
            for field in _MOVE_DIFF_FIELDS
            if override_values[field] != defaults[field]
        ]
        return {
            **_move_entry_fields(override_values, override.chrooked_id, aka),
            "overridden_fields": provided,
            "base": {},
        }

    overridden: list[str] = []
    base_values: dict[str, Any] = {}
    for field in _MOVE_DIFF_FIELDS:
        base_value = base.get(field)
        if override_values[field] != base_value:
            overridden.append(field)
            base_values[field] = base_value

    return {
        **_move_entry_fields(override_values, override.chrooked_id, aka),
        "overridden_fields": overridden,
        "base": base_values,
    }


def build_type_chart(
    snapshot: dict[str, Any], ruleset: Ruleset
) -> list[dict[str, Any]]:
    """Merge the Ruleset's type-chart overrides onto the full base matrix.

    The type chart reaches canon parity here exactly like `build_abilities` /
    `build_moves`, but the merge unit is a single matrix CELL rather than a keyed
    entity. The base snapshot carries the FULL attacker×defender grid (every cell
    a concrete multiplier); each `TypeChartOverride` replaces the matching cell's
    multiplier and flags it `overridden` with the pre-override `base_multiplier`.

    Contract per cell:
    - non-overridden: `overridden=False`, `multiplier=<base>`, `base_multiplier=None`.
    - overridden:     `overridden=True`,  `multiplier=<ruleset>`,
                      `base_multiplier=<base>`.

    A Ruleset override that references a pair with no base cell ("created") emits
    a cell with `base_multiplier=None`; with the full base matrix this should not
    occur. The type universe + ordering derive from the base cells (sorted by
    `(attacker, defender)`) for a stable, deterministic grid.
    """
    base_cells: list[dict[str, Any]] = snapshot.get("type_chart", [])
    overrides: dict[tuple[str, str], TypeChartOverride] = {
        (entry.attacker, entry.defender): entry for entry in ruleset.type_chart
    }

    entries = [
        _merge_type_cell(cell, overrides.get((cell["attacker"], cell["defender"])))
        for cell in base_cells
    ]

    # Overrides referencing a pair absent from the base matrix are "created" cells.
    base_pairs = {(cell["attacker"], cell["defender"]) for cell in base_cells}
    created_pairs = sorted(set(overrides) - base_pairs)
    entries.extend(_merge_type_cell(None, overrides[pair]) for pair in created_pairs)

    return sorted(entries, key=lambda e: (e["attacker"], e["defender"]))


def _merge_type_cell(
    base: dict[str, Any] | None, override: TypeChartOverride | None
) -> dict[str, Any]:
    """One merged type-chart cell: base ⊕ Ruleset override.

    Three cases, mirroring `_merge_ability` / `_merge_move`:
    - base-only (override is None): pass the base multiplier through, unflagged.
    - created (base is None): no base cell to diff against, so `base_multiplier`
      stays None and the override's multiplier shows as overridden.
    - overridden: the override's multiplier replaces base; carry the pre-override
      base multiplier for the diff.
    """
    if override is None:
        # base is guaranteed present here (called over base cells).
        assert base is not None
        return {
            "attacker": base["attacker"],
            "defender": base["defender"],
            "multiplier": float(base["multiplier"]),
            "overridden": False,
            "base_multiplier": None,
        }

    # A YAML override `multiplier: 2` loads as int; coerce so every cell's
    # multiplier and base_multiplier are floats per the contract.
    base_multiplier = float(base["multiplier"]) if base is not None else None
    return {
        "attacker": override.attacker,
        "defender": override.defender,
        "multiplier": float(override.multiplier),
        "overridden": True,
        "base_multiplier": base_multiplier,
    }


def _move_schema_defaults() -> dict[str, Any]:
    """The MoveDef field defaults, in the base snapshot's JSON shapes.

    A created move with no base carries these as its "unset" baseline; only
    fields the Ruleset set away from a default count as provided/overridden. Name,
    type, and category are required (no default), so they always count when set.
    """
    return {
        "name": None,
        "type": None,
        "category": None,
        "power": None,
        "accuracy": None,
        "pp": None,
        "description": "",
        "effect": "hit",
        "argument": None,
        "additional_effects": [],
        "flags": [],
        "priority": 0,
        "target": "selected",
    }
