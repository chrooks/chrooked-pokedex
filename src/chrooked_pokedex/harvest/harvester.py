"""Harvest: propose Ruleset edits from in-game tuning, gated by confirmation.

Harvest is the reverse of apply. Apply writes the Ruleset's recorded values into a
fork; harvest reads a fork back and, for each field the Ruleset already overrides,
notices where the fork now holds a different value (someone tuned it in-game) and
proposes pulling that value into the Ruleset. The Ruleset stays canonical: nothing
is written until a proposal is accepted, one field at a time.

This compares the fork against the Ruleset, not against base — so it needs no base
checkout and surfaces exactly the drift in fields the Ruleset tracks.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from ..appliers.pokeemerald.resolution import ResolutionMap
from ..model import Ruleset
from ..model.schema import AbilitiesOverride, SpeciesOverride
from ..readers.pokeemerald import species_parser
from ..seed import neutralize as nz
from ..seed.writer import species_yaml

_ABILITY_SLOTS = ("primary", "secondary", "hidden")


@dataclass(frozen=True)
class Proposal:
    """One proposed Ruleset edit. `kind` is stat/type/ability; `key` names the slot
    (a stat key, the literal 'types', or an ability slot)."""

    chrooked_id: str
    kind: str
    key: str
    ruleset_value: object
    fork_value: object

    def describe(self) -> str:
        return (
            f"{self.chrooked_id}: {self.kind}.{self.key} "
            f"{self.ruleset_value!r} -> {self.fork_value!r}"
        )


def propose_changes(
    fork: Path, ruleset: Ruleset, resmap: ResolutionMap
) -> list[Proposal]:
    fork_species = species_parser.parse_species_profiles(fork)
    ability_names = nz.build_ability_name_map(fork)
    proposals: list[Proposal] = []

    for chrooked_id in sorted(ruleset.species):
        override = ruleset.species[chrooked_id]
        symbol = resmap.species(chrooked_id, dict(override.aka))
        profile = fork_species.get(symbol) if symbol else None
        if profile is None:
            continue
        proposals.extend(
            _diff_species(chrooked_id, override, profile.fields, ability_names)
        )
    return proposals


def _diff_species(chrooked_id, override: SpeciesOverride, fields, ability_names) -> list[Proposal]:
    proposals: list[Proposal] = []

    if override.stats:
        for key, ruleset_value in override.stats.items():
            fork_field = _stat_key_to_field(key)
            raw = fields.get(fork_field)
            if raw is not None and raw.isdigit() and int(raw) != ruleset_value:
                proposals.append(Proposal(
                    chrooked_id, "stat", key, ruleset_value, int(raw)
                ))

    if override.types:
        fork_types = nz.extract_types(fields.get("types"))
        if fork_types and fork_types != override.types:
            proposals.append(Proposal(
                chrooked_id, "type", "types", list(override.types), list(fork_types)
            ))

    if override.abilities:
        fork_slots = nz.extract_ability_constants(fields.get("abilities"))
        for index, slot in enumerate(_ABILITY_SLOTS):
            ruleset_name = getattr(override.abilities, slot)
            if ruleset_name is None:
                continue
            fork_const = fork_slots[index] if index < len(fork_slots) else None
            fork_name = (
                nz.ability_name(fork_const, ability_names) if fork_const else None
            )
            if fork_name and fork_name != ruleset_name:
                proposals.append(Proposal(
                    chrooked_id, "ability", slot, ruleset_name, fork_name
                ))
    return proposals


def apply_proposals(
    ruleset_dir: Path, ruleset: Ruleset, accepted: list[Proposal]
) -> set[str]:
    """Apply accepted proposals to the Ruleset YAML; return touched chrooked_ids."""
    by_species: dict[str, list[Proposal]] = {}
    for proposal in accepted:
        by_species.setdefault(proposal.chrooked_id, []).append(proposal)

    touched: set[str] = set()
    for chrooked_id, proposals in by_species.items():
        override = ruleset.species[chrooked_id]
        for proposal in proposals:
            override = _apply_one(override, proposal)
        path = Path(ruleset_dir) / "species" / f"{chrooked_id}.yaml"
        path.write_text(species_yaml(override), encoding="utf-8")
        touched.add(chrooked_id)
    return touched


def _apply_one(override: SpeciesOverride, proposal: Proposal) -> SpeciesOverride:
    if proposal.kind == "stat":
        new_stats = {**(override.stats or {}), proposal.key: proposal.fork_value}
        return replace(override, stats=new_stats)
    if proposal.kind == "type":
        return replace(override, types=tuple(proposal.fork_value))
    if proposal.kind == "ability":
        current = override.abilities or AbilitiesOverride()
        return replace(
            override,
            abilities=replace(current, **{proposal.key: proposal.fork_value}),
        )
    return override


def _stat_key_to_field(key: str) -> str:
    for field, stat_key in nz.STAT_FIELD_TO_KEY.items():
        if stat_key == key:
            return field
    return key
