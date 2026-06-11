from chrooked_pokedex.readers.pokeemerald.species_parser import parse_species_profiles


def test_parse_flat_species_info_preserves_allowed_source_expressions(tmp_path):
    source_repo = tmp_path / "PKMN-Chrooked-HnS"
    pokemon_dir = source_repo / "src" / "data" / "pokemon"
    pokemon_dir.mkdir(parents=True)
    (pokemon_dir / "species_info.h").write_text(
        """
        const struct SpeciesInfo gSpeciesInfo[] =
        {
            [SPECIES_CHARIZARD] =
            {
                .baseHP        = 75, // changed
                .baseHP_old    = 78,
                .types = { TYPE_FIRE, TYPE_DRAGON },
                .types_old = { TYPE_FIRE, TYPE_FLYING },
                .catchRate = 45,
                .catchRate_hard = 3,
                .genderRatio = PERCENT_FEMALE(12.5),
                .eggGroups = { EGG_GROUP_MONSTER, EGG_GROUP_DRAGON },
                .abilities = {ABILITY_BLAZE, ABILITY_NONE},
                .speciesName = _("Charizard"),
                .levelUpLearnset = sCharizardLevelUpLearnset,
            },
        };
        """,
        encoding="utf-8",
    )

    profiles = parse_species_profiles(source_repo)

    assert profiles["SPECIES_CHARIZARD"].fields == {
        "baseHP": "75",
        "types": "{ TYPE_FIRE, TYPE_DRAGON }",
        "catchRate": "45",
        "genderRatio": "PERCENT_FEMALE(12.5)",
        "eggGroups": "{ EGG_GROUP_MONSTER, EGG_GROUP_DRAGON }",
        "abilities": "{ ABILITY_BLAZE, ABILITY_NONE }",
    }


def test_parse_split_species_info_files_inside_preprocessor_blocks(tmp_path):
    source_repo = tmp_path / "pokeemerald-expansion"
    pokemon_dir = source_repo / "src" / "data" / "pokemon"
    split_dir = pokemon_dir / "species_info"
    split_dir.mkdir(parents=True)
    (pokemon_dir / "species_info.h").write_text(
        '#include "species_info/gen_1_families.h"\n',
        encoding="utf-8",
    )
    (split_dir / "gen_1_families.h").write_text(
        """
        #if P_GEN_1_POKEMON
            [SPECIES_CHARIZARD] =
            {
                .baseHP        = 78,
                #if P_UPDATED_EXP_YIELDS >= GEN_8
                    .expYield = 267,
                #elif P_UPDATED_EXP_YIELDS >= GEN_5
                    .expYield = 240,
                #else
                    .expYield = 209,
                #endif
                .types = MON_TYPES(TYPE_FIRE, TYPE_FLYING),
                .eggGroups = MON_EGG_GROUPS(EGG_GROUP_MONSTER, EGG_GROUP_DRAGON),
                .bodyColor = BODY_COLOR_RED,
                .description = COMPOUND_STRING("Ignored"),
            },
        #endif
        """,
        encoding="utf-8",
    )

    profiles = parse_species_profiles(source_repo)

    assert profiles["SPECIES_CHARIZARD"].fields == {
        "baseHP": "78",
        "expYield": "209",
        "types": "MON_TYPES(TYPE_FIRE, TYPE_FLYING)",
        "eggGroups": "MON_EGG_GROUPS(EGG_GROUP_MONSTER, EGG_GROUP_DRAGON)",
        "bodyColor": "BODY_COLOR_RED",
    }


def test_parse_function_macro_species_profile_entry(tmp_path):
    source_repo = tmp_path / "pokeemerald-expansion"
    pokemon_dir = source_repo / "src" / "data" / "pokemon"
    pokemon_dir.mkdir(parents=True)
    (pokemon_dir / "species_info.h").write_text(
        """
        #define UNOWN_MISC_INFO(type) { .baseHP = 48, .types = MON_TYPES(type), .catchRate = 225 }

        const struct SpeciesInfo gSpeciesInfo[] =
        {
            [SPECIES_UNOWN] = UNOWN_MISC_INFO(TYPE_PSYCHIC),
        };
        """,
        encoding="utf-8",
    )

    profiles = parse_species_profiles(source_repo)

    assert profiles["SPECIES_UNOWN"].fields == {
        "baseHP": "48",
        "types": "MON_TYPES(TYPE_PSYCHIC)",
        "catchRate": "225",
    }


def test_parse_multiline_function_macro_species_profile_entry(tmp_path):
    source_repo = tmp_path / "pokeemerald-expansion"
    pokemon_dir = source_repo / "src" / "data" / "pokemon"
    pokemon_dir.mkdir(parents=True)
    (pokemon_dir / "species_info.h").write_text(
        r"""
        #define ARCEUS_SPECIES_INFO(type, ability) { \
            .baseHP = 120, \
            .types = MON_TYPES(type), \
            .abilities = { ability, ABILITY_NONE }, \
        }

        const struct SpeciesInfo gSpeciesInfo[] =
        {
            [SPECIES_ARCEUS_NORMAL] = ARCEUS_SPECIES_INFO(TYPE_NORMAL, ABILITY_MULTITYPE),
        };
        """,
        encoding="utf-8",
    )

    profiles = parse_species_profiles(source_repo)

    assert profiles["SPECIES_ARCEUS_NORMAL"].fields == {
        "baseHP": "120",
        "types": "MON_TYPES(TYPE_NORMAL)",
        "abilities": "{ ABILITY_MULTITYPE, ABILITY_NONE }",
    }
