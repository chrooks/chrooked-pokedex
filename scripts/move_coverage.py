"""Audit the move-coverage matrix: type x phys/spec x base-power band.

An editorial tool over the Ruleset, like ``scripts/build_tags.py`` — stdlib +
PyYAML, no import surface into the app. It answers three questions:

    python scripts/move_coverage.py gaps            # which (type, split, band) cells are blank
    python scripts/move_coverage.py counts <id>...  # how many species learn each move
    python scripts/move_coverage.py check <id>...   # do these moves obey effect map + band conventions

A "cell" is (type, split, band). A cell is FILLED when a ladder-eligible move
(no priority / multi-hit / charge / variable / self-KO / Z-Max) lands in it and
is learned by >= 18 species at level-up, OR the move is a Ruleset ("custom")
move regardless of learner count.

Data flow: base snapshot -> fill null powers from the embedded canon table ->
overlay ruleset/moves/*.yaml -> rebuild learnsets (base, then whole-file
replacement for any species YAML carrying ``learnset:``) -> count learners.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Mapping, NamedTuple, Optional, Union

import yaml

try:  # C loader when the wheel ships it; ~5x faster over ~2k YAML files.
    from yaml import CSafeLoader as _SafeLoader
except ImportError:  # pragma: no cover - pure-Python fallback
    from yaml import SafeLoader as _SafeLoader

ROOT = Path(__file__).resolve().parent.parent
RULESET = ROOT / "ruleset"
BASE_SNAPSHOT = RULESET / ".base" / "1.11.2.json"

# --- Domain constants --------------------------------------------------------

COMMON_THRESHOLD = 18  # a cell is "common" at >= this many level-up learners

# Band bounds come from the shared band Contract (learnset_rubric.json) so
# coverage bands and the pacing rubric are tuned in one file. Reading the app's
# data file is not an app import — this script stays stdlib+PyYAML.
_BAND_CONTRACT = json.loads(
    (ROOT / "src" / "chrooked_pokedex" / "web" / "learnset_rubric.json")
    .read_text("utf-8")
)["coverage_bands"]

# 1 = sentinel for variable-power moves; real weak moves count.
MIN_LADDER_POWER: int = _BAND_CONTRACT["min_ladder_power"]

# Moves Chris ruled too flavor- or effect-specific to be ladder rungs, even
# though they pass the mechanical filters (2026-07-25 review). Trap-family
# moves ride along with Whirlpool — same partial-trapping effect class.
# Now stored in the shared band Contract (learnset_rubric.json:
# coverage_bands.rung_exclusions) so the web slot skeleton honors the same
# curation when it builds rung candidate lists.
CURATED_EXCLUSIONS: frozenset[str] = frozenset(_BAND_CONTRACT["rung_exclusions"])

# Body-plan-specific moves (fangs, punches, tails, blades...) need a specific
# anatomy in a way Flamethrower or Acid does not. They still count as ladder
# moves, but a cell whose only common moves are body-specific is flagged
# "body-only" — it wants a body-neutral companion.
BODY_SPECIFIC_RE = re.compile(
    r"fang|punch|kick|tail|claw|slash|blade|wing|bone|horn|drill|peck",
    re.IGNORECASE,
)

# 18 real types, in matrix order. Excludes '', None, Typeless, ???.
TYPES: tuple[str, ...] = (
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting",
    "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost",
    "Dragon", "Dark", "Steel", "Fairy",
)
REAL_TYPES = frozenset(TYPES)
SPLITS: tuple[str, ...] = ("physical", "special")

# Bands are upper-inclusive. A move's band is the last edge <= its power.
# First band opens at 2 so weak starter rungs (Poison Sting 15, Mud-Slap 20,
# Absorb 30) count; power 1 stays out as the variable-power sentinel.
BAND_EDGES: tuple[tuple[int, str], ...] = tuple(
    (edge["min_power"], edge["label"]) for edge in _BAND_CONTRACT["edges"]
)
BAND_LABELS: tuple[str, ...] = tuple(label for _, label in BAND_EDGES)

# Move effect names that disqualify a move from being an ordinary ladder rung.
EXCLUDED_EFFECTS = frozenset({
    "multi_hit", "max_move", "ohko", "explosion", "two_turns_attack",
    "semi_invulnerable", "power_based_on_target_hp", "power_based_on_user_hp",
    "super_fang", "return", "counter", "mirror_coat", "metal_burst", "bide",
    "present", "magnitude", "psywave", "flail", "frustration", "pledge",
    "fling", "natural_gift", "spit_up", "beat_up", "sky_drop", "solar_beam",
    "meteor_beam",
})

# Two-hit heuristic: multi_hit tags the 2-to-5 movers, but fixed two-hitters
# (Double Kick, Dragon Darts...) hide behind a plain effect, so fall back to
# the description. Matches "hits twice", "two to five times", "three times",
# "consecutively in a row".
_TWO_HIT_RE = re.compile(
    r"twice|two to five|2 to 5|three times|consecutively in a row",
    re.IGNORECASE,
)

# --- D1 effect map + D3 band conventions (the `check` audit source) ----------
#
# Concrete effect ids use the ruleset additional_effects vocabulary (see
# ruleset/moves/*.yaml). Grass "drain" is the move.effect == "absorb" marker,
# not an additional_effect. Split-typed entries (Fighting/Rock/Ghost) map
# split -> effect.

EffectSpec = Union[None, str, dict[str, str]]

EFFECT_MAP: dict[str, EffectSpec] = {
    "Normal": None,
    "Fire": "burn",
    "Water": "flinch",
    "Electric": "paralysis",
    "Grass": "drain",
    "Ice": "freeze",
    "Fighting": {"physical": "def_minus_1", "special": "sp_def_minus_1"},
    "Poison": "poison",
    "Ground": "spd_minus_1",
    "Flying": None,
    "Psychic": "confusion",
    "Bug": "sp_atk_minus_1",
    "Rock": {"physical": "def_minus_1", "special": "sp_def_minus_1"},
    "Ghost": {"physical": "def_minus_1", "special": "sp_def_minus_1"},
    "Dragon": None,
    "Dark": "flinch",
    "Steel": {"physical": "flinch", "special": "acc_minus_1"},
    "Fairy": "sp_atk_minus_1",
}

BAND_CONVENTIONS: dict[str, dict[str, int]] = {
    "≤50": {"accuracy": 100, "pp": 30},
    "51-75": {"accuracy": 100, "pp": 25},
    "76-90": {"accuracy": 100, "pp": 15},
    "91-110": {"accuracy": 90, "pp": 10},
    ">110": {"accuracy": 90, "pp": 5},
}

STATUS_EFFECTS = frozenset({
    "burn", "paralysis", "freeze", "flinch", "confusion", "poison",
})
STAT_DROP_EFFECTS = frozenset({
    "def_minus_1", "sp_def_minus_1", "spd_minus_1", "sp_atk_minus_1",
    "atk_minus_1", "acc_minus_1",
})
KNOWN_SECONDARY = STATUS_EFFECTS | STAT_DROP_EFFECTS

STATUS_CHANCE = 10
STAT_DROP_CHANCE: dict[str, int] = {
    "≤50": 100, "51-75": 100, "76-90": 20, "91-110": 20, ">110": 30,
}

# Renaming a band label in learnset_rubric.json must fail HERE, loudly, not as
# a silent KeyError deep in an audit — these tables are keyed by label.
assert set(BAND_LABELS) == set(BAND_CONVENTIONS) == set(STAT_DROP_CHANCE), (
    f"band labels in learnset_rubric.json {BAND_LABELS} no longer match "
    "BAND_CONVENTIONS / STAT_DROP_CHANCE keys — update them together"
)


# --- Pool assembly -----------------------------------------------------------


class Pool(NamedTuple):
    """The merged move universe plus per-move learner counts."""

    moves: dict[str, dict]      # chrooked_id -> resolved move dict
    custom: frozenset[str]      # ids carrying a ruleset/moves/*.yaml
    learners: dict[str, int]    # chrooked_id -> distinct level-up learners


def band_of(power: Optional[int]) -> Optional[str]:
    """Return the band label for a base power, or None below MIN_LADDER_POWER."""
    if power is None or power < MIN_LADDER_POWER:
        return None
    label: Optional[str] = None
    for edge, name in BAND_EDGES:
        if power >= edge:
            label = name
    return label


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = yaml.load(handle, Loader=_SafeLoader)
    return data if isinstance(data, dict) else {}


def merge_ruleset_moves(
    base_moves: Mapping[str, dict], moves_dir: Path
) -> tuple[dict[str, dict], frozenset[str]]:
    """Overlay ruleset/moves/*.yaml onto the base pool.

    Non-None YAML fields win over the base entry; net-new ids become new moves.
    Returns (merged_moves, custom_ids).
    """
    merged: dict[str, dict] = {mid: dict(m) for mid, m in base_moves.items()}
    custom: set[str] = set()
    for path in sorted(moves_dir.glob("*.yaml")):
        y = _load_yaml(path)
        mid = y.get("chrooked_id") or path.stem
        custom.add(mid)
        entry = dict(merged.get(mid, {}))
        for key, value in y.items():
            if value is not None:
                entry[key] = value
        entry.setdefault("chrooked_id", mid)
        merged[mid] = entry
    return merged, frozenset(custom)


def build_learnsets(
    base_species: Mapping[str, dict], species_dir: Path
) -> dict[str, list[dict]]:
    """Base learnsets, then whole-file replacement for species YAMLs with one."""
    learnsets: dict[str, list[dict]] = {
        sid: list(sp.get("learnset") or [])
        for sid, sp in base_species.items()
    }
    for path in sorted(species_dir.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        if "learnset:" not in text:  # skip parse for the common no-learnset file
            continue
        y = yaml.load(text, Loader=_SafeLoader)
        if not isinstance(y, dict) or "learnset" not in y:
            continue
        sid = y.get("chrooked_id") or path.stem
        learnsets[sid] = list(y.get("learnset") or [])
    return learnsets


def count_learners(
    moves: Mapping[str, dict], learnsets: Mapping[str, list[dict]]
) -> dict[str, int]:
    """Count distinct species that learn each move, by case-insensitive name."""
    name_to_id: dict[str, str] = {}
    for mid, move in moves.items():
        name = move.get("name")
        if name:
            name_to_id[name.casefold()] = mid
    counts: dict[str, int] = {mid: 0 for mid in moves}
    for rows in learnsets.values():
        seen: set[str] = set()
        for row in rows:
            display = row.get("move")
            if not display:
                continue
            mid = name_to_id.get(display.casefold())
            if mid is not None:
                seen.add(mid)
        for mid in seen:
            counts[mid] += 1
    return counts


def build_pool(ruleset_dir: Path = RULESET) -> Pool:
    """Assemble the merged move pool and learner counts from a ruleset tree."""
    base = json.loads((ruleset_dir / ".base" / "1.11.2.json").read_text("utf-8"))
    moves, custom = merge_ruleset_moves(base["moves"], ruleset_dir / "moves")
    learnsets = build_learnsets(base["species"], ruleset_dir / "species")
    learners = count_learners(moves, learnsets)
    return Pool(moves=moves, custom=custom, learners=learners)


# --- Ladder filter + cell fill -----------------------------------------------


def is_ladder_eligible(move: Mapping) -> bool:
    """True when the move is an ordinary damaging ladder rung (see module docstring)."""
    if move.get("category") not in ("physical", "special"):
        return False
    power = move.get("power")
    if power is None or power < MIN_LADDER_POWER:
        return False
    priority = move.get("priority") or 0  # net-new moves omit priority (== 0)
    if priority != 0:
        return False
    pp = move.get("pp")
    # pp None = hidden behind a gen-config ternary in the base source (drain
    # family); unknown is fine — only a literal 1 (Z/Max) disqualifies.
    if pp is not None and pp <= 1:
        return False
    if move.get("chrooked_id") in CURATED_EXCLUSIONS:
        return False
    if move.get("effect") in EXCLUDED_EFFECTS:
        return False
    if _TWO_HIT_RE.search(move.get("description") or ""):
        return False
    if move.get("type") not in REAL_TYPES:
        return False
    return True


def is_body_specific(move: Mapping) -> bool:
    """True when the move's name implies a body plan (fang, punch, tail...)."""
    return bool(BODY_SPECIFIC_RE.search(move.get("name") or ""))


def filled_cells(pool: Pool) -> tuple[set[tuple[str, str, str]], set[tuple[str, str, str]]]:
    """(cells with any common move, cells with a body-NEUTRAL common move)."""
    filled: set[tuple[str, str, str]] = set()
    neutral: set[tuple[str, str, str]] = set()
    for mid, move in pool.moves.items():
        if not is_ladder_eligible(move):
            continue
        common = mid in pool.custom or pool.learners.get(mid, 0) >= COMMON_THRESHOLD
        if not common:
            continue
        cell = (move["type"], move["category"], band_of(move["power"]))
        filled.add(cell)
        if not is_body_specific(move):
            neutral.add(cell)
    return filled, neutral


# --- Conformance audit (`check`) ---------------------------------------------


def _expected_effect(move_type: str, split: str) -> EffectSpec:
    spec = EFFECT_MAP.get(move_type)
    if isinstance(spec, dict):
        return spec.get(split)
    return spec


def _expected_chance(effect: str, band: str) -> Optional[int]:
    if effect in STATUS_EFFECTS:
        return STATUS_CHANCE
    if effect in STAT_DROP_EFFECTS:
        return STAT_DROP_CHANCE[band]
    return None


def _drawback_deviations(mid: str, split: str, move: Mapping) -> list[str]:
    # ponytail: no >110 move exists yet, so this branch is unexercised. Encoded
    # to the likely shape — phys drawback == move.effect 'recoil', spec drawback
    # == additional 'sp_atk_minus_2'. Retune to the id the move-design skill
    # actually emits when the first >110 rung lands.
    if split == "physical":
        if move.get("effect") != "recoil":
            return [f"{mid}: drawback expected recoil got {move.get('effect')}"]
        return []
    effects = {ae.get("effect") for ae in (move.get("additional_effects") or [])}
    # Standard special >110 drawback: user's Sp. Atk falls two steps (Draco
    # Meteor / Overheat, funccode 0x03F).
    if "sp_atk_minus_2" in effects:
        return []
    # Type-flavored variant (Sinkhole): the caster sinks — Sp. Atk AND Speed each
    # -1. No vanilla funccode does both, so a behavior (chrooked_sinkhole) applies
    # it; the data carries both markers so this audit passes.
    if {"sp_atk_minus_1", "spd_minus_1"} <= effects:
        return []
    got = sorted(e for e in effects if e) or "none"
    return [f"{mid}: drawback expected sp_atk_minus_2 or sp_atk_minus_1+spd_minus_1 got {got}"]


def audit_move(mid: str, move: Mapping) -> list[str]:
    """Report every way a move deviates from the D1 effect map + D3 conventions."""
    deviations: list[str] = []
    move_type = move.get("type")
    split = move.get("category")
    band = band_of(move.get("power"))
    if band is None:
        return [f"{mid}: power expected >={MIN_LADDER_POWER} got {move.get('power')}"]

    conv = BAND_CONVENTIONS[band]
    if move.get("accuracy") != conv["accuracy"]:
        deviations.append(f"{mid}: accuracy expected {conv['accuracy']} got {move.get('accuracy')}")
    if move.get("pp") != conv["pp"]:
        deviations.append(f"{mid}: pp expected {conv['pp']} got {move.get('pp')}")

    # At >110 the drawback IS the secondary (D21): a top-band nuke carries its
    # self-cost (phys recoil / spec -2 SpA) instead of the type's target effect,
    # matching canon (Overheat, Head Smash, Double-Edge carry no target effect).
    if band == ">110":
        deviations.extend(_drawback_deviations(mid, split, move))
        return deviations

    expected = _expected_effect(move_type, split)
    present = {ae.get("effect"): ae.get("chance") for ae in (move.get("additional_effects") or [])}
    if expected is None:
        stray = next((e for e in present if e in KNOWN_SECONDARY), None)
        if stray is not None:
            deviations.append(f"{mid}: effect expected none got {stray}")
    elif expected == "drain":
        if move.get("effect") != "absorb":
            deviations.append(f"{mid}: effect expected absorb got {move.get('effect')}")
    else:
        if expected not in present:
            got = next((e for e in present if e in KNOWN_SECONDARY), "none")
            deviations.append(f"{mid}: effect expected {expected} got {got}")
        else:
            want = _expected_chance(expected, band)
            if present[expected] != want:
                deviations.append(f"{mid}: chance expected {want} got {present[expected]}")

    return deviations


# --- Subcommands -------------------------------------------------------------


def cmd_gaps(pool: Pool) -> int:
    filled, neutral = filled_cells(pool)
    blank_rows: list[tuple[str, str, list[str]]] = []
    body_rows: list[tuple[str, str, list[str]]] = []
    total_blank = total_body = 0
    for move_type in TYPES:
        for split in SPLITS:
            missing = [b for b in BAND_LABELS if (move_type, split, b) not in filled]
            body_only = [
                b for b in BAND_LABELS
                if (move_type, split, b) in filled and (move_type, split, b) not in neutral
            ]
            if missing:
                total_blank += len(missing)
                blank_rows.append((move_type, split, missing))
            if body_only:
                total_body += len(body_only)
                body_rows.append((move_type, split, body_only))
    print(f"{total_blank} blank cells across {len(blank_rows)} rows")
    for move_type, split, missing in blank_rows:
        print(f"{move_type} {split}: {', '.join(missing)}")
    print(f"\n{total_body} body-only cells (common moves exist, all body-specific) "
          f"across {len(body_rows)} rows")
    for move_type, split, body_only in body_rows:
        print(f"{move_type} {split}: {', '.join(body_only)}")
    return 0


def cmd_counts(pool: Pool, ids: list[str]) -> int:
    exit_code = 0
    for mid in ids:
        move = pool.moves.get(mid)
        if move is None:
            print(f"error: unknown move id '{mid}'", file=sys.stderr)
            exit_code = 2
            continue
        print(f"{mid} {move.get('name')} n={pool.learners.get(mid, 0)}")
    return exit_code


def cmd_check(pool: Pool, ids: list[str]) -> int:
    exit_code = 0
    for mid in ids:
        move = pool.moves.get(mid)
        if move is None:
            print(f"{mid}: unknown move id")
            exit_code = 1
            continue
        deviations = audit_move(mid, move)
        for line in deviations:
            print(line)
        if deviations:
            exit_code = 1
    return exit_code


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("gaps", help="print blank (type, split, band) cells")
    counts = sub.add_parser("counts", help="learner count per move id")
    counts.add_argument("ids", nargs="+")
    check = sub.add_parser("check", help="audit moves against effect map + band conventions")
    check.add_argument("ids", nargs="+")

    args = parser.parse_args(argv)
    pool = build_pool()
    if args.command == "gaps":
        return cmd_gaps(pool)
    if args.command == "counts":
        return cmd_counts(pool, args.ids)
    if args.command == "check":
        return cmd_check(pool, args.ids)
    return 1  # pragma: no cover - argparse enforces a valid command


if __name__ == "__main__":
    raise SystemExit(main())
