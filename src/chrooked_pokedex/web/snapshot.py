"""The committed base snapshot: base 1.11.2 frozen into a deterministic JSON.

The Canon dex needs full base values to merge the Ruleset's overrides onto, but
the Ruleset itself stores only the changed fields. Rather than depend on the
deletable `_scratch-expansion-1.11.2` checkout at view time, we read it once with
the existing pokeemerald readers and write a committed JSON keyed by `chrooked_id`
— the same join key the overrides use. `build_snapshot` produces it; `write_snapshot`
emits it deterministically (so a re-run is byte-identical); `load_snapshot` reads
it back.

Base values are stored in the Ruleset's neutral vocabulary (`Water`, not
`TYPE_WATER`) by reusing `seed.neutralize`, so a merged dex entry is neutral
end to end.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..readers.pokeemerald import (
    learnset_parser,
    species_parser,
)
from ..seed import neutralize as nz

_NATIONAL_DEX_TOKEN = re.compile(r"NATIONAL_DEX_[A-Z0-9_]+")
_ENUM_MEMBER = re.compile(r"(NATIONAL_DEX_[A-Z0-9_]+)\s*(?:=\s*(\d+))?")
# Anchor on the `enum {` opener (keyword + brace) so a stray lowercase "enum"
# fragment — a comment word, an identifier — can't redirect the slice.
_ENUM_OPEN = re.compile(r"\benum\s*\{")

# Where the committed snapshot lives, relative to the repo root.
DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "ruleset" / ".base" / "1.11.2.json"
)

SNAPSHOT_VERSION = "1.11.2"

# Gigantamax entries are cosmetic battle-only forms the Ruleset never rules on
# (mirrors the seed's exclusion), so the dex skips them too.
def _is_gmax(constant: str) -> bool:
    return constant.endswith("_GMAX")


def build_snapshot(base_dir: Path) -> dict[str, Any]:
    """Read base 1.11.2 with the pokeemerald readers into a neutral snapshot dict.

    Every national-dex species becomes one entry keyed by `chrooked_id`, carrying
    the fields a `SpeciesOverride` can change: dex number, name, types, the three
    ability slots, the six base stats, and the level-up learnset.
    """
    base_dir = Path(base_dir)
    profiles = species_parser.parse_species_profiles(base_dir)
    learnsets = learnset_parser.parse_learnsets(base_dir)
    ability_names = nz.build_ability_name_map(base_dir)
    move_names = nz.build_move_name_map(base_dir)
    dex_numbers = _national_dex_map(base_dir)

    species: dict[str, dict[str, Any]] = {}
    for constant in sorted(profiles):
        if _is_gmax(constant):
            continue
        entry = _base_species_entry(
            constant,
            profiles[constant],
            learnsets.get(constant),
            ability_names,
            move_names,
            dex_numbers,
        )
        species[entry["chrooked_id"]] = entry

    return {
        "version": SNAPSHOT_VERSION,
        "species": species,
        # The other kinds the dex surfaces are Ruleset-owned (moves/abilities are
        # only present when changed) so they merge from the Ruleset, not the base.
        # Reserved here for shape stability; populated in a later slice if needed.
        "moves": {},
        "abilities": {},
        "type_chart": [],
    }


def _base_species_entry(
    constant: str,
    profile: species_parser.SpeciesProfile,
    learnset: list[learnset_parser.LearnsetEntry] | None,
    ability_names: dict[str, str],
    move_names: dict[str, str],
    dex_numbers: dict[str, int],
) -> dict[str, Any]:
    fields = profile.fields
    name = nz.species_display_name(constant)
    return {
        "dex": _resolve_dex(fields.get("natDexNum"), dex_numbers),
        "chrooked_id": nz.slug(name),
        "name": name,
        "types": list(nz.extract_types(fields.get("types"))),
        "abilities": _base_abilities(
            nz.extract_ability_constants(fields.get("abilities")), ability_names
        ),
        "stats": _base_stats(fields),
        "learnset": [
            {"level": entry.level, "move": nz.move_name(entry.move, move_names)}
            for entry in (learnset or [])
        ],
    }


def _base_stats(fields: dict[str, str]) -> dict[str, int]:
    stats: dict[str, int] = {}
    for c_field, key in nz.STAT_FIELD_TO_KEY.items():
        value = fields.get(c_field)
        if value is not None and value.isdigit():
            stats[key] = int(value)
    return stats


def _resolve_dex(raw: str | None, dex_numbers: dict[str, int]) -> int | None:
    """Resolve a `natDexNum` field to an integer.

    Base 1.11.2 writes the symbolic `NATIONAL_DEX_GOODRA`; we map it through the
    enum order. A bare integer (some forks inline it) is taken directly.
    """
    if not raw:
        return None
    token = _NATIONAL_DEX_TOKEN.search(raw)
    if token:
        return dex_numbers.get(token.group(0))
    return int(raw) if raw.isdigit() else None


def _national_dex_map(base_dir: Path) -> dict[str, int]:
    """Map each `NATIONAL_DEX_*` symbol to its number from the enum order.

    The enum is positional (`NATIONAL_DEX_NONE` = 0, `NATIONAL_DEX_BULBASAUR` = 1,
    …). We walk it in source order, honoring any explicit `= N` and incrementing
    otherwise — so Goodra resolves to 706 without a hardcoded table.
    """
    header = base_dir / "include" / "constants" / "pokedex.h"
    if not header.exists():
        return {}
    text = header.read_text(encoding="utf-8")

    # Only the first `enum { … };` is the national-dex order. The `#define
    # NATIONAL_DEX_COUNT …` lines that follow it must not feed the counter.
    opener = _ENUM_OPEN.search(text)
    body = text[opener.start() : text.find("};", opener.start())] if opener else ""

    numbers: dict[str, int] = {}
    counter = 0
    for name, explicit in _ENUM_MEMBER.findall(body):
        counter = int(explicit) if explicit else counter
        numbers[name] = counter
        counter += 1
    return numbers


def _base_abilities(
    constants: tuple[str, ...], ability_names: dict[str, str]
) -> dict[str, str | None]:
    """Map the three ordered ability slots to neutral names; empty slots stay None."""
    slots = ("primary", "secondary", "hidden")
    result: dict[str, str | None] = {slot: None for slot in slots}
    for index, slot in enumerate(slots):
        if index < len(constants) and constants[index] != "ABILITY_NONE":
            result[slot] = nz.ability_name(constants[index], ability_names)
    return result


def write_snapshot(snapshot: dict[str, Any], out_path: Path) -> Path:
    """Write the snapshot as deterministic JSON (sorted keys, trailing newline).

    Determinism is the point: a re-run on an unchanged base produces byte-identical
    output, so `git status` stays clean and the committed file is a real fixed point.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    out_path.write_text(text, encoding="utf-8")
    return out_path


def load_snapshot(path: Path = DEFAULT_SNAPSHOT_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
