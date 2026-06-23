"""Write layer for the three simple-record Ruleset kinds (Milestone 2, slice 2a):
species Overrides, owned moves, owned abilities.

Every write runs one pipeline: build the dataclass from the request payload,
render canonical YAML via `seed.writer`, then *reload that YAML through the
loader* — the single validation Boundary — before it lands on disk. A rejected
edit raises `ValidationError` (the route maps it to HTTP 422 with the loader's
own message) and **nothing is written**: the staged file never replaces the real
one. The UI never touches git; Chris reviews `git diff` and commits.

Deleting an owned move or ability a species still cites is blocked
(`CitationError` → HTTP 409) until the caller confirms, so a reference can't be
silently orphaned — left in place it would report `partial` on the next apply.
Deleting a species Override just removes its file (the dex reverts to base).
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from ..model import Ruleset
from ..model.behavior_spec import BehaviorEffect, BehaviorSpec, BehaviorTestCase
from ..model.loader import (
    load_ability,
    load_behavior,
    load_move,
    load_species,
    load_type_chart,
)
from ..model.schema import (
    AbilitiesOverride,
    AbilityDef,
    AdditionalEffect,
    EvolutionOverride,
    LearnsetMove,
    MoveDef,
    SpeciesOverride,
    TypeChartOverride,
)
from ..seed import writer
from . import collections as colmod


class ValidationError(Exception):
    """A write was rejected by the loader Boundary (→ HTTP 422). Nothing wrote."""


class NotFoundError(Exception):
    """A delete targeted a file that does not exist (→ HTTP 404)."""


class CitationError(Exception):
    """A delete would orphan a still-cited reference (→ HTTP 409) without confirm."""

    def __init__(self, message: str, citing: list[str]) -> None:
        super().__init__(message)
        self.citing = citing


# --------------------------------------------------------------------------- #
# Edit scope: base Ruleset vs a per-Target override namespace
# --------------------------------------------------------------------------- #


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def resolve_scope_dir(
    ruleset_dir: Path,
    scope: Optional[str],
    *,
    engine: Optional[str] = None,
    label: Optional[str] = None,
) -> Path:
    """Map an edit scope to the directory writes should land in.

    ``"base"`` (or empty/None) → the base ``ruleset_dir`` itself, exactly as
    today. ``"target:<slug>"`` → ``ruleset_dir/targets/<slug>``, the committed
    Target Override namespace; the namespace's ``meta.yaml`` is created on first
    write (carrying ``slug`` plus ``engine``/``label`` when known) so the folder
    is self-describing in git. A malformed scope or slug raises
    ``ValidationError`` (→ 422), never writes.
    """
    ruleset_dir = Path(ruleset_dir)
    if scope in (None, "", "base"):
        return ruleset_dir
    if not scope.startswith("target:"):
        raise ValidationError(
            f"Unknown edit scope {scope!r}; expected 'base' or 'target:<slug>'."
        )
    slug = scope.split(":", 1)[1].strip()
    if not _SLUG_RE.match(slug):
        raise ValidationError(
            f"Invalid target slug {slug!r}; use lowercase letters, digits, and hyphens."
        )
    namespace_dir = ruleset_dir / "targets" / slug
    meta_path = namespace_dir / "meta.yaml"
    if not meta_path.exists():
        namespace_dir.mkdir(parents=True, exist_ok=True)
        meta: dict[str, str] = {"slug": slug}
        if engine:
            meta["engine"] = engine
        if label:
            meta["label"] = label
        meta_path.write_text(yaml.safe_dump(meta, sort_keys=True), encoding="utf-8")
    return namespace_dir


# --------------------------------------------------------------------------- #
# The validate-then-write core
# --------------------------------------------------------------------------- #


def _validated_write(
    final_path: Path, yaml_text: str, validate: Callable[[Path], Any]
) -> Any:
    """Write `yaml_text` to `final_path` only if the loader accepts it.

    Staging happens in a temp directory *inside the target's parent* so the
    final move is an atomic same-filesystem rename, and the staged file keeps
    the real name (`goodra.yaml`) — so the loader's error messages name the file
    the user sees, not a temp path. On any validation failure nothing replaces
    the real file and the loader's `ValueError` is re-raised as `ValidationError`.
    Returns the validated dataclass so the caller serializes exactly what landed
    without a second disk read.
    """
    final_path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=final_path.parent, prefix=".staging-"))
    try:
        staged = staging / final_path.name
        staged.write_text(yaml_text, encoding="utf-8")
        try:
            result = validate(staged)
        except (ValueError, KeyError, TypeError) as error:
            raise ValidationError(str(error)) from error
        os.replace(staged, final_path)
        return result
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _check_id(payload: dict[str, Any], chrooked_id: str, where: str) -> None:
    body_id = payload.get("chrooked_id")
    if body_id is not None and body_id != chrooked_id:
        raise ValidationError(
            f"{where}: chrooked_id {body_id!r} in the body does not match "
            f"{chrooked_id!r} in the path."
        )


def _require(payload: dict[str, Any], key: str, where: str) -> Any:
    value = payload.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{where}: missing required field {key!r}.")
    return value


# --------------------------------------------------------------------------- #
# Species
# --------------------------------------------------------------------------- #


def _species_from_payload(payload: dict[str, Any], chrooked_id: str) -> SpeciesOverride:
    where = f"{chrooked_id}.yaml"
    _check_id(payload, chrooked_id, where)
    name = _require(payload, "name", where)

    abilities = None
    if payload.get("abilities") is not None:
        ab = payload["abilities"]
        abilities = AbilitiesOverride(
            primary=ab.get("primary"),
            secondary=ab.get("secondary"),
            hidden=ab.get("hidden"),
        )

    learnset = None
    if payload.get("learnset") is not None:
        learnset = tuple(
            LearnsetMove(level=entry["level"], move=entry["move"])
            for entry in payload["learnset"]
        )

    evolution = None
    if payload.get("evolution") is not None:
        evo = payload["evolution"]
        evolution = EvolutionOverride(
            from_species=evo.get("from"),
            method=dict(evo.get("method") or {}),
        )

    types = tuple(payload["types"]) if payload.get("types") is not None else None
    stats = dict(payload["stats"]) if payload.get("stats") is not None else None

    return SpeciesOverride(
        name=name,
        chrooked_id=chrooked_id,
        aka=dict(payload.get("aka") or {}),
        types=types,
        abilities=abilities,
        stats=stats,
        learnset=learnset,
        evolution=evolution,
    )


_SPECIES_FIELDS = (
    "name", "chrooked_id", "aka", "types",
    "abilities", "stats", "learnset", "evolution",
)


def upsert_species(ruleset_dir: Path, chrooked_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate-write a species Override; returns the raw Override as JSON."""
    _reject_unknown(payload, _SPECIES_FIELDS, f"{chrooked_id}.yaml")
    try:
        override = _species_from_payload(payload, chrooked_id)
        yaml_text = writer.species_yaml(override)
    except (KeyError, TypeError) as error:
        raise ValidationError(f"{chrooked_id}.yaml: malformed payload ({error}).") from error
    path = Path(ruleset_dir) / "species" / f"{chrooked_id}.yaml"
    return serialize_species(_validated_write(path, yaml_text, load_species))


