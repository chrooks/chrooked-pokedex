from pathlib import Path

from chrooked_pokedex.readers.pokeemerald.ability_parser import (
    find_ability_battle_logic,
    find_ability_species,
    parse_ability_constants,
    parse_ability_text,
)


def test_parse_define_ability_constants(tmp_path: Path) -> None:
    """Parse #define ABILITY_X N format (Chrooked)."""
    repo = tmp_path / "repo"
    _write_define_abilities(repo)

    constants = parse_ability_constants(repo)

    assert constants == {
        "ABILITY_STENCH": 1,
        "ABILITY_CACOPHONY": 76,
        "ABILITY_MULTITYPE": 80,
    }


def test_parse_enum_ability_constants(tmp_path: Path) -> None:
    """Parse enum-style ABILITY_X format (Pokeemerald)."""
    repo = tmp_path / "repo"
    _write_enum_abilities(repo)

    constants = parse_ability_constants(repo)

    assert constants == {
        "ABILITY_STENCH": 1,
        "ABILITY_DRIZZLE": 2,
        "ABILITY_TRANSISTOR": 224,
    }


def test_parse_ability_text_separate_arrays(tmp_path: Path) -> None:
    """Parse Chrooked-style separate name array + description constants."""
    repo = tmp_path / "repo"
    _write_chrooked_ability_text(repo)

    text = parse_ability_text(repo)

    assert text["ABILITY_STENCH"] == ("Stench", "Helps repel wild POKeMON.")
    assert text["ABILITY_CACOPHONY"] == ("Cacophony", "Boosts sound-based moves.")


def test_parse_ability_text_struct_format(tmp_path: Path) -> None:
    """Parse Pokeemerald-style struct AbilityInfo with .name and .description."""
    repo = tmp_path / "repo"
    _write_pokeemerald_ability_text(repo)

    text = parse_ability_text(repo)

    assert text["ABILITY_STENCH"] == ("Stench", "Helps repel wild POKeMON.")
    assert text["ABILITY_DRIZZLE"] == ("Drizzle", "Summons rain in battle.")


def test_find_ability_battle_logic_simple(tmp_path: Path) -> None:
    """Simple ability case block returns file and line count."""
    repo = tmp_path / "repo"
    _write_battle_util(repo)

    result = find_ability_battle_logic(repo, "ABILITY_CACOPHONY")

    assert result is not None
    file_path, line_count = result
    assert file_path == "src/battle_util.c"
    assert line_count == 5


def test_find_ability_battle_logic_complex(tmp_path: Path) -> None:
    """Complex ability case block returns high line count."""
    repo = tmp_path / "repo"
    _write_battle_util(repo)

    result = find_ability_battle_logic(repo, "ABILITY_MULTITYPE")

    assert result is not None
    _, line_count = result
    assert line_count > 20


def test_find_ability_battle_logic_nested_braces(tmp_path: Path) -> None:
    """Nested braces inside case block don't end count early."""
    repo = tmp_path / "repo"
    src_dir = repo / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "battle_util.c").write_text(
        """\
u32 AbilityBattleEffects(u32 caseID, u32 battler)
{
    switch (gLastUsedAbility)
    {
        case ABILITY_NESTED:
            if (condition)
            {
                doSomething();
                doMore();
            }
            effect++;
            break;
        case ABILITY_OTHER:
            break;
    }
}
""",
        encoding="utf-8",
    )

    result = find_ability_battle_logic(repo, "ABILITY_NESTED")

    assert result is not None
    _, line_count = result
    # All lines from case to break, including the nested block
    assert line_count == 8


def test_find_ability_battle_logic_missing(tmp_path: Path) -> None:
    """Ability with no case block returns None."""
    repo = tmp_path / "repo"
    _write_battle_util(repo)

    result = find_ability_battle_logic(repo, "ABILITY_NONEXISTENT")

    assert result is None


def test_find_ability_species(tmp_path: Path) -> None:
    """Find species that reference an ability in species_info."""
    repo = tmp_path / "repo"
    _write_species_info_with_abilities(repo)

    species = find_ability_species(repo, "ABILITY_CACOPHONY")

    assert species == ("SPECIES_EXPLOUD", "SPECIES_WHISMUR")


def test_find_ability_species_none_found(tmp_path: Path) -> None:
    """Ability not referenced by any species returns empty tuple."""
    repo = tmp_path / "repo"
    _write_species_info_with_abilities(repo)

    species = find_ability_species(repo, "ABILITY_NONEXISTENT")

    assert species == ()


# --- Fixture helpers ---


