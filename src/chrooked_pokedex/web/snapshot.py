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
    ability_parser,
    evolution_parser,
    learnset_parser,
    move_parser,
    species_parser,
    type_chart_parser,
)
from ..seed import neutralize as nz

_NATIONAL_DEX_TOKEN = re.compile(r"NATIONAL_DEX_[A-Z0-9_]+")
_ENUM_MEMBER = re.compile(r"(NATIONAL_DEX_[A-Z0-9_]+)\s*(?:=\s*(\d+))?")
# Anchor on the enum opener (keyword + brace) so a stray lowercase "enum"
# fragment — a comment word, an identifier — can't redirect the slice. The enum
# may be anonymous (`enum {`, base 1.11.2) or tagged (`enum NationalDexOrder {`,
# as some forks write it), so allow one optional tag name before the brace.
_ENUM_OPEN = re.compile(r"\benum\b\s*(?:[A-Za-z_]\w*\s*)?\{")

# A `#define NAME body` line; body keeps everything up to a trailing `// comment`.
_DEFINE = re.compile(r"#define\s+([A-Z_][A-Z0-9_]*)\s+(.+)")
# A config-gated ternary stat value, e.g. `(P_UPDATED_STATS >= GEN_8 ? 140 : 150)`.
_GEN_TERNARY = re.compile(
    r"\(?\s*([A-Z_][A-Z0-9_]*)\s*>=\s*([A-Z_][A-Z0-9_]*)\s*\?\s*(\d+)\s*:\s*(\d+)\s*\)?\Z"
)
# A stat value with an integer offset, e.g. `ALAKAZAM_SP_DEF + 10`, `CORSOLA_HP - 5`.
_STAT_OFFSET = re.compile(r"(.*\S)\s*([+-])\s*(\d+)\Z")

# Where the committed snapshot lives, relative to the repo root.
DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "ruleset" / ".base" / "1.11.2.json"
)

SNAPSHOT_VERSION = "1.11.2"

# Engine placeholder types that aren't real battle types: NONE/MYSTERY pad the
# enum, STELLAR is a Terastal-only cosmetic. The dex rules on the 18 real battle
# types only, so we drop these at the snapshot boundary — the API and frontend
# then share one 18×18 type universe. Promoting one of these to a real future
# type (e.g. Stellar) is a deliberate allowlist change: remove it from this set.
_NON_BATTLE_TYPES = frozenset({"None", "Mystery", "Stellar"})

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
    # Species that appear as a key here have at least one outgoing evolution, so
    # their complement is "fully evolved" (a final form or a single-stage mon).
    evolving = set(evolution_parser.parse_evolutions(base_dir))
    # One symbol table the stat evaluator reads: engine config ints
    # (P_UPDATED_STATS, the GEN_* ladder) plus the named stat macros.
    config = _config_int_map(base_dir)
    symbols = {**config, **_stat_macro_map(base_dir, config)}

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
            symbols,
        )
        entry["fully_evolved"] = constant not in evolving
        species[entry["chrooked_id"]] = entry

    return {
        "version": SNAPSHOT_VERSION,
        "species": species,
        "abilities": _base_abilities_map(base_dir),
        "moves": _base_moves_map(base_dir),
        "type_chart": _base_type_chart(base_dir),
    }


def _base_type_chart(base_dir: Path) -> list[dict[str, Any]]:
    """Read the full base type-effectiveness matrix into a neutral cell list.

    `type_chart_parser.parse_type_chart` already yields a FULL attacker×defender
    grid keyed by neutral type names (`Water`, `Fire`, …) — no neutralization or
    enum mapping needed here (unlike moves). Each `TypeChartCell.value` is the
    resolved float multiplier, or None for a token the parser couldn't resolve;
    we treat that as 1.0 (regular effectiveness) so every cell carries a concrete
    multiplier the merge can overlay onto. The shape matches the Ruleset's
    `TypeChartOverride` join key (`attacker`, `defender`), so `build_type_chart`
    can merge by `(attacker, defender)`. Deterministic: sorted by the pair.
    """
    cells = type_chart_parser.parse_type_chart(base_dir)
    return [
        {
            "attacker": cell.attacker,
            "defender": cell.defender,
            # An unresolved token (None) means regular effectiveness for this pair.
            "multiplier": float(cell.value) if cell.value is not None else 1.0,
        }
        for (attacker, defender), cell in sorted(cells.items())
        # Skip engine placeholders so the snapshot carries only the 18 real
        # battle types (18×18 = 324 cells), one type universe for API + frontend.
        if attacker not in _NON_BATTLE_TYPES and defender not in _NON_BATTLE_TYPES
    ]