def delete_species(ruleset_dir: Path, chrooked_id: str) -> None:
    path = Path(ruleset_dir) / "species" / f"{chrooked_id}.yaml"
    if not path.exists():
        raise NotFoundError(f"No species Override {chrooked_id!r} to delete.")
    path.unlink()


def serialize_species(species: SpeciesOverride) -> dict[str, Any]:
    """The raw Override as JSON (overrides-only) — what the species editor loads
    so a save round-trips exactly the changed fields, never base values."""
    return {
        "name": species.name,
        "chrooked_id": species.chrooked_id,
        "aka": dict(species.aka),
        "types": list(species.types) if species.types is not None else None,
        "abilities": (
            {
                "primary": species.abilities.primary,
                "secondary": species.abilities.secondary,
                "hidden": species.abilities.hidden,
            }
            if species.abilities is not None
            else None
        ),
        "stats": dict(species.stats) if species.stats is not None else None,
        "learnset": (
            [{"level": m.level, "move": m.move} for m in species.learnset]
            if species.learnset is not None
            else None
        ),
        "evolution": (
            {"from": species.evolution.from_species, "method": dict(species.evolution.method)}
            if species.evolution is not None
            else None
        ),
    }


# --------------------------------------------------------------------------- #
# Moves
# --------------------------------------------------------------------------- #


def _move_from_payload(payload: dict[str, Any], chrooked_id: str) -> MoveDef:
    where = f"{chrooked_id}.yaml"
    _check_id(payload, chrooked_id, where)
    name = _require(payload, "name", where)
    move_type = _require(payload, "type", where)
    category = _require(payload, "category", where)

    additional = tuple(
        # Pass through unchanged; the loader validates shape on reload.
        _additional_effect(entry) for entry in (payload.get("additional_effects") or [])
    )
    return MoveDef(
        name=name,
        chrooked_id=chrooked_id,
        type=move_type,
        category=category,
        power=payload.get("power"),
        accuracy=payload.get("accuracy"),
        pp=payload.get("pp"),
        description=payload.get("description", ""),
        aka=dict(payload.get("aka") or {}),
        effect=payload.get("effect", "hit"),
        argument=dict(payload["argument"]) if payload.get("argument") else None,
        additional_effects=additional,
        flags=tuple(payload.get("flags") or ()),
        priority=int(payload.get("priority", 0)),
        target=payload.get("target", "selected"),
    )


