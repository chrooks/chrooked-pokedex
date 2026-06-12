"""Diff a fork against its base and build an in-memory Ruleset (the seed).

This is the one place diffing legitimately lives. For each modeled category it
compares the base (unmodified pokeemerald-expansion at the pinned version) to
the fork (Dreamstone) and keeps only what the fork changed:

  * species: only the overridden scalar fields (types, abilities, stats);
  * learnsets: the whole fork list whenever it differs at all (the fix for v1's
    duplicate-move bug — the Ruleset owns the entire list);
  * moves / abilities: a Ruleset-owned definition for anything the fork added or
    changed;
  * type chart: an override for any matchup whose raw cell token differs.

Evolutions are intentionally not seeded here; they are handled in a later
milestone. Other species fields (catch rate, EV yields, ...) are outside the
neutral schema and are not captured.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from ..model.schema import (
    AbilitiesOverride,
    AbilityDef,
    AdditionalEffect,
    LearnsetMove,
    MoveDef,
    SpeciesOverride,
    TypeChartOverride,
)
from ..model.schema import EvolutionOverride
from ..readers.pokeemerald import (
    ability_parser,
    evolution_parser,
    learnset_parser,
    move_parser,
    species_parser,
)
from ..readers.pokeemerald.type_chart_parser import parse_type_chart
from . import neutralize as nz


@dataclass(frozen=True)
class SeedData:
    species: dict[str, SpeciesOverride] = field(default_factory=dict)
    moves: dict[str, MoveDef] = field(default_factory=dict)
    abilities: dict[str, AbilityDef] = field(default_factory=dict)
    type_chart: list[TypeChartOverride] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        learnsets = sum(1 for s in self.species.values() if s.learnset is not None)
        evolutions = sum(1 for s in self.species.values() if s.evolution is not None)
        return {
            "species_changed": len(self.species),
            "learnsets_replaced": learnsets,
            "evolutions_changed": evolutions,
            "moves_owned": len(self.moves),
            "abilities_owned": len(self.abilities),
            "type_chart_overrides": len(self.type_chart),
        }


def seed_from_fork(fork: Path, base: Path) -> SeedData:
    fork_species = species_parser.parse_species_profiles(fork)
    base_species = species_parser.parse_species_profiles(base)
    fork_learnsets = learnset_parser.parse_learnsets(fork)
    base_learnsets = learnset_parser.parse_learnsets(base)

    fork_move_names = nz.build_move_name_map(fork)
    base_move_names = nz.build_move_name_map(base)
    move_names = {**base_move_names, **fork_move_names}

    ability_names = {**nz.build_ability_name_map(base), **nz.build_ability_name_map(fork)}

    species = _seed_species(
        fork_species,
        base_species,
        fork_learnsets,
        base_learnsets,
        move_names,
        ability_names,
    )
    _merge_evolutions(species, fork, base)
    moves = _seed_moves(fork, base)
    abilities = _seed_abilities(fork, base)
    type_chart = _seed_type_chart(fork, base)

    return SeedData(
        species=species, moves=moves, abilities=abilities, type_chart=type_chart
    )


def _merge_evolutions(species: dict, fork: Path, base: Path) -> None:
    """Add evolution Overrides (and any source identity stubs) into the species map.

    When a species' forward evolution list differs from base, the Ruleset owns the
    whole list (the learnset lesson): every target in the fork list is emitted as a
    backward `from` pointer on that target. Each pre-evolution source is guaranteed
    a species entry (a stub if it has no other Override) so the applier can resolve
    its symbol when it reconstructs the source's evolution list.
    """
    fork_evos = evolution_parser.parse_evolutions(fork)
    base_evos = evolution_parser.parse_evolutions(base)

    for source_const in sorted(fork_evos):
        if fork_evos.get(source_const) == base_evos.get(source_const):
            continue  # this source's evolutions are unchanged
        source_name = nz.species_display_name(source_const)
        _ensure_identity(species, source_const)
        for entry in fork_evos[source_const]:
            target_cid = nz.slug(nz.species_display_name(entry.target_species))
            _ensure_identity(species, entry.target_species)
            evolution = EvolutionOverride(
                from_species=source_name,
                method=nz.neutralize_evolution_method(entry.method, entry.param),
            )
            species[target_cid] = replace(species[target_cid], evolution=evolution)


def _ensure_identity(species: dict, constant: str) -> None:
    """Make sure `species` has an entry for this constant (stub if absent)."""
    cid = nz.slug(nz.species_display_name(constant))
    if cid not in species:
        species[cid] = SpeciesOverride(
            name=nz.species_display_name(constant),
            chrooked_id=cid,
            aka={"pokeemerald": constant},
        )


def _insert_unique(result: dict, key: str, value, kind: str, source: str) -> None:
    """Insert into a seed dict, failing fast if two distinct sources collide on the
    same `chrooked_id`. A silent overwrite would drop one entity from the Ruleset."""
    if key in result:
        raise ValueError(
            f"chrooked_id collision: {kind} {source!r} and an earlier entity both "
            f"slug to {key!r}; give one an explicit distinct id"
        )
    result[key] = value


def _is_gmax(constant: str) -> bool:
    """Gigantamax forms are battle-only cosmetic forms Chris does not rule on.
    They are excluded from the seed so a re-seed never re-creates their entries."""
    return constant.endswith("_GMAX")


def _seed_species(
    fork_species, base_species, fork_learnsets, base_learnsets, move_names, ability_names
):
    result: dict[str, SpeciesOverride] = {}
    for constant in sorted(fork_species):
        if _is_gmax(constant):
            continue
        fork_p = fork_species[constant]
        base_p = base_species.get(constant)
        base_fields = base_p.fields if base_p else {}

        types = _diff_types(base_fields.get("types"), fork_p.fields.get("types"))
        abilities = _diff_abilities(
            base_fields.get("abilities"),
            fork_p.fields.get("abilities"),
            ability_names,
        )
        stats = _diff_stats(base_fields, fork_p.fields)
        learnset = _diff_learnset(
            base_learnsets.get(constant), fork_learnsets.get(constant), move_names
        )

        if not any((types, abilities, stats, learnset is not None)):
            continue

        chrooked_id = nz.slug(nz.species_display_name(constant))
        _insert_unique(result, chrooked_id, SpeciesOverride(
            name=nz.species_display_name(constant),
            chrooked_id=chrooked_id,
            aka=_species_aka(constant, fork_p.fields),
            types=types or None,
            abilities=abilities,
            stats=stats or None,
            learnset=learnset,
        ), "species", constant)
    return result


def _species_aka(constant: str, fields: dict[str, str]) -> dict[str, object]:
    aka: dict[str, object] = {"pokeemerald": constant}
    dex = fields.get("natDexNum")
    if dex and dex.isdigit():
        aka = {"dex": int(dex), "pokeemerald": constant}
    return aka


def _diff_types(base_value, fork_value):
    base_types = nz.extract_types(base_value)
    fork_types = nz.extract_types(fork_value)
    if fork_types and fork_types != base_types:
        return fork_types
    return ()


def _diff_abilities(base_value, fork_value, ability_names):
    base_slots = nz.extract_ability_constants(base_value)
    fork_slots = nz.extract_ability_constants(fork_value)
    if not fork_slots or fork_slots == base_slots:
        return None

    slot_names = ("primary", "secondary", "hidden")
    changed: dict[str, str] = {}
    for index, name in enumerate(slot_names):
        fork_ability = fork_slots[index] if index < len(fork_slots) else "ABILITY_NONE"
        base_ability = base_slots[index] if index < len(base_slots) else "ABILITY_NONE"
        if fork_ability != base_ability and fork_ability != "ABILITY_NONE":
            changed[name] = nz.ability_name(fork_ability, ability_names)
    if not changed:
        return None
    return AbilitiesOverride(
        primary=changed.get("primary"),
        secondary=changed.get("secondary"),
        hidden=changed.get("hidden"),
    )


def _diff_stats(base_fields, fork_fields):
    changed: dict[str, int] = {}
    for c_field, key in nz.STAT_FIELD_TO_KEY.items():
        fork_value = fork_fields.get(c_field)
        base_value = base_fields.get(c_field)
        if fork_value is not None and fork_value != base_value and fork_value.isdigit():
            changed[key] = int(fork_value)
    return changed


def _diff_learnset(base_list, fork_list, move_names):
    if fork_list is None:
        return None
    base_pairs = [(e.level, e.move) for e in (base_list or [])]
    fork_pairs = [(e.level, e.move) for e in fork_list]
    if fork_pairs == base_pairs:
        return None
    return tuple(
        LearnsetMove(level=level, move=nz.move_name(move, move_names))
        for level, move in fork_pairs
    )


def _seed_moves(fork: Path, base: Path) -> dict[str, MoveDef]:
    fork_moves = move_parser.parse_moves(fork)
    base_moves = move_parser.parse_moves(base)
    result: dict[str, MoveDef] = {}
    for constant in sorted(fork_moves):
        info = fork_moves[constant]
        if base_moves.get(constant) == info:
            continue
        chrooked_id = nz.slug(info.name)
        _insert_unique(result, chrooked_id, MoveDef(
            name=info.name,
            chrooked_id=chrooked_id,
            type=nz.type_name(info.type) if info.type else "",
            category=info.category.lower(),
            power=info.power,
            accuracy=info.accuracy,
            pp=info.pp,
            description=nz.normalize_description(info.description),
            aka={"pokeemerald": constant},
            effect=nz.primary_effect_name(info.effect),
            argument=nz.neutralize_argument(info.argument) if info.argument else None,
            additional_effects=tuple(
                AdditionalEffect(effect=nz.move_effect_name(token), chance=chance)
                for token, chance in info.additional_effects
            ),
            flags=tuple(
                name for token in info.flags
                if (name := nz.move_flag_name(token)) is not None
            ),
            priority=info.priority,
            target=nz.move_target_name(info.target),
        ), "move", constant)
    return result


def _seed_abilities(fork: Path, base: Path) -> dict[str, AbilityDef]:
    fork_text = ability_parser.parse_ability_text(fork)
    base_text = ability_parser.parse_ability_text(base)
    result: dict[str, AbilityDef] = {}
    for constant in sorted(fork_text):
        name, desc = fork_text[constant]
        if base_text.get(constant) == (name, desc):
            continue
        chrooked_id = nz.slug(name)
        _insert_unique(result, chrooked_id, AbilityDef(
            name=name,
            chrooked_id=chrooked_id,
            description=nz.normalize_description(desc),
            aka={"pokeemerald": constant},
        ), "ability", constant)
    return result


def _seed_type_chart(fork: Path, base: Path) -> list[TypeChartOverride]:
    fork_chart = parse_type_chart(fork)
    base_chart = parse_type_chart(base)
    overrides: list[TypeChartOverride] = []
    for key in sorted(fork_chart):
        fork_cell = fork_chart[key]
        base_cell = base_chart.get(key)
        if base_cell is not None and base_cell.raw == fork_cell.raw:
            continue
        if fork_cell.value is None:
            continue
        attacker, defender = key
        overrides.append(
            TypeChartOverride(
                attacker=attacker, defender=defender, multiplier=fork_cell.value
            )
        )
    return overrides
