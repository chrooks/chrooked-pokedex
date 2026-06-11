"""The top-level Ruleset: the in-memory whole of a `ruleset/` folder."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from . import loader
from .schema import AbilityDef, MoveDef, SpeciesOverride, TypeChartOverride


@dataclass(frozen=True)
class Ruleset:
    """All Overrides and Ruleset-owned definitions, keyed by `chrooked_id`."""

    species: Mapping[str, SpeciesOverride] = field(default_factory=dict)
    moves: Mapping[str, MoveDef] = field(default_factory=dict)
    abilities: Mapping[str, AbilityDef] = field(default_factory=dict)
    type_chart: tuple[TypeChartOverride, ...] = ()
    meta: Mapping[str, Any] = field(default_factory=dict)

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

        return cls(
            species=species,
            moves=moves,
            abilities=abilities,
            type_chart=type_chart,
            meta=meta,
        )

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


def _yaml_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.yaml"))
