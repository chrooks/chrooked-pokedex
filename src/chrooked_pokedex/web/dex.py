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

import json
from pathlib import Path
from typing import Any, Mapping

from ..model import Ruleset
from ..model.evolution_methods import CANONICAL
from ..model.schema import (
    AbilitiesOverride,
    AbilityDef,
    EvolutionOverride,
    MoveDef,
    SpeciesOverride,
    TypeChartOverride,
)
from . import collections as colmod
from .evolution import method_label

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
    name_to_id = _name_to_id(snapshot)
    overrides_by_pre_evo = _index_overrides_by_pre_evo(snapshot, ruleset, name_to_id)
    entries = [
        _merge_species(
            base, ruleset.species.get(chrooked_id), snapshot, overrides_by_pre_evo, name_to_id
        )
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
    name_to_id = _name_to_id(snapshot)
    overrides_by_pre_evo = _index_overrides_by_pre_evo(snapshot, ruleset, name_to_id)
    return _merge_species(
        base, ruleset.species.get(chrooked_id), snapshot, overrides_by_pre_evo, name_to_id
    )


def resolve_form_id(snapshot: dict[str, Any], chrooked_id: str) -> str:
    """Map a Target-backdrop form id to its canon `chrooked_id`.

    The makeover operates on **canon** (base ⊕ Ruleset), where a regional form is
    a bare concatenated slug — `marowakalola`, `ponytagalar`. But a Rejuv/Essentials
    backdrop preview re-slugs non-base forms `<base>--<label slug>` (`marowak--
    alolanform`), so the workbench, launched from that preview, hands us an id canon
    doesn't have. This bridges it back, mirroring ``rekey_ruleset_to_rejuv`` inverted
    onto the canon id set: base + the form label's core, matched against canon ids
    that start with the base and whose suffix PREFIXES that core ("alola" ⊂ "alolan").

    Returns the input unchanged when it already resolves directly, carries no `--`,
    or is ambiguous — so a genuinely unknown id still yields the caller's honest 404,
    never a silent wrong match.
    """
    from ..appliers.rejuv.resolution import _form_core

    species = snapshot.get("species", {})
    if chrooked_id in species or "--" not in chrooked_id:
        return chrooked_id
    base, _, form_slug = chrooked_id.partition("--")
    core = _form_core(form_slug)
    if not core:
        return chrooked_id
    candidates = [
        cid
        for cid in species
        if cid != base and cid.startswith(base) and core.startswith(cid[len(base):])
    ]
    if not candidates:
        return chrooked_id
    best = max(candidates, key=len)
    if sum(1 for cid in candidates if len(cid) == len(best)) > 1:
        return chrooked_id  # ambiguous — leave unresolved rather than guess a form
    return best


def _name_to_id(snapshot: dict[str, Any]) -> dict[str, str]:
    """Display name -> `chrooked_id`, the join a Ruleset evolution override needs.

    An `EvolutionOverride` names its pre-evo by display name ("Dusclops"); every
    other edge in the dex is keyed by `chrooked_id`. Built once per request and
    handed to both consumers so neither rebuilds it per species.
    """
    return {base["name"]: cid for cid, base in snapshot["species"].items()}


def _index_overrides_by_pre_evo(
    snapshot: dict[str, Any], ruleset: Ruleset, name_to_id: dict[str, str]
) -> dict[str, list[tuple[str, SpeciesOverride]]]:
    """Ruleset `evolution` overrides, indexed by the pre-evo's `chrooked_id`.

    An `EvolutionOverride` lives on the evolved-into species and names its
    pre-evo by display name (`from_species`), not `chrooked_id` — so patching
    the pre-evo's forward `evolves_into` means resolving that name once, then
    grouping every override that points back at it. Without this, a level
    edited via the pre-evo's "evolves into" card only ever updates the
    evolved species' own backward `evolution`; the pre-evo's forward edge
    keeps showing the frozen base value forever.
    """
    index: dict[str, list[tuple[str, SpeciesOverride]]] = {}
    for target_id, override in ruleset.species.items():
        if override.evolution is None or override.evolution.from_species is None:
            continue
        # An override whose own species isn't in this snapshot can't produce a
        # real forward edge — skip it. The Rejuv/Essentials form rekey ADDS a form
        # id (`braviary--hisuianform`) without dropping the original canon id
        # (`braviaryhisui`), so both survive in `ruleset.species`; without this
        # guard the shared pre-evo splices a phantom duplicate edge keyed by the
        # dead canon id (to_dex null) — two "Braviary Hisui" cards on Rufflet.
        if target_id not in snapshot["species"]:
            continue
        from_id = name_to_id.get(override.evolution.from_species)
        if from_id is None:
            continue
        index.setdefault(from_id, []).append((target_id, override))
    return index


def _resolved_evolution_method(method: Mapping[str, Any]) -> tuple[str, dict[str, str]]:
    """A Ruleset evolution-override method dict as (display string, method_detail).

    Mirrors the base snapshot's own `evolves_into` shape (`method_label` +
    `{kind, param}`) so a Ruleset-authored forward edge reads and edits
    identically to a base-derived one. Covers the three shapes
    `EvolutionOverride.method` can take: the clean `level`/`item` dicts, a
    canonical `{method: id, param?}`, and the raw `{pokeemerald|essentials:
    token, param?}` escape.
    """
    if "level" in method:
        param = str(method["level"])
        return method_label("EVO_LEVEL", param), {"kind": "EVO_LEVEL", "param": param}
    if "item" in method:
        item = str(method["item"])
        return method_label("EVO_ITEM", item), {"kind": "EVO_ITEM", "param": item}
    if "method" in method:
        canonical = CANONICAL.get(str(method["method"]))
        token = canonical.pokeemerald if canonical is not None else str(method["method"])
        param = str(method.get("param", ""))
        return method_label(token, param), {"kind": token, "param": param}
    token = str(method.get("pokeemerald") or method.get("essentials") or "")
    param = str(method.get("param", ""))
    return method_label(token, param), {"kind": token, "param": param}


def _dex_sort_key(entry: dict[str, Any]) -> tuple[int, str]:
    # National dex order; species without a number sort last, then by id for stability.
    dex = entry.get("dex")
    return (dex if dex is not None else 10**9, entry["chrooked_id"])


def _merge_species(
    base: dict[str, Any],
    override: SpeciesOverride | None,
    snapshot: dict[str, Any],
    overrides_by_pre_evo: dict[str, list[tuple[str, SpeciesOverride]]],
    name_to_id: dict[str, str],
) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "dex": base.get("dex"),
        "chrooked_id": base["chrooked_id"],
        "name": base["name"],
        "types": list(base.get("types", [])),
        "abilities": dict(base.get("abilities", {})),
        "stats": dict(base.get("stats", {})),
        "learnset": list(base.get("learnset", [])),
        # The base evolution graph flows through, then any Ruleset override
        # authored on a CHILD species (an `evolution` override) is spliced into
        # this species' forward `evolves_into` below — so both directions of
        # the same edge always agree, however they were edited.
        "evolution": _copy_evolution(base.get("evolution")),
        "evolves_into": _forward_edges(
            base, snapshot, overrides_by_pre_evo.get(base["chrooked_id"], [])
        ),
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
        # Override precedence: the Ruleset's pre-evo replaces the base `from`. The
        # base value (if any) rides along under `base` for the diff toggle.
        if merged["evolution"] is not None:
            base_values["evolution"] = _copy_evolution(merged["evolution"])
        merged["evolution"] = _backward_edge(override.evolution, snapshot, name_to_id)
        overridden.append("evolution")

    # Design metadata: flavor coverage types (Ruleset-only — the base never has
    # them, so no base→now diff row; the learnset skeleton reads them).
    if override.flavor_types is not None:
        merged["flavor_types"] = list(override.flavor_types)

    merged["overridden_fields"] = [f for f in _FLAGGABLE_FIELDS if f in overridden]
    merged["base"] = {k: base_values[k] for k in _FLAGGABLE_FIELDS if k in base_values}
    return merged


def _backward_edge(
    evolution: EvolutionOverride, snapshot: dict[str, Any], name_to_id: dict[str, str]
) -> dict[str, Any]:
    """A Ruleset backward edge in the same shape a base-derived one has.

    The override names its pre-evo by display name and carries a raw method
    dict; a base edge carries `chrooked_id` + `from_name`/`from_dex` + a
    readable method. Resolving here (the mirror of `_forward_edges`) is what
    lets the ledger draw the pre-evo's portrait and cross-link for an
    override-authored evolution instead of dropping to a bare-name fallback.
    An unresolvable name (a species outside this snapshot) keeps the raw shape.
    """
    from_name = evolution.from_species
    method, method_detail = _resolved_evolution_method(evolution.method)
    from_id = name_to_id.get(from_name or "")
    if from_name is None or from_id is None:
        return {"from": from_name, "method": dict(evolution.method)}
    return {
        "from": from_id,
        "from_name": from_name,
        "from_dex": snapshot["species"].get(from_id, {}).get("dex"),
        "method": method,
        "method_detail": method_detail,
    }


def _copy_evolution(evolution: dict[str, Any] | None) -> dict[str, Any] | None:
    """A shallow copy of a base/merged `evolution` dict (or None passthrough).

    Keeps the merge immutable: the dex entry never aliases the snapshot's dict,
    so a later override that replaces `evolution` can't mutate the shared base.
    """
    return dict(evolution) if evolution is not None else None


def _forward_edges(
    base: dict[str, Any],
    snapshot: dict[str, Any],
    pre_evo_overrides: list[tuple[str, SpeciesOverride]],
) -> list[dict[str, Any]]:
    """This species' `evolves_into`: base-derived, with Ruleset overrides spliced in.

    `pre_evo_overrides` is this species' entry in `_index_overrides_by_pre_evo` —
    every override elsewhere in the Ruleset that names this species as its
    pre-evo. Each one replaces (or adds) the matching edge with the override's
    real method, keyed by the evolved species' `chrooked_id` so branching
    (Eevee-style) targets don't collide.
    """
    edges = {edge["to"]: dict(edge) for edge in base.get("evolves_into", [])}
    for target_id, override in pre_evo_overrides:
        assert override.evolution is not None  # guaranteed by the index
        method, method_detail = _resolved_evolution_method(override.evolution.method)
        edges[target_id] = {
            "to": target_id,
            "to_name": override.name,
            "to_dex": snapshot["species"].get(target_id, {}).get("dex"),
            "method": method,
            "method_detail": method_detail,
        }
    return list(edges.values())


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
    # `custom` marks net-new abilities (a merely rebalanced canon ability is NOT
    # custom), mirroring `build_move_pool` — the suggest pool tags them so the
    # model can see them among ~300 canon names.
    entries = [
        {**entry, "custom": entry["chrooked_id"] in created_ids} for entry in entries
    ]
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
            # A base-only ability has no composition — the snapshot has no such
            # concept, so it always uses its own behavior.
            "behaviors": [],
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
            "behaviors": list(override.behaviors),
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
        # Likewise behaviors: without this an edit through the dex would reset a
        # composed ability to "its own behavior" without anyone asking it to.
        "behaviors": list(override.behaviors),
        "overridden_fields": overridden,
        "base": base_values,
    }


