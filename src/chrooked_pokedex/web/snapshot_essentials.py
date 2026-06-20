"""Build the neutral per-Target snapshot from an Essentials PBS directory.

This is the engine-aware sibling of ``web/snapshot.py::build_snapshot``. Pointed
at an Essentials game (a ``PBS/`` tree of text files, not a pokeemerald C source
tree), it produces the *same* neutral snapshot dict the backdrop merge
(``web/dex.py``) consumes, so an Essentials target's dex / abilities / moves /
type-chart render its own values.

The read is dialect-routed (``appliers/essentials/dialect.detect_dialect``):

* ``essentials16`` (16.2) — pokemon/types are ``[N]`` numeric sections with an
  ``InternalName=`` line; abilities/moves are flat CSV rows.
* ``essentials21`` (modern v21) — every section header *is* the internal name
  (``[BULBASAUR]``); abilities/moves carry a ``Name=`` line.

A thin per-dialect adapter normalizes each record to ``(internal_name, fields)``
before a single shared mapping turns it into the neutral shape. The join key is
``nz.slug(InternalName)`` (#40 D3-REVISED) — language-independent, so it equals
the English base's ``chrooked_id`` and a localized (e.g. Spanish) target overlays
the base instead of producing foreign duplicates. The display ``Name`` is kept as
the human label.

Scope (D4): species (dex #, name, types, ability slots, six stats), abilities
map, moves map, and the full 18×18 type-chart grid. Evolution edges and the
level-up learnset are deferred to a follow-up, and the merge ``.get``-defaults
them so omission renders cleanly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..appliers.essentials.dialect import detect_dialect
from ..appliers.essentials.pbs_read import parse_sections as parse_sections_v21
from ..appliers.essentials162.section_read import (
    parse_sections as parse_sections_162,
)
from ..seed import neutralize as nz

SNAPSHOT_VERSION = "essentials"

# Essentials BaseStats are positional: HP, Attack, Defense, Speed, Sp.Atk,
# Sp.Def — so Speed is index 3 (mirrors ``species_apply._STAT_KEY_TO_INDEX``).
_STAT_KEYS_BY_INDEX = ("hp", "atk", "def", "spe", "spa", "spd")

# The 18 real battle types, in canonical neutral form, used to size the full
# type-chart grid. Defenders/attackers the PBS does not mention still get a 1.0
# row/column so the grid is always 18×18 = 324 cells.
_BATTLE_TYPES = (
    "Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug",
    "Ghost", "Steel", "Fire", "Water", "Grass", "Electric", "Psychic",
    "Ice", "Dragon", "Dark", "Fairy",
)


# --- A normalized record: an internal name plus its (key, value) fields ----- #

_Record = tuple[str, dict[str, str]]


def _fields_to_dict(fields: list[tuple[str, str]]) -> dict[str, str]:
    """Collapse a section's ordered ``(key, value)`` pairs into a dict.

    Duplicate keys are rare in PBS; last-wins is fine for the read-only mapping.
    """
    return {key: value for key, value in fields}


def _records_v21(text: str) -> list[_Record]:
    """Modern v21: the section header *is* the internal name."""
    return [
        (header, _fields_to_dict(fields))
        for header, fields in parse_sections_v21(text)
    ]


def _records_162_sectioned(text: str) -> list[_Record]:
    """16.2 ``[N]`` sections: identity lives in the ``InternalName=`` line.

    Sections without an ``InternalName=`` are skipped — they have no stable
    identity to key on.
    """
    records: list[_Record] = []
    for _index, fields in parse_sections_162(text):
        mapping = _fields_to_dict(fields)
        internal = mapping.get("InternalName")
        if internal:
            records.append((internal, mapping))
    return records


# --- 16.2 flat-CSV readers (abilities, moves) ------------------------------- #
#
# 16.2 abilities/moves are not sectioned: each non-comment line is a CSV row.
# Quoted fields (descriptions) may contain commas, so a naive split is wrong —
# a tiny quote-aware splitter keeps a quoted description intact.


def _split_csv_row(line: str) -> list[str]:
    """Split one CSV row, honoring double-quoted fields that contain commas."""
    fields: list[str] = []
    current: list[str] = []
    in_quotes = False
    for char in line:
        if char == '"':
            in_quotes = not in_quotes
        elif char == "," and not in_quotes:
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return [field.strip() for field in fields]


def _csv_rows(text: str) -> list[list[str]]:
    """Return the meaningful (non-blank, non-comment) CSV rows of a 16.2 file."""
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip().lstrip("﻿")
        if not stripped or stripped.startswith("#"):
            continue
        rows.append(_split_csv_row(stripped))
    return rows


# --- Shared mapping: records -> neutral snapshot dicts ---------------------- #


def _neutral_type(internal: str) -> str:
    """Neutralize an Essentials internal type name (``GRASS`` -> ``Grass``).

    Reuses the pokeemerald neutralizer by prefixing the ``TYPE_`` the engine
    omits, so the 18 type names match the one type universe the rest of the
    snapshot uses.
    """
    return nz.type_name(f"TYPE_{internal}")


def _species_types(mapping: dict[str, str]) -> list[str]:
    """Read a species' types from either ``Types=`` (v21) or ``Type1/Type2``.

    Modern v21 carries a single ``Types=A,B`` line; 16.2 splits it across
    ``Type1=`` / ``Type2=``. Empty slots are dropped.
    """
    if "Types" in mapping:
        raw = [t.strip() for t in mapping["Types"].split(",") if t.strip()]
    else:
        raw = [
            mapping[key].strip()
            for key in ("Type1", "Type2")
            if mapping.get(key, "").strip()
        ]
    return [_neutral_type(internal) for internal in raw]


def _species_stats(mapping: dict[str, str]) -> dict[str, int]:
    """Read the six positional ``BaseStats`` into the neutral stat dict.

    Order is HP, ATK, DEF, SPEED, SPATK, SPDEF — so Speed is index 3. A
    non-integer or short list yields only the stats that parse.
    """
    raw = mapping.get("BaseStats", "")
    values = [v.strip() for v in raw.split(",") if v.strip()]
    stats: dict[str, int] = {}
    for index, key in enumerate(_STAT_KEYS_BY_INDEX):
        if index < len(values) and values[index].lstrip("-").isdigit():
            stats[key] = int(values[index])
    return stats


def _species_abilities(mapping: dict[str, str]) -> dict[str, str | None]:
    """Map ``Abilities`` (primary, secondary) + ``HiddenAbility`` to slots.

    Ability values are internal names; they are kept as-is (the abilities map
    keys off display name, but a species cites the internal slot symbol). Empty
    slots stay ``None``.
    """
    slots: dict[str, str | None] = {"primary": None, "secondary": None, "hidden": None}
    listed = [a.strip() for a in mapping.get("Abilities", "").split(",") if a.strip()]
    if listed:
        slots["primary"] = listed[0]
    if len(listed) > 1:
        slots["secondary"] = listed[1]
    hidden = mapping.get("HiddenAbility", "").strip()
    if hidden:
        slots["hidden"] = hidden
    return slots


def _build_species(records: list[_Record]) -> dict[str, dict[str, Any]]:
    """Map species records to the neutral ``{chrooked_id: entry}`` dict.

    The join key is ``nz.slug(InternalName)`` (#40 D3-REVISED) — language-
    independent, so it equals the English base's ``chrooked_id`` and a localized
    target overlays the base instead of producing foreign duplicates. The
    display ``Name`` is kept as the human label.
    """
    species: dict[str, dict[str, Any]] = {}
    for index, (internal, mapping) in enumerate(records, start=1):
        name = mapping.get("Name", "").strip()
        if not name or not internal:
            continue
        chrooked_id = nz.slug(internal)
        species[chrooked_id] = {
            "dex": index,
            "chrooked_id": chrooked_id,
            "name": name,
            "types": _species_types(mapping),
            "abilities": _species_abilities(mapping),
            "stats": _species_stats(mapping),
            "learnset": [],
        }
    return species


def _build_abilities_v21(text: str) -> dict[str, dict[str, Any]]:
    """Modern v21 abilities: ``[INTERNALNAME]`` sections with ``Name=``/``Description=``."""
    abilities: dict[str, dict[str, Any]] = {}
    for internal, fields in _records_v21(text):
        name = fields.get("Name", "").strip()
        if not name or not internal:
            continue
        chrooked_id = nz.slug(internal)
        abilities[chrooked_id] = {
            "chrooked_id": chrooked_id,
            "name": name,
            "description": fields.get("Description", "").strip(),
            "aka": {},
        }
    return abilities


def _build_abilities_162(text: str) -> dict[str, dict[str, Any]]:
    """16.2 abilities: flat CSV ``idx,INTERNAL,Display,"Description"``.

    Keyed on ``slug(InternalName)`` (row 1) so a localized target overlays the
    base; the display ``Name`` (row 2) stays the human label.
    """
    abilities: dict[str, dict[str, Any]] = {}
    for row in _csv_rows(text):
        if len(row) < 3:
            continue
        internal = row[1].strip()
        name = row[2].strip()
        if not name or not internal:
            continue
        chrooked_id = nz.slug(internal)
        description = row[3].strip() if len(row) > 3 else ""
        abilities[chrooked_id] = {
            "chrooked_id": chrooked_id,
            "name": name,
            "description": description,
            "aka": {},
        }
    return abilities


def _move_entry(internal: str, name: str, type_internal: str, category: str,
                power: str, accuracy: str, pp: str,
                description: str) -> dict[str, Any]:
    """Build one neutral move entry from already-extracted raw fields.

    The join key is ``slug(InternalName)`` (#40), not the localized display
    ``name`` — so a Spanish move overlays the English base by internal symbol.
    """
    chrooked_id = nz.slug(internal)

    def _int_or_none(raw: str) -> int | None:
        raw = raw.strip()
        return int(raw) if raw.lstrip("-").isdigit() else None

    return {
        "chrooked_id": chrooked_id,
        "name": name,
        "aka": {},
        "type": _neutral_type(type_internal) if type_internal else "",
        "category": category.strip().lower(),
        "power": _int_or_none(power),
        "accuracy": _int_or_none(accuracy),
        "pp": _int_or_none(pp),
        "description": description.strip(),
    }


def _build_moves_v21(text: str) -> dict[str, dict[str, Any]]:
    """Modern v21 moves: ``[INTERNALNAME]`` sections with named fields."""
    moves: dict[str, dict[str, Any]] = {}
    for internal, fields in _records_v21(text):
        name = fields.get("Name", "").strip()
        if not name or not internal:
            continue
        entry = _move_entry(
            internal=internal,
            name=name,
            type_internal=fields.get("Type", "").strip(),
            category=fields.get("Category", ""),
            power=fields.get("Power", ""),
            accuracy=fields.get("Accuracy", ""),
            pp=fields.get("TotalPP", ""),
            description=fields.get("Description", ""),
        )
        moves[entry["chrooked_id"]] = entry
    return moves


def _build_moves_162(text: str) -> dict[str, dict[str, Any]]:
    """16.2 moves: flat CSV, the REAL Essentials 16.2 column layout (#40).

    Proven against the real Africanvs PBS::

        idx(0), InternalName(1), Display(2), FunctionCode(3), BaseDamage/Power(4),
        Type(5), Category(6), Accuracy(7), TotalPP(8), EffectChance(9), Target(10),
        Priority(11), Flags(12), Description(13)

    The #38 reader wrongly read FunctionCode(3) as the type (the junk ``000``
    badge) and shifted every later column. Description lives at col 13.
    """
    moves: dict[str, dict[str, Any]] = {}
    for row in _csv_rows(text):
        if len(row) < 9:
            continue
        entry = _move_entry(
            internal=row[1],
            name=row[2],
            type_internal=row[5],
            category=row[6],
            power=row[4],
            accuracy=row[7],
            pp=row[8],
            description=row[13] if len(row) > 13 else "",
        )
        moves[entry["chrooked_id"]] = entry
    return moves


# --- Type chart: invert defender Weak/Resist/Immune into a full grid -------- #


def _build_type_chart(records: list[_Record]) -> list[dict[str, Any]]:
    """Invert each defender's Weak/Resist/Immune lists into a full 18×18 grid.

    A types file lists, for each *defender* type, the OTHER types it is weak to
    (``Weaknesses=``), resists (``Resistances=``), or is immune to
    (``Immunities=``). So ``defender=Grass`` weak to ``FIRE`` means the cell
    ``attacker=Fire, defender=Grass`` is 2.0. Every other cell defaults to 1.0,
    so the grid is always the full 324 cells, matching ``_base_type_chart``.
    """
    # defender (neutral) -> {attacker (neutral): multiplier}
    overrides: dict[str, dict[str, float]] = {}
    for internal, mapping in records:
        defender = _neutral_type(internal)
        cell: dict[str, float] = {}
        for key, multiplier in (
            ("Weaknesses", 2.0),
            ("Resistances", 0.5),
            ("Immunities", 0.0),
        ):
            for attacker_internal in mapping.get(key, "").split(","):
                attacker_internal = attacker_internal.strip()
                if attacker_internal:
                    cell[_neutral_type(attacker_internal)] = multiplier
        overrides[defender] = cell

    chart: list[dict[str, Any]] = []
    for attacker in _BATTLE_TYPES:
        for defender in _BATTLE_TYPES:
            multiplier = overrides.get(defender, {}).get(attacker, 1.0)
            chart.append(
                {"attacker": attacker, "defender": defender, "multiplier": multiplier}
            )
    return sorted(chart, key=lambda c: (c["attacker"], c["defender"]))


# --- Public entrypoint ------------------------------------------------------ #


def build_snapshot_essentials(pbs_dir: Path) -> dict[str, Any]:
    """Read an Essentials game directory into the neutral snapshot dict.

    ``pbs_dir`` is the game root (the parent of ``PBS/``), matching
    ``Target.path``. Routes on the detected dialect; an undetectable dialect
    yields an empty-but-shaped snapshot rather than raising, so the backdrop
    renders a clean Empty State.
    """
    pbs_dir = Path(pbs_dir)
    dialect = detect_dialect(pbs_dir)
    pbs = pbs_dir / "PBS"

    def _read(name: str) -> str:
        path = pbs / name
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")

    if dialect == "essentials21":
        species_records = _records_v21(_read("pokemon.txt"))
        abilities = _build_abilities_v21(_read("abilities.txt"))
        moves = _build_moves_v21(_read("moves.txt"))
    elif dialect == "essentials16":
        species_records = _records_162_sectioned(_read("pokemon.txt"))
        abilities = _build_abilities_162(_read("abilities.txt"))
        moves = _build_moves_162(_read("moves.txt"))
    else:
        species_records = []
        abilities = {}
        moves = {}

    # Types files share the ``[N]`` (16.2) / ``[INTERNALNAME]`` (v21) shape with
    # pokemon, so they route the same way.
    if dialect == "essentials21":
        type_records = _records_v21(_read("types.txt"))
    elif dialect == "essentials16":
        type_records = _records_162_sectioned(_read("types.txt"))
    else:
        type_records = []

    return {
        "version": SNAPSHOT_VERSION,
        "species": _build_species(species_records),
        "abilities": abilities,
        "moves": moves,
        "type_chart": _build_type_chart(type_records) if type_records else [],
    }
