"""The top-level Ruleset: the in-memory whole of a `ruleset/` folder."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from . import loader
from .behavior_spec import BehaviorSpec
from .schema import AbilityDef, MoveDef, SpeciesOverride, TypeChartOverride


@dataclass(frozen=True)
class Ruleset:
    """All Overrides and Ruleset-owned definitions, keyed by `chrooked_id`.

    `behaviors` is the human-owned mechanic layer, kept apart from the machine-owned data
    the seed regenerates (species/moves/abilities/type_chart).
    """

    species: Mapping[str, SpeciesOverride] = field(default_factory=dict)
    moves: Mapping[str, MoveDef] = field(default_factory=dict)
    abilities: Mapping[str, AbilityDef] = field(default_factory=dict)
    type_chart: tuple[TypeChartOverride, ...] = ()
    behaviors: Mapping[str, BehaviorSpec] = field(default_factory=dict)
    meta: Mapping[str, Any] = field(default_factory=dict)
    # Full base species data (stats/types/abilities/...) from the `.base/<version>.json`
    # seed snapshot, keyed by chrooked_id. Overrides are diffs against this; an applier
    # that must CREATE a species the target lacks merges base + override to get a full
    # row. Empty when no snapshot is present.
    base_species: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, ruleset_dir: Path) -> "Ruleset":
        ruleset_dir = Path(ruleset_dir)

        meta: dict[str, Any] = {}
        meta_path = ruleset_dir / "meta.yaml"
        if meta_path.exists():
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}

        species = {
            s.chrooked_id: s
            for s in (loader.load_species(p) for p in _yaml_files(ruleset_dir / "species"))
        }
        moves = {
            m.chrooked_id: m
            for m in (loader.load_move(p) for p in _yaml_files(ruleset_dir / "moves"))
        }
        abilities = {
            a.chrooked_id: a
            for a in (loader.load_ability(p) for p in _yaml_files(ruleset_dir / "abilities"))
        }

        type_chart: tuple[TypeChartOverride, ...] = ()
        type_chart_path = ruleset_dir / "type-chart" / "overrides.yaml"
        if type_chart_path.exists():
            type_chart = loader.load_type_chart(type_chart_path)

        behaviors = {
            b.chrooked_id: b
            for b in (loader.load_behavior(p) for p in _yaml_files(ruleset_dir / "behaviors"))
        }

        return cls(
            species=species,
            moves=moves,
            abilities=abilities,
            type_chart=type_chart,
            behaviors=behaviors,
            meta=meta,
            base_species=_load_base_species(ruleset_dir),
        )

    @classmethod
    def load_namespace(cls, ruleset_dir: Path, slug: str) -> "Optional[Ruleset]":
        """Load a Target Override set from `ruleset/targets/<slug>/`, or None if absent.

        The namespace folder mirrors the base layout exactly (species/, moves/,
        abilities/, type-chart/, behaviors/), so the regular `load` reads it with no
        special parsing. Its `meta.yaml` carries `slug`/`engine`/`label` instead of a
        base version; that lands in the returned Ruleset's `meta`. A namespace has no
        `.base/` snapshot, so `base_species` comes back empty — that is fine, the
        overlay is composed onto a base Ruleset that already has one.
        """
        namespace_dir = Path(ruleset_dir) / "targets" / slug
        if not namespace_dir.exists():
            return None
        return cls.load(namespace_dir)

    def owned_move(self, name_or_id: str) -> Optional[MoveDef]:
        """Resolve a move name or `chrooked_id` to a Ruleset-owned MoveDef.

        Learnsets cite moves by display name (`Excalibur`); this matches that
        name case-insensitively, and also accepts a `chrooked_id` directly.
        Returns None when the Ruleset does not own the move.
        """
        key = name_or_id.strip().lower()
        for move in self.moves.values():
            if move.chrooked_id == key or move.name.lower() == key:
                return move
        return None

    def owned_ability(self, name_or_id: str) -> Optional[AbilityDef]:
        """Resolve an ability name or `chrooked_id` to a Ruleset-owned AbilityDef."""
        key = name_or_id.strip().lower()
        for ability in self.abilities.values():
            if ability.chrooked_id == key or ability.name.lower() == key:
                return ability
        return None

    def behavior_for(self, name_or_id: str) -> Optional[BehaviorSpec]:
        """Resolve a name or `chrooked_id` to its BehaviorSpec, if one exists."""
        key = name_or_id.strip().lower()
        for spec in self.behaviors.values():
            if spec.chrooked_id == key or spec.name.lower() == key:
                return spec
        return None


def _yaml_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.yaml"))


def _load_base_species(ruleset_dir: Path) -> Mapping[str, Mapping[str, Any]]:
    """Read the `.base/<version>.json` seed snapshot's `species` map, or {} if absent.

    The snapshot is the full base data the Ruleset was seeded from; its `species` is
    keyed by `chrooked_id`, the same key the Overrides use. When more than one snapshot
    is present, the lexicographically last filename wins (highest version).
    """
    base_dir = ruleset_dir / ".base"
    snapshots = sorted(base_dir.glob("*.json")) if base_dir.exists() else []
    if not snapshots:
        return {}
    data = json.loads(snapshots[-1].read_text(encoding="utf-8"))
    species = data.get("species") if isinstance(data, dict) else None
    return species if isinstance(species, dict) else {}