def _write_define_abilities(repo: Path) -> None:
    constants_dir = repo / "include" / "constants"
    constants_dir.mkdir(parents=True)
    (constants_dir / "abilities.h").write_text(
        """\
#ifndef GUARD_CONSTANTS_ABILITIES_H
#define GUARD_CONSTANTS_ABILITIES_H

#define ABILITY_NONE 0
#define ABILITY_STENCH 1
#define ABILITY_CACOPHONY 76
#define ABILITY_MULTITYPE 80

#define ABILITIES_COUNT 81

#endif // GUARD_CONSTANTS_ABILITIES_H
""",
        encoding="utf-8",
    )


def _write_enum_abilities(repo: Path) -> None:
    constants_dir = repo / "include" / "constants"
    constants_dir.mkdir(parents=True)
    (constants_dir / "abilities.h").write_text(
        """\
#ifndef GUARD_CONSTANTS_ABILITIES_H
#define GUARD_CONSTANTS_ABILITIES_H

enum {
    ABILITY_NONE,
    ABILITY_STENCH,
    ABILITY_DRIZZLE,
    ABILITIES_COUNT_GEN3,
    ABILITY_TRANSISTOR = 224,
    ABILITIES_COUNT,
};

#endif // GUARD_CONSTANTS_ABILITIES_H
""",
        encoding="utf-8",
    )


def _write_chrooked_ability_text(repo: Path) -> None:
    text_dir = repo / "src" / "data" / "text"
    text_dir.mkdir(parents=True)
    (text_dir / "abilities.h").write_text(
        """\
static const u8 sStenchDescription[] = _("Helps repel wild POKeMON.");
static const u8 sCacophonyDescription[] = _("Boosts sound-based moves.");

const u8 gAbilityNames[ABILITIES_COUNT][ABILITY_NAME_LENGTH + 1] =
{
    [ABILITY_NONE] = _("-------"),
    [ABILITY_STENCH] = _("Stench"),
    [ABILITY_CACOPHONY] = _("Cacophony"),
};

const u8 *const gAbilityDescriptionPointers[ABILITIES_COUNT] =
{
    [ABILITY_NONE] = sNoneDescription,
    [ABILITY_STENCH] = sStenchDescription,
    [ABILITY_CACOPHONY] = sCacophonyDescription,
};
""",
        encoding="utf-8",
    )


def _write_pokeemerald_ability_text(repo: Path) -> None:
    data_dir = repo / "src" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "abilities.h").write_text(
        """\
const struct AbilityInfo gAbilitiesInfo[ABILITIES_COUNT] =
{
    [ABILITY_NONE] =
    {
        .name = _("-------"),
        .description = COMPOUND_STRING("No ability."),
    },
    [ABILITY_STENCH] =
    {
        .name = _("Stench"),
        .description = COMPOUND_STRING("Helps repel wild POKeMON."),
        .aiRating = 1,
    },
    [ABILITY_DRIZZLE] =
    {
        .name = _("Drizzle"),
        .description = COMPOUND_STRING("Summons rain in battle."),
        .aiRating = 8,
    },
};
""",
        encoding="utf-8",
    )


def _write_battle_util(repo: Path) -> None:
    src_dir = repo / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    # Generate a MULTITYPE block >20 lines
    multitype_lines = "\n".join(
        f"            gBattleMons[battler].type{i} = TYPE_NORMAL;"
        for i in range(25)
    )
    (src_dir / "battle_util.c").write_text(
        f"""\
u32 AbilityBattleEffects(u32 caseID, u32 battler)
{{
    switch (gLastUsedAbility)
    {{
        case ABILITY_CACOPHONY:
            if (IsMoveSoundBased(move))
                gBattleMoveDamage = gBattleMoveDamage * 130 / 100;
            effect++;
            break;
        case ABILITY_MULTITYPE:
{multitype_lines}
            effect++;
            break;
        case ABILITY_STENCH:
            if (RandomPercentage(10))
                gBattleMons[battler].status2 |= STATUS2_FLINCHED;
            break;
    }}
}}
""",
        encoding="utf-8",
    )


def _write_species_info_with_abilities(repo: Path) -> None:
    pokemon_dir = repo / "src" / "data" / "pokemon"
    pokemon_dir.mkdir(parents=True, exist_ok=True)
    (pokemon_dir / "species_info.h").write_text(
        """\
    [SPECIES_WHISMUR] =
    {
        .baseHP = 64,
        .abilities = {ABILITY_CACOPHONY, ABILITY_NONE, ABILITY_NONE},
    },
    [SPECIES_EXPLOUD] =
    {
        .baseHP = 104,
        .abilities = {ABILITY_CACOPHONY, ABILITY_NONE, ABILITY_NONE},
    },
    [SPECIES_CHARIZARD] =
    {
        .baseHP = 78,
        .abilities = {ABILITY_BLAZE, ABILITY_NONE, ABILITY_SOLAR_POWER},
    },
""",
        encoding="utf-8",
    )