def _base_moves_map(base_dir: Path) -> dict[str, dict[str, Any]]:
    """Read every base move into a neutral entry keyed by `chrooked_id`.

    `move_parser.parse_moves` returns engine TOKENS (`TYPE_WATER`, `EFFECT_HIT`,
    `MOVE_TARGET_BOTH`, camelCase flags). This is the one collection whose reader
    is *not* already neutral, so we run the exact same neutralization the seed's
    `_seed_moves` applies (`seed.neutralize`) — type/category/effect/additional
    effects/flags/target all become plain names, and the description is flattened
    of textbox control codes — so no raw ALL_CAPS engine token leaks into the
    snapshot. The shape matches `collections.serialize_move` so the merge produces
    one consistent MoveEntry. Deterministic: sorted over the parser's symbols.
    """
    moves: dict[str, dict[str, Any]] = {}
    for constant in sorted(parsed := move_parser.parse_moves(base_dir)):
        info = parsed[constant]
        chrooked_id = nz.slug(info.name)
        moves[chrooked_id] = {
            "chrooked_id": chrooked_id,
            "name": info.name,
            "aka": {"pokeemerald": constant},
            "type": nz.type_name(info.type) if info.type else "",
            "category": info.category.lower(),
            "power": info.power,
            "accuracy": info.accuracy,
            "pp": info.pp,
            "description": nz.normalize_description(info.description),
            "effect": nz.primary_effect_name(info.effect),
            "argument": (
                nz.neutralize_argument(info.argument) if info.argument else None
            ),
            "additional_effects": [
                {"effect": nz.move_effect_name(token), "chance": chance}
                for token, chance in info.additional_effects
            ],
            "flags": [
                name
                for token in info.flags
                if (name := nz.move_flag_name(token)) is not None
            ],
            "priority": info.priority,
            "target": nz.move_target_name(info.target),
        }
    return moves


def _base_abilities_map(base_dir: Path) -> dict[str, dict[str, Any]]:
    """Read every base ability into a neutral entry keyed by `chrooked_id`.

    Mirrors how species are built: `ability_parser.parse_ability_text` returns
    `{ABILITY_X: (name, description)}` already neutral of engine tokens; we slug
    the name into the join key the Ruleset's AbilityDefs use and flatten textbox
    control codes out of the description (`normalize_description`) so the value is
    neutral end to end. Deterministic: sorted over the parser's symbols.
    """
    abilities: dict[str, dict[str, Any]] = {}
    parsed = ability_parser.parse_ability_text(base_dir)
    for constant in sorted(parsed):
        name, description = parsed[constant]
        chrooked_id = nz.slug(name)
        abilities[chrooked_id] = {
            "chrooked_id": chrooked_id,
            "name": name,
            "description": nz.normalize_description(description),
            "aka": {"pokeemerald": constant},
        }
    return abilities


def _base_species_entry(
    constant: str,
    profile: species_parser.SpeciesProfile,
    learnset: list[learnset_parser.LearnsetEntry] | None,
    ability_names: dict[str, str],
    move_names: dict[str, str],
    dex_numbers: dict[str, int],
    symbols: dict[str, int],
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
        "stats": _base_stats(fields, symbols),
        "learnset": [
            {"level": entry.level, "move": nz.move_name(entry.move, move_names)}
            for entry in (learnset or [])
        ],
    }


def _base_stats(fields: dict[str, str], symbols: dict[str, int]) -> dict[str, int]:
    """Read the six base stats, resolving symbolic values.

    A stat field can be a digit, a named macro (`= AEGISLASH_MAIN_STAT`), an
    inline config-gated ternary (`= P_UPDATED_STATS >= GEN_7 ? 95 : 85`), or a
    macro with an offset (`= ALAKAZAM_SP_DEF + 10`). A digit-only read dropped
    the symbolic forms; `_eval_expr` resolves them all. An unresolved value is
    skipped (the stat is absent rather than wrong).
    """
    stats: dict[str, int] = {}
    for c_field, key in nz.STAT_FIELD_TO_KEY.items():
        value = fields.get(c_field)
        if value is None:
            continue
        resolved = _eval_expr(value, symbols)
        if resolved is not None:
            stats[key] = resolved
    return stats