def build_statuses(ruleset: Ruleset) -> list[dict[str, Any]]:
    """The Ruleset's status conditions, sorted by name.

    No merge step and no snapshot argument, unlike `build_abilities` / `build_moves`:
    statuses are Ruleset-owned outright rather than Overrides, because the base
    snapshot carries no status data to diff against — upstream has no such concept.
    Every entry is therefore "created" and nothing can be flagged as changed.
    """
    return sorted(
        (colmod.serialize_status(status) for status in ruleset.statuses.values()),
        key=lambda e: e["name"],
    )


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


# The MoveEntry contract types these as non-null lists. A per-Target snapshot
# reader (e.g. the Essentials reader) may leave them None; coerce here — the one
# chokepoint every move-merge path flows through — so canon /api/moves AND every
# Target backdrop honor the contract instead of shipping `flags: null` (which
# crashes the frontend's `move.flags.length`).
_MOVE_LIST_FIELDS = ("flags", "additional_effects")


def _move_entry_fields(values: dict[str, Any], chrooked_id: str, aka: dict) -> dict[str, Any]:
    """Assemble the contract MoveEntry body (sans merge fields) from field values."""
    body = {field: values.get(field) for field in _MOVE_DIFF_FIELDS}
    for field in _MOVE_LIST_FIELDS:
        if body.get(field) is None:
            body[field] = []
    return {
        "chrooked_id": chrooked_id,
        "aka": aka,
        **body,
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


def build_type_pool(snapshot: dict[str, Any], ruleset: Ruleset) -> list[str]:
    """The distinct type universe from the merged type chart, sorted deterministically.

    Collects every type name that appears as an attacker or defender in the merged
    type chart and returns a sorted, deduplicated list. This is the real, current
    type universe (base ⊕ Ruleset), exactly like `build_abilities` is for abilities.
    The suggest capability picks only from this list; a hallucinated type is a
    `SuggestError`. Sorting makes the list cache-stable across equal Rulesets.
    """
    cells = build_type_chart(snapshot, ruleset)
    names: set[str] = set()
    for cell in cells:
        names.add(cell["attacker"])
        names.add(cell["defender"])
    return sorted(names)


def build_move_pool(snapshot: dict[str, Any], ruleset: Ruleset) -> list[dict[str, Any]]:
    """The compact move pool the model picks learnset moves from.

    Built from the merged moves collection (``build_moves``) so it is the real,
    current set (base ⊕ Ruleset): an edited move shows its new type/power, and a
    created move is present. Each row carries only the fields the learnset rubric
    needs — name, type, category, power, accuracy, `pp`, a short effect string,
    the engine-neutral `flags`, a `secondary` bool (any additional effect), and a
    `custom` flag marking net-new created moves (a Ruleset id with no base entry;
    a merely rebalanced canon move is NOT custom). Flags/secondary/accuracy feed
    the ability-fuel slot filters (ability_fuel.json) — an -ate or sound-booster
    slot gates on them. Null base powers the vendored parser skipped are
    backfilled from the canon table so the model's power/pacing reasoning and
    ability shortlists see real BP. Sorted by name for a deterministic,
    cache-stable prefix. Rows without a name are dropped.
    """
    all_moves = build_moves(snapshot, ruleset)
    created_ids = set(ruleset.moves) - set(snapshot.get("moves", {}))
    pool = [
        {
            "move": entry["name"],
            "type": entry.get("type") or "",
            "category": entry.get("category") or "",
            "power": _pool_power(entry),
            "accuracy": entry.get("accuracy"),
            "pp": entry.get("pp"),
            "effect": entry.get("effect") or "",
            "flags": list(entry.get("flags") or ()),
            "secondary": bool(entry.get("additional_effects")),
            # The utility grader reads target (spread) and additional_effects
            # (the 100%-status classifier); without them a spread status move
            # grades as single-target and Nuzzle reads as an attacking rung.
            "target": entry.get("target") or "",
            "additional_effects": [
                dict(e) if isinstance(e, dict) else
                {"effect": getattr(e, "effect", None), "chance": getattr(e, "chance", None)}
                for e in (entry.get("additional_effects") or ())
            ],
            "chrooked_id": entry.get("chrooked_id"),
            "custom": entry["chrooked_id"] in created_ids,
        }
        for entry in all_moves
        if entry.get("name")
    ]
    return sorted(pool, key=lambda row: row["move"])


def _pool_power(entry: dict[str, Any]) -> Any:
    """Resolved power for a pool row.

    This used to backfill from a hand-kept canon table, because the move parser
    read only a bare literal and left 104 gen-gated powers null. The parser now
    resolves those ternaries, so the base carries the real number and the table
    is gone — it had already drifted from the source on two entries.

    A variable-power move reads 1 in the source (not 0); callers that must not
    show a number treat <= 1 as "no fixed BP".
    """
    return entry.get("power")


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
