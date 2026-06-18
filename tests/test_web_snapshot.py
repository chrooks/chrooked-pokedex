"""Milestone 0 — the committed base snapshot.

`web/snapshot.py` turns base 1.11.2 into a deterministic JSON the Canon dex
merges onto. These tests pin the write/load round-trip and idempotency with a
synthetic snapshot dict, and exercise the real reader path only when the base
checkout is present (integration).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chrooked_pokedex.web import snapshot as snap

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE = _REPO_ROOT.parent / "ROMs" / "_scratch-expansion-1.11.2"

_TINY = {
    "version": "1.11.2",
    "species": {
        "goodra": {
            "dex": 706,
            "chrooked_id": "goodra",
            "name": "Goodra",
            "types": ["Dragon"],
            "abilities": {"primary": "Sap Sipper", "secondary": None, "hidden": "Hydration"},
            "stats": {"hp": 90, "atk": 100, "def": 70, "spa": 110, "spd": 150, "spe": 60},
            "learnset": [{"level": 1, "move": "Dragon Breath"}],
        },
    },
    "moves": {},
    "abilities": {},
    "type_chart": [],
}


def test_write_then_load_roundtrips(tmp_path: Path) -> None:
    out = tmp_path / "1.11.2.json"
    snap.write_snapshot(_TINY, out)
    assert snap.load_snapshot(out) == _TINY


def test_write_is_deterministic_and_idempotent(tmp_path: Path) -> None:
    out = tmp_path / "1.11.2.json"
    snap.write_snapshot(_TINY, out)
    first = out.read_bytes()
    snap.write_snapshot(_TINY, out)
    assert out.read_bytes() == first  # byte-identical on a second run


def test_write_creates_missing_parent_dir(tmp_path: Path) -> None:
    out = tmp_path / ".base" / "1.11.2.json"
    snap.write_snapshot(_TINY, out)
    assert out.exists()


def test_national_dex_map_is_positional_and_ignores_trailing_defines(tmp_path: Path) -> None:
    header = tmp_path / "include" / "constants" / "pokedex.h"
    header.parent.mkdir(parents=True)
    header.write_text(
        "enum {\n"
        "    NATIONAL_DEX_NONE,\n"
        "    NATIONAL_DEX_BULBASAUR,\n"
        "    NATIONAL_DEX_IVYSAUR,\n"
        "};\n"
        # A trailing #define that must NOT bump the counter.
        "#define NATIONAL_DEX_COUNT NATIONAL_DEX_IVYSAUR\n",
        encoding="utf-8",
    )
    numbers = snap._national_dex_map(tmp_path)
    assert numbers["NATIONAL_DEX_NONE"] == 0
    assert numbers["NATIONAL_DEX_BULBASAUR"] == 1
    assert numbers["NATIONAL_DEX_IVYSAUR"] == 2


def test_national_dex_map_handles_a_tagged_enum(tmp_path: Path) -> None:
    # Some forks write a named enum (`enum NationalDexOrder {`) rather than the
    # anonymous `enum {` base 1.11.2 uses. Both must parse, or every species'
    # dex number resolves to None (the "---" backdrop bug).
    header = tmp_path / "include" / "constants" / "pokedex.h"
    header.parent.mkdir(parents=True)
    header.write_text(
        "enum NationalDexOrder\n"
        "{\n"
        "    NATIONAL_DEX_NONE,\n"
        "    NATIONAL_DEX_BULBASAUR,\n"
        "    NATIONAL_DEX_IVYSAUR,\n"
        "};\n",
        encoding="utf-8",
    )
    numbers = snap._national_dex_map(tmp_path)
    assert numbers["NATIONAL_DEX_NONE"] == 0
    assert numbers["NATIONAL_DEX_BULBASAUR"] == 1
    assert numbers["NATIONAL_DEX_IVYSAUR"] == 2


def test_resolve_dex_handles_symbol_and_bare_integer() -> None:
    numbers = {"NATIONAL_DEX_GOODRA": 706}
    assert snap._resolve_dex("NATIONAL_DEX_GOODRA", numbers) == 706
    assert snap._resolve_dex("706", numbers) == 706  # some forks inline the number
    assert snap._resolve_dex(None, numbers) is None


def test_eval_define_reads_plain_integer() -> None:
    assert snap._eval_define("150", {}) == 150
    assert snap._eval_define("234  // expyield", {}) == 234


def test_eval_define_resolves_config_gated_ternary() -> None:
    config = {"P_UPDATED_STATS": 8, "GEN_8": 7, "GEN_6": 5}
    # 8 >= 7 -> the modern (first) value
    assert (
        snap._eval_define("(P_UPDATED_STATS >= GEN_8 ? 140 : 150)", config) == 140
    )
    # a config below the gate takes the legacy value
    assert (
        snap._eval_define("(P_UPDATED_STATS >= GEN_8 ? 140 : 150)", {"P_UPDATED_STATS": 5, "GEN_8": 7})
        == 150
    )


def test_eval_define_returns_none_for_unsupported_shape() -> None:
    assert snap._eval_define("SOME_OTHER_MACRO", {}) is None
    assert snap._eval_define("(a + b)", {}) is None


def test_eval_expr_resolves_symbols_ternaries_and_offsets() -> None:
    symbols = {"P_UPDATED_STATS": 8, "GEN_7": 6, "ALAKAZAM_SP_DEF": 95, "CORSOLA_HP": 65}
    assert snap._eval_expr("130", symbols) == 130
    assert snap._eval_expr("ALAKAZAM_SP_DEF", symbols) == 95
    assert snap._eval_expr("P_UPDATED_STATS >= GEN_7 ? 95 : 85", symbols) == 95
    # macro with an integer offset, both directions
    assert snap._eval_expr("ALAKAZAM_SP_DEF + 10", symbols) == 105
    assert snap._eval_expr("CORSOLA_HP - 5", symbols) == 60
    assert snap._eval_expr("UNKNOWN_MACRO", symbols) is None


def test_base_abilities_map_reads_neutral_name_and_description(tmp_path: Path) -> None:
    # A minimal struct-format pokeemerald fork: the ability reader returns
    # (name, description) already neutral of engine tokens; build keys it by the
    # slug of the name and flattens textbox control codes out of the description.
    data = tmp_path / "src" / "data"
    data.mkdir(parents=True)
    (data / "abilities.h").write_text(
        "const struct AbilityInfo gAbilitiesInfo[ABILITIES_COUNT] =\n"
        "{\n"
        "    [ABILITY_OVERGROW] =\n"
        "    {\n"
        '        .name = _("Overgrow"),\n'
        '        .description = COMPOUND_STRING("Ups Grass moves\\nin a pinch."),\n'
        "    },\n"
        "};\n",
        encoding="utf-8",
    )
    abilities = snap._base_abilities_map(tmp_path)
    assert "overgrow" in abilities
    entry = abilities["overgrow"]
    assert entry["chrooked_id"] == "overgrow"
    assert entry["name"] == "Overgrow"
    # Control code \n flattened to a single space (charmap safety).
    assert entry["description"] == "Ups Grass moves in a pinch."
    assert entry["aka"] == {"pokeemerald": "ABILITY_OVERGROW"}


def test_base_moves_map_neutralizes_engine_tokens(tmp_path: Path) -> None:
    # ac5: the move reader returns engine TOKENS (TYPE_*, EFFECT_*, MOVE_TARGET_*,
    # MOVE_EFFECT_*, camelCase flags). _base_moves_map must store them NEUTRAL —
    # plain names, no raw ALL_CAPS engine token in the diffable fields.
    data = tmp_path / "src" / "data"
    data.mkdir(parents=True)
    (data / "moves_info.h").write_text(
        "const struct MoveInfo gMovesInfo[MOVES_COUNT] =\n"
        "{\n"
        "    [MOVE_THUNDER_PUNCH] =\n"
        "    {\n"
        '        .name = COMPOUND_STRING("Thunder Punch"),\n'
        "        .type = TYPE_ELECTRIC,\n"
        "        .category = DAMAGE_CATEGORY_PHYSICAL,\n"
        "        .power = 75,\n"
        "        .accuracy = 100,\n"
        "        .pp = 15,\n"
        '        .description = COMPOUND_STRING("An electrified\\npunch."),\n'
        "        .effect = EFFECT_HIT,\n"
        "        .target = MOVE_TARGET_SELECTED,\n"
        "        .priority = 0,\n"
        "        .makesContact = TRUE,\n"
        "        .punchingMove = TRUE,\n"
        "        .additionalEffects = ADDITIONAL_EFFECTS({\n"
        "            .moveEffect = MOVE_EFFECT_PARALYSIS,\n"
        "            .chance = 10,\n"
        "        }),\n"
        "    },\n"
        "};\n",
        encoding="utf-8",
    )
    moves = snap._base_moves_map(tmp_path)
    assert "thunderpunch" in moves
    entry = moves["thunderpunch"]
    assert entry["chrooked_id"] == "thunderpunch"
    assert entry["name"] == "Thunder Punch"
    assert entry["aka"] == {"pokeemerald": "MOVE_THUNDER_PUNCH"}
    # Neutral values — no engine tokens.
    assert entry["type"] == "Electric"
    assert entry["category"] == "physical"
    assert entry["effect"] == "hit"
    assert entry["target"] == "selected"
    assert sorted(entry["flags"]) == ["contact", "punching"]
    assert entry["additional_effects"] == [{"effect": "paralysis", "chance": 10}]
    # Control code \n flattened to a single space (charmap safety).
    assert entry["description"] == "An electrified punch."
    # Hard guard: no raw ALL_CAPS engine token leaks into the diffable fields.
    import re as _re

    diffable = {k: v for k, v in entry.items() if k != "aka"}
    assert not _re.search(
        r"TYPE_|EFFECT_|MOVE_TARGET_|MOVE_EFFECT_|DAMAGE_CATEGORY_|FLAG_|\bTRUE\b",
        str(diffable),
    ), diffable


@pytest.mark.integration
@pytest.mark.skipif(not _BASE.exists(), reason="base 1.11.2 checkout not present")
def test_build_snapshot_populates_base_moves() -> None:
    # ac1: build_snapshot fills the moves map from the fork, keyed by chrooked_id,
    # with a known move's neutral fields.
    moves = snap.build_snapshot(_BASE)["moves"]
    assert moves  # non-empty
    assert "tackle" in moves
    tackle = moves["tackle"]
    assert tackle["name"] == "Tackle"
    assert tackle["type"] == "Normal"
    assert tackle["category"] == "physical"
    assert tackle["aka"] == {"pokeemerald": "MOVE_TACKLE"}


@pytest.mark.integration
@pytest.mark.skipif(not _BASE.exists(), reason="base 1.11.2 checkout not present")
def test_build_snapshot_base_moves_are_neutral_no_token_leak() -> None:
    # ac5: across the WHOLE base move set, the contract's diffable fields carry no
    # raw engine tokens (aka legitimately keeps the MOVE_* symbol, so it's excluded).
    import re as _re

    moves = snap.build_snapshot(_BASE)["moves"]
    token = _re.compile(
        r"TYPE_[A-Z]|EFFECT_[A-Z]|MOVE_TARGET_|DAMAGE_CATEGORY_|FLAG_[A-Z]"
    )
    for cid, entry in moves.items():
        for field in ("type", "category", "effect", "target", "flags"):
            assert not token.search(str(entry[field])), (cid, field, entry[field])


def test_base_type_chart_reads_full_grid_neutral_floats(tmp_path: Path) -> None:
    # ac1: parse_type_chart already yields neutral type names + resolved floats;
    # _base_type_chart emits one {attacker, defender, multiplier} per cell, sorted
    # by (attacker, defender), turning an unresolved (None) token into 1.0.
    data = tmp_path / "src" / "data"
    data.mkdir(parents=True)
    # Positional rows (column order = row order), as the real engine writes it.
    (data / "types_info.h").write_text(
        "const uq4_12_t gTypeEffectivenessTable"
        "[NUMBER_OF_MON_TYPES][NUMBER_OF_MON_TYPES] =\n"
        "{//                  Normal  Rock\n"
        "    [TYPE_NORMAL] = {______, X(0.5)},\n"
        "    [TYPE_ROCK]   = {X(2.0), ______},\n"
        "};\n",
        encoding="utf-8",
    )
    chart = snap._base_type_chart(tmp_path)
    # sorted by (attacker, defender): Normal/Normal, Normal/Rock, Rock/Normal, Rock/Rock
    assert chart == [
        {"attacker": "Normal", "defender": "Normal", "multiplier": 1.0},
        {"attacker": "Normal", "defender": "Rock", "multiplier": 0.5},
        {"attacker": "Rock", "defender": "Normal", "multiplier": 2.0},
        {"attacker": "Rock", "defender": "Rock", "multiplier": 1.0},
    ]
    # every multiplier is a float, every type name neutral (no TYPE_ token)
    assert all(isinstance(c["multiplier"], float) for c in chart)
    assert not any("TYPE_" in c["attacker"] or "TYPE_" in c["defender"] for c in chart)


def test_base_type_chart_drops_engine_placeholder_types(tmp_path: Path) -> None:
    # fix1: None/Mystery/Stellar are engine placeholders, not real battle types.
    # Any cell whose attacker OR defender is one of them is skipped, so the
    # snapshot carries one 18×18 type universe shared by API + frontend.
    data = tmp_path / "src" / "data"
    data.mkdir(parents=True)
    (data / "types_info.h").write_text(
        "const uq4_12_t gTypeEffectivenessTable"
        "[NUMBER_OF_MON_TYPES][NUMBER_OF_MON_TYPES] =\n"
        "{//                    Normal  Mystery  Stellar\n"
        "    [TYPE_NORMAL]  = {______, ______,  ______},\n"
        "    [TYPE_MYSTERY] = {______, ______,  ______},\n"
        "    [TYPE_STELLAR] = {______, ______,  ______},\n"
        "};\n",
        encoding="utf-8",
    )
    chart = snap._base_type_chart(tmp_path)
    types = {c["attacker"] for c in chart} | {c["defender"] for c in chart}
    assert snap._NON_BATTLE_TYPES.isdisjoint(types)
    # only the Normal/Normal cell survives the placeholder rows + columns.
    assert chart == [{"attacker": "Normal", "defender": "Normal", "multiplier": 1.0}]


@pytest.mark.integration
@pytest.mark.skipif(not _BASE.exists(), reason="base 1.11.2 checkout not present")
def test_build_snapshot_populates_base_type_chart() -> None:
    # ac1: build_snapshot fills the type_chart from the fork as a full grid of
    # neutral-named cells with float multipliers — the 18 real battle types only
    # (engine placeholders None/Mystery/Stellar are dropped at this boundary).
    chart = snap.build_snapshot(_BASE)["type_chart"]
    assert chart  # non-empty
    types = {c["attacker"] for c in chart} | {c["defender"] for c in chart}
    assert "Water" in types and "Fire" in types
    # exactly the 18 real battle types, no engine placeholders
    assert len(types) == 18
    assert snap._NON_BATTLE_TYPES.isdisjoint(types)
    # full square grid over the 18 real types: 18 × 18 = 324 cells
    assert len(chart) == 324
    assert len(chart) == len(types) ** 2
    # a canon pair resolves to its known multiplier (Water super-effective on Fire)
    water_fire = next(
        c for c in chart if c["attacker"] == "Water" and c["defender"] == "Fire"
    )
    assert water_fire["multiplier"] == 2.0
    assert isinstance(water_fire["multiplier"], float)


@pytest.mark.integration
@pytest.mark.skipif(not _BASE.exists(), reason="base 1.11.2 checkout not present")
def test_build_snapshot_from_real_base() -> None:
    built = snap.build_snapshot(_BASE)
    assert built["version"] == "1.11.2"
    goodra = built["species"]["goodra"]
    assert goodra["dex"] == 706
    assert "Dragon" in goodra["types"]
    assert set(goodra["stats"]) == {"hp", "atk", "def", "spa", "spd", "spe"}
    assert goodra["learnset"]  # base Goodra learns moves
    # Pikachu rides along unchanged in the full national dex.
    assert "pikachu" in built["species"]


@pytest.mark.integration
@pytest.mark.skipif(not _BASE.exists(), reason="base 1.11.2 checkout not present")
def test_build_snapshot_populates_evolution_both_directions() -> None:
    # ac1: the snapshot carries the full evolution graph. Buizel evolves into
    # Floatzel at Level 26 (forward), and Floatzel inverts that into its pre-evo.
    species = snap.build_snapshot(_BASE)["species"]

    buizel = species["buizel"]
    [edge] = buizel["evolves_into"]
    assert edge["to"] == "floatzel"
    assert edge["to_name"] == "Floatzel"
    assert edge["method"] == "Level 26"
    assert edge["method_detail"] == {"kind": "EVO_LEVEL", "param": "26"}
    assert edge["to_dex"] == species["floatzel"]["dex"]
    assert buizel["evolution"] is None  # Buizel has no pre-evo
    assert buizel["fully_evolved"] is False

    floatzel = species["floatzel"]
    assert floatzel["evolution"]["from"] == "buizel"
    assert floatzel["evolution"]["from_name"] == "Buizel"
    assert floatzel["evolution"]["method"] == "Level 26"
    assert floatzel["evolution"]["from_dex"] == buizel["dex"]
    assert floatzel["evolves_into"] == []
    assert floatzel["fully_evolved"] is True


@pytest.mark.integration
@pytest.mark.skipif(not _BASE.exists(), reason="base 1.11.2 checkout not present")
def test_build_snapshot_evolution_handles_branching() -> None:
    # ac1: a branching evolver (Eevee) lists every forward target, and each
    # target inverts Eevee as its single pre-evo.
    species = snap.build_snapshot(_BASE)["species"]
    eevee = species["eevee"]
    targets = {e["to"] for e in eevee["evolves_into"]}
    # The classic three stones are all present among Eevee's many branches.
    assert {"vaporeon", "jolteon", "flareon"} <= targets
    assert len(eevee["evolves_into"]) >= 3
    # No raw EVO_* token leaks into the readable method label.
    assert all(not e["method"].startswith("EVO_") for e in eevee["evolves_into"])
    # The inverse: each branch names Eevee as its pre-evo.
    assert species["vaporeon"]["evolution"]["from"] == "eevee"
    assert species["jolteon"]["evolution"]["from_name"] == "Eevee"


@pytest.mark.integration
@pytest.mark.skipif(not _BASE.exists(), reason="base 1.11.2 checkout not present")
def test_build_snapshot_populates_base_abilities() -> None:
    # ac1: build_snapshot fills the abilities map from the fork, keyed by
    # chrooked_id, with a known ability's neutral name + description.
    abilities = snap.build_snapshot(_BASE)["abilities"]
    assert abilities  # non-empty
    assert "overgrow" in abilities
    overgrow = abilities["overgrow"]
    assert overgrow["name"] == "Overgrow"
    assert overgrow["description"]  # has a neutral description
    assert overgrow["aka"] == {"pokeemerald": "ABILITY_OVERGROW"}


@pytest.mark.integration
@pytest.mark.skipif(not _BASE.exists(), reason="base 1.11.2 checkout not present")
def test_symbolic_form_stats_are_resolved_not_dropped() -> None:
    # Forms whose stats are named macros (AEGISLASH_MAIN_STAT etc.) must resolve
    # to their real values, not vanish. P_UPDATED_STATS = GEN_LATEST, so the
    # modern values apply (Aegislash main stat 140, Alakazam SpDef 95).
    species = snap.build_snapshot(_BASE)["species"]
    blade = species["aegislashblade"]["stats"]
    shield = species["aegislashshield"]["stats"]
    assert blade["atk"] == 140 and blade["spa"] == 140
    assert shield["def"] == 140 and shield["spd"] == 140
    # every form carries the full six stats now
    assert set(blade) == {"hp", "atk", "def", "spa", "spd", "spe"}
    assert species["alakazam"]["stats"]["spd"] == 95