def _additional_effect(entry: dict[str, Any]) -> AdditionalEffect:
    return AdditionalEffect(effect=entry["effect"], chance=int(entry["chance"]))


_MOVE_FIELDS = (
    "name", "chrooked_id", "aka", "type",
    "category", "power", "accuracy", "pp", "description",
    "effect", "argument", "additional_effects", "flags", "priority", "target",
)


def upsert_move(ruleset_dir: Path, chrooked_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate-write an owned move; returns the move as JSON."""
    _reject_unknown(payload, _MOVE_FIELDS, f"{chrooked_id}.yaml")
    try:
        move = _move_from_payload(payload, chrooked_id)
        yaml_text = writer.move_yaml(move)
    except (KeyError, TypeError, ValueError) as error:
        # _require/_check_id raise ValidationError (not a ValueError), so they
        # propagate unwrapped; this catches only payload-shape errors.
        raise ValidationError(f"{chrooked_id}.yaml: malformed payload ({error}).") from error
    path = Path(ruleset_dir) / "moves" / f"{chrooked_id}.yaml"
    return colmod.serialize_move(_validated_write(path, yaml_text, load_move))


def delete_move(
    ruleset: Ruleset, ruleset_dir: Path, chrooked_id: str, *, confirm: bool = False
) -> None:
    move = ruleset.moves.get(chrooked_id)
    if move is None:
        raise NotFoundError(f"No owned move {chrooked_id!r} to delete.")
    citing = move_citations(ruleset, move)
    if citing and not confirm:
        raise CitationError(
            f"{move.name} is cited by {len(citing)} learnset(s); "
            "confirm to delete and leave those references dangling.",
            citing,
        )
    (Path(ruleset_dir) / "moves" / f"{chrooked_id}.yaml").unlink()


def move_citations(ruleset: Ruleset, move: MoveDef) -> list[str]:
    """Species whose learnset cites this move (by display name or chrooked_id)."""
    keys = {move.chrooked_id.lower(), move.name.strip().lower()}
    citing = [
        species.name
        for species in ruleset.species.values()
        if species.learnset is not None
        and any(entry.move.strip().lower() in keys for entry in species.learnset)
    ]
    return sorted(set(citing))


# --------------------------------------------------------------------------- #
# Abilities
# --------------------------------------------------------------------------- #


def _ability_from_payload(payload: dict[str, Any], chrooked_id: str) -> AbilityDef:
    where = f"{chrooked_id}.yaml"
    _check_id(payload, chrooked_id, where)
    name = _require(payload, "name", where)
    return AbilityDef(
        name=name,
        chrooked_id=chrooked_id,
        description=payload.get("description", ""),
        aka=dict(payload.get("aka") or {}),
    )


def upsert_ability(ruleset_dir: Path, chrooked_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Build, render, and validate-write an owned ability.

    The payload is rendered as-is so the loader catches unknown fields — but the
    writer only emits known fields, so an extra key in the body would be
    silently dropped on a pure render. To keep the loader as the real Boundary
    (the acceptance: an unknown ability field is a 422), any key outside the
    allowed set is rejected here before the render.
    """
    _reject_unknown(payload, _ABILITY_FIELDS, f"{chrooked_id}.yaml")
    ability = _ability_from_payload(payload, chrooked_id)
    yaml_text = writer.ability_yaml(ability)
    path = Path(ruleset_dir) / "abilities" / f"{chrooked_id}.yaml"
    return colmod.serialize_ability(_validated_write(path, yaml_text, load_ability))


_ABILITY_FIELDS = ("name", "chrooked_id", "aka", "description")


def _reject_unknown(payload: dict[str, Any], allowed: tuple[str, ...], where: str) -> None:
    unknown = [key for key in payload if key not in allowed]
    if unknown:
        raise ValidationError(
            f"{where}: unknown field(s) {', '.join(sorted(unknown))}; "
            f"allowed fields are {', '.join(sorted(allowed))}."
        )


def delete_ability(
    ruleset: Ruleset, ruleset_dir: Path, chrooked_id: str, *, confirm: bool = False
) -> None:
    ability = ruleset.abilities.get(chrooked_id)
    if ability is None:
        raise NotFoundError(f"No owned ability {chrooked_id!r} to delete.")
    citing = ability_citations(ruleset, ability)
    if citing and not confirm:
        raise CitationError(
            f"{ability.name} is cited by {len(citing)} species; "
            "confirm to delete and leave those slots pointing at a missing ability.",
            citing,
        )
    (Path(ruleset_dir) / "abilities" / f"{chrooked_id}.yaml").unlink()


def ability_citations(ruleset: Ruleset, ability: AbilityDef) -> list[str]:
    """Species whose ability slots cite this ability (by display name or chrooked_id)."""
    keys = {ability.chrooked_id.lower(), ability.name.strip().lower()}
    citing = []
    for species in ruleset.species.values():
        slots = species.abilities
        if slots is None:
            continue
        if any(
            slot and slot.strip().lower() in keys
            for slot in (slots.primary, slots.secondary, slots.hidden)
        ):
            citing.append(species.name)
    return sorted(set(citing))


# --------------------------------------------------------------------------- #
# Type chart — one whole-list file (type-chart/overrides.yaml), so a write is a
# full replace of the override list rather than a per-id upsert.
# --------------------------------------------------------------------------- #


def replace_type_chart(ruleset_dir: Path, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate-write the whole type-chart override list; returns it serialized."""
    where = "overrides.yaml"
    overrides: list[TypeChartOverride] = []
    try:
        for entry in entries:
            _reject_unknown(entry, _TYPE_CHART_FIELDS, where)
            overrides.append(
                TypeChartOverride(
                    attacker=_require(entry, "attacker", where),
                    defender=_require(entry, "defender", where),
                    multiplier=float(entry["multiplier"]),
                )
            )
    except (KeyError, TypeError, ValueError) as error:
        # _require raises ValidationError (not a ValueError), so it propagates
        # unwrapped; this catches only entry-shape errors (e.g. a bad multiplier).
        raise ValidationError(f"{where}: malformed type-chart entry ({error}).") from error
    yaml_text = writer.type_chart_yaml(overrides)
    path = Path(ruleset_dir) / "type-chart" / "overrides.yaml"
    validated = _validated_write(path, yaml_text, load_type_chart)
    return [colmod.serialize_type_chart_entry(t) for t in validated]


_TYPE_CHART_FIELDS = ("attacker", "defender", "multiplier")


# --------------------------------------------------------------------------- #
# Behaviors — human-owned specs; the seed never writes them, so this is their
# only writer. No citation guard: a behavior attaches by chrooked_id and leaves
# no dangling data reference when removed.
# --------------------------------------------------------------------------- #


_BEHAVIOR_FIELDS = (
    "name", "chrooked_id", "applies_to", "aka",
    "effects", "test_cases", "notes", "engine_hints",
)


def upsert_behavior(ruleset_dir: Path, chrooked_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate-write one behavior spec; returns it serialized."""
    _reject_unknown(payload, _BEHAVIOR_FIELDS, f"{chrooked_id}.yaml")
    try:
        spec = _behavior_from_payload(payload, chrooked_id)
        yaml_text = writer.behavior_yaml(spec)
    except (KeyError, TypeError, ValueError) as error:
        # _check_id raises ValidationError (not a ValueError) and propagates
        # unwrapped; this catches only payload-shape errors.
        raise ValidationError(f"{chrooked_id}.yaml: malformed payload ({error}).") from error
    path = Path(ruleset_dir) / "behaviors" / f"{chrooked_id}.yaml"
    return colmod.serialize_behavior(_validated_write(path, yaml_text, load_behavior))


def delete_behavior(ruleset_dir: Path, chrooked_id: str) -> None:
    path = Path(ruleset_dir) / "behaviors" / f"{chrooked_id}.yaml"
    if not path.exists():
        raise NotFoundError(f"No behavior spec {chrooked_id!r} to delete.")
    path.unlink()


def _behavior_from_payload(payload: dict[str, Any], chrooked_id: str) -> BehaviorSpec:
    where = f"{chrooked_id}.yaml"
    _check_id(payload, chrooked_id, where)
    effects = tuple(
        BehaviorEffect(
            summary=entry.get("summary", ""),
            trigger=entry.get("trigger", ""),
            effect=entry.get("effect", ""),
            when=entry.get("when") or None,
        )
        for entry in (payload.get("effects") or [])
    )
    test_cases = tuple(
        BehaviorTestCase(given=entry.get("given", ""), expect=entry.get("expect", ""))
        for entry in (payload.get("test_cases") or [])
    )
    return BehaviorSpec(
        name=payload.get("name", ""),
        chrooked_id=chrooked_id,
        applies_to=payload.get("applies_to", ""),
        aka=dict(payload.get("aka") or {}),
        effects=effects,
        test_cases=test_cases,
        notes=tuple(payload.get("notes") or ()),
        engine_hints=dict(payload.get("engine_hints") or {}),
    )