def _stat_macro_map(base_dir: Path, config: dict[str, int]) -> dict[str, int]:
    """Resolve `#define` stat macros to integers using the engine's config.

    Form stats reference macros like `AEGISLASH_MAIN_STAT`, defined as a
    generation-gated ternary `(P_UPDATED_STATS >= GEN_8 ? 140 : 150)`. We walk
    every `#define` in the species_info headers, keeping those that evaluate to
    an int. Plain integer defines resolve directly; unknown shapes are skipped.
    """
    macros: dict[str, int] = {}
    info_dir = base_dir / "src" / "data" / "pokemon" / "species_info"
    if not info_dir.exists():
        return macros
    for path in sorted(info_dir.glob("*.h")):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _DEFINE.match(line.strip())
            if match is None:
                continue
            value = _eval_define(match.group(2), config)
            if value is not None:
                macros[match.group(1)] = value
    return macros


def _config_int_map(base_dir: Path) -> dict[str, int]:
    """Resolve the engine config `#define`s the stat ternaries depend on.

    Values may be plain ints (`GEN_9 8`) or aliases (`GEN_LATEST GEN_9`,
    `P_UPDATED_STATS GEN_LATEST`); we resolve aliases transitively to ints.
    """
    raw: dict[str, str] = {}
    for rel in ("include/config/general.h", "include/config/pokemon.h"):
        path = base_dir / rel
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _DEFINE.match(line.strip())
            if match is not None:
                raw[match.group(1)] = match.group(2).split("//")[0].strip()

    resolved: dict[str, int] = {}

    def resolve(name: str, seen: frozenset[str]) -> int | None:
        if name in resolved:
            return resolved[name]
        body = raw.get(name)
        if body is None or name in seen:
            return None
        if body.isdigit():
            resolved[name] = int(body)
            return resolved[name]
        alias = resolve(body, seen | {name})
        if alias is not None:
            resolved[name] = alias
        return alias

    for name in raw:
        resolve(name, frozenset())
    return resolved


def _eval_define(body: str, config: dict[str, int]) -> int | None:
    """Evaluate a `#define` body to an int, or None if its shape isn't supported.

    Handles a plain integer and the single config-gated ternary shape the stat
    macros use (`NAME >= GEN_x ? a : b`). Anything else returns None.
    """
    text = body.split("//")[0].strip()
    if text.isdigit():
        return int(text)
    match = _GEN_TERNARY.match(text)
    if match is None:
        return None
    lhs, rhs, when_true, when_false = match.groups()
    if lhs in config and rhs in config:
        return int(when_true) if config[lhs] >= config[rhs] else int(when_false)
    return None


def _eval_expr(value: str, symbols: dict[str, int]) -> int | None:
    """Evaluate a base-stat field value to an int over `symbols`, or None.

    Supports the shapes 1.11.2 actually uses for a stat value, recursively:
    a digit, a known symbol (`ALAKAZAM_SP_DEF`), a config-gated ternary
    (`P_UPDATED_STATS >= GEN_7 ? 95 : 85`), and a symbol/ternary with an integer
    offset (`ALAKAZAM_SP_DEF + 10`, `CORSOLA_HP - 5`). Unknown shapes return None.
    """
    text = value.split("//")[0].strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    if text.isdigit():
        return int(text)
    if text in symbols:
        return symbols[text]
    ternary = _GEN_TERNARY.match(text)
    if ternary is not None:
        lhs, rhs, when_true, when_false = ternary.groups()
        if lhs in symbols and rhs in symbols:
            return int(when_true) if symbols[lhs] >= symbols[rhs] else int(when_false)
        return None
    offset = _STAT_OFFSET.match(text)
    if offset is not None:
        left = _eval_expr(offset.group(1), symbols)
        if left is not None:
            delta = int(offset.group(3))
            return left + delta if offset.group(2) == "+" else left - delta
    return None


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
