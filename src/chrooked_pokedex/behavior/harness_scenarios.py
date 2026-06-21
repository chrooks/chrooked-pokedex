"""Per-mechanic harness scenarios — the only place that is mechanic-specific.

The harness *runner* (`harness.py`) is generic. Each mechanic contributes one
list of CHECKS here, aligned 1:1 and in order with that mechanic's
`test_cases` in `ruleset/behaviors/<id>.yaml`. A check says:

  * ``stage``  — the one human action that exercises this test_case in a debug
    battle (the play-one-battle step);
  * ``select`` — key/values that pick the relevant observation line the
    mechanic's plugin logged (``[chrooked:<id>] OBS k=v ...``);
  * ``expect`` — key/values that must hold on that observation for the case to
    pass.

Adding a mechanic = add an entry here + its plugin. The runner does not change.
Keys are arbitrary strings; they only have to agree with what the plugin logs,
so the runner stays mechanic-agnostic.
"""

from __future__ import annotations

# chrooked_id -> ordered checks, one per spec test_case.
SCENARIOS: dict[str, list[dict[str, object]]] = {
    "innerfocus": [
        {
            "stage": "With your Inner Focus user, use Focus Blast on the foe.",
            "select": {"move": "FOCUSBLAST", "if": "true"},
            "expect": {"result": "ALWAYS_HIT"},
        },
        {
            "stage": "With the SAME Inner Focus user, use Hydro Pump on the foe.",
            "select": {"move": "HYDROPUMP", "if": "true"},
            "expect": {"result": "NORMAL"},
        },
        {
            "stage": "Switch to a NON-Inner-Focus user and use Focus Blast on the foe.",
            "select": {"move": "FOCUSBLAST", "if": "false"},
            "expect": {"result": "NORMAL"},
        },
    ],
    "kindle": [
        {
            "stage": "With your Kindle user, use Flamethrower (Fire) on the foe.",
            "select": {"move": "FLAMETHROWER", "kindle": "true"},
            "expect": {"result": "BOOSTED"},
        },
        {
            # Spec names Surf; ANY non-Fire move witnesses "no boost" (Kindle only
            # touches Fire), so Tackle is an equally valid witness for this case.
            "stage": "With the SAME Kindle user, use a NON-Fire move (Surf, or Tackle) on the foe.",
            "select": {"move": "TACKLE", "kindle": "true"},
            "expect": {"result": "NORMAL"},
        },
        {
            "stage": "With the SAME Kindle user (at full HP), use Ember (Fire) on the foe.",
            "select": {"move": "EMBER", "kindle": "true"},
            "expect": {"result": "BOOSTED"},
        },
    ],
    "chitinize": [
        {"stage": "Chitinize user uses Tackle (Normal) at a foe weak to BUG.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "BUG", "boosted": "true"}},
        {"stage": "Chitinize user uses Tackle (Normal) at a foe that resists BUG.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "BUG", "boosted": "true"}},
        {"stage": "Chitinize user uses XSCISSOR (already non-Normal).", "select": {"move": "XSCISSOR", "ability": "true"}, "expect": {"converted": "none", "boosted": "false"}},
    ],
    "foliate": [
        {"stage": "Foliate user uses Tackle (Normal) at a foe weak to GRASS.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "GRASS", "boosted": "true"}},
        {"stage": "Foliate user uses Tackle (Normal) at a foe that resists GRASS.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "GRASS", "boosted": "true"}},
        {"stage": "Foliate user uses EMBER (already non-Normal).", "select": {"move": "EMBER", "ability": "true"}, "expect": {"converted": "none", "boosted": "false"}},
    ],
    "hydrate": [
        {"stage": "Hydrate user uses Tackle (Normal) at a foe weak to WATER.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "WATER", "boosted": "true"}},
        {"stage": "Hydrate user uses Tackle (Normal) at a foe that resists WATER.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "WATER", "boosted": "true"}},
        {"stage": "Hydrate user uses SURF (already non-Normal).", "select": {"move": "SURF", "ability": "true"}, "expect": {"converted": "none", "boosted": "false"}},
    ],
    "immolate": [
        {"stage": "Immolate user uses Tackle (Normal) at a foe weak to FIRE.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "FIRE", "boosted": "true"}},
        {"stage": "Immolate user uses Tackle (Normal) at a foe that resists FIRE.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "FIRE", "boosted": "true"}},
        {"stage": "Immolate user uses EMBER (already non-Normal).", "select": {"move": "EMBER", "ability": "true"}, "expect": {"converted": "none", "boosted": "false"}},
    ],
    "martialize": [
        {"stage": "Martialize user uses Tackle (Normal) at a foe weak to FIGHTING.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "FIGHTING", "boosted": "true"}},
        {"stage": "Martialize user uses Tackle (Normal) at a foe that resists FIGHTING.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "FIGHTING", "boosted": "true"}},
        {"stage": "Martialize user uses EMBER (already non-Normal).", "select": {"move": "EMBER", "ability": "true"}, "expect": {"converted": "none", "boosted": "false"}},
    ],
    "mineralize": [
        {"stage": "Mineralize user uses Tackle (Normal) at a foe weak to ROCK.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "ROCK", "boosted": "true"}},
        {"stage": "Mineralize user uses Tackle (Normal) at a foe that resists ROCK.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "ROCK", "boosted": "true"}},
        {"stage": "Mineralize user uses WATERGUN (already non-Normal).", "select": {"move": "WATERGUN", "ability": "true"}, "expect": {"converted": "none", "boosted": "false"}},
    ],
    "obfuscate": [
        {"stage": "Obfuscate user uses Tackle (Normal) at a foe weak to DARK.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "DARK", "boosted": "true"}},
        {"stage": "Obfuscate user uses Tackle (Normal) at a foe that resists DARK.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "DARK", "boosted": "true"}},
        {"stage": "Obfuscate user uses EMBER (already non-Normal).", "select": {"move": "EMBER", "ability": "true"}, "expect": {"converted": "none", "boosted": "false"}},
    ],
    "psyonize": [
        {"stage": "Psyonize user uses Tackle (Normal) at a foe weak to PSYCHIC.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "PSYCHIC", "boosted": "true"}},
        {"stage": "Psyonize user uses Tackle (Normal) at a foe that resists PSYCHIC.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "PSYCHIC", "boosted": "true"}},
        {"stage": "Psyonize user uses EMBER (already non-Normal).", "select": {"move": "EMBER", "ability": "true"}, "expect": {"converted": "none", "boosted": "false"}},
    ],
    "spectralize": [
        {"stage": "Spectralize user uses Tackle (Normal) at a foe weak to GHOST.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "GHOST", "boosted": "true"}},
        {"stage": "Spectralize user uses Tackle (Normal) at a foe that resists GHOST.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "GHOST", "boosted": "true"}},
        {"stage": "Spectralize user uses EMBER (already non-Normal).", "select": {"move": "EMBER", "ability": "true"}, "expect": {"converted": "none", "boosted": "false"}},
    ],
    "tectonize": [
        {"stage": "Tectonize user uses Tackle (Normal) at a foe weak to GROUND.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "GROUND", "boosted": "true"}},
        {"stage": "Tectonize user uses Tackle (Normal) at a foe that resists GROUND.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "GROUND", "boosted": "true"}},
        {"stage": "Tectonize user uses EARTHQUAKE (already non-Normal).", "select": {"move": "EARTHQUAKE", "ability": "true"}, "expect": {"converted": "none", "boosted": "false"}},
    ],
    "venomize": [
        {"stage": "Venomize user uses Tackle (Normal) at a foe weak to POISON.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "POISON", "boosted": "true"}},
        {"stage": "Venomize user uses Tackle (Normal) at a foe that resists POISON.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "POISON", "boosted": "true"}},
        {"stage": "Venomize user uses EMBER (already non-Normal).", "select": {"move": "EMBER", "ability": "true"}, "expect": {"converted": "none", "boosted": "false"}},
    ],
    "wyvernize": [
        {"stage": "Wyvernize user uses Tackle (Normal) at a foe weak to DRAGON.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "DRAGON", "boosted": "true"}},
        {"stage": "Wyvernize user uses Tackle (Normal) at a foe that resists DRAGON.", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"converted": "DRAGON", "boosted": "true"}},
        {"stage": "Wyvernize user uses EMBER (already non-Normal).", "select": {"move": "EMBER", "ability": "true"}, "expect": {"converted": "none", "boosted": "false"}},
    ],
    "bloom": [
        {"stage": "c1", "select": {"move": "ENERGYBALL", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "c2", "select": {"move": "FLAMETHROWER", "ability": "true"}, "expect": {"result": "NORMAL"}},
        {"stage": "c3", "select": {"move": "VINEWHIP", "ability": "true"}, "expect": {"result": "BOOSTED"}},
    ],
    "cryomancer": [
        {"stage": "c1", "select": {"move": "ICEBEAM", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "c2", "select": {"move": "THUNDERBOLT", "ability": "true"}, "expect": {"result": "NORMAL"}},
        {"stage": "c3", "select": {"move": "POWDERSNOW", "ability": "true"}, "expect": {"result": "BOOSTED"}},
    ],
    "deluge": [
        {"stage": "c1", "select": {"move": "SURF", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "c2", "select": {"move": "FLAMETHROWER", "ability": "true"}, "expect": {"result": "NORMAL"}},
        {"stage": "c3", "select": {"move": "WATERGUN", "ability": "true"}, "expect": {"result": "BOOSTED"}},
    ],
    "overcharge": [
        {"stage": "c1", "select": {"move": "THUNDERBOLT", "ability": "true", "hp_low": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "c2", "select": {"move": "THUNDERBOLT", "ability": "true", "hp_low": "false"}, "expect": {"result": "NORMAL"}},
        {"stage": "c3", "select": {"move": "ICEBEAM", "ability": "true", "hp_low": "true"}, "expect": {"result": "NORMAL"}},
    ],
    "amplifier": [
        {"stage": "matching sound move with Amplifier user is boosted", "select": {"move": "HYPERVOICE", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "non-sound move with Amplifier user is unchanged", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"result": "NORMAL"}},
        {"stage": "another non-sound physical move stays normal", "select": {"move": "EARTHQUAKE", "ability": "true"}, "expect": {"result": "NORMAL"}},
    ],
    "hammerfist": [
        {"stage": "punch move matches isPunchingMove? gate with the ability", "select": {"move": "MACHPUNCH", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "hammer/slam-named move matches the curated constant set with the ability", "select": {"move": "BODYSLAM", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "neither punch nor hammer/slam named, even with the ability", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"result": "NORMAL"}},
    ],
    "impale": [
        {"stage": "piercing move + Impale boosts damage", "select": {"move": "MEGAHORN", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "non-piercing move with Impale is unchanged", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"result": "NORMAL"}},
        {"stage": "piercing move without Impale is unchanged", "select": {"move": "DRILLPECK", "ability": "false"}, "expect": {"result": "NORMAL"}},
    ],
    "martialartist": [
        {"stage": "punch move with ability -> BOOSTED", "select": {"move": "MACHPUNCH", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "curated kick move with ability -> BOOSTED", "select": {"move": "HIJUMPKICK", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "neither punch nor kick with ability -> NORMAL", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"result": "NORMAL"}},
    ],
    "sledgehammer": [
        {"stage": "hammer/slam move + ability -> boosted", "select": {"move": "WOODHAMMER", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "another hammer/slam move + ability -> boosted", "select": {"move": "BODYSLAM", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "punching move + ability -> unchanged (punch half excluded)", "select": {"move": "MACHPUNCH", "ability": "true"}, "expect": {"result": "NORMAL"}},
    ],
    "striker": [
        {"stage": "kicking move + Striker user", "select": {"move": "HIGHJUMPKICK", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "non-kicking move + Striker user", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"result": "NORMAL"}},
        {"stage": "kicking move + non-Striker user", "select": {"move": "BLAZEKICK", "ability": "false"}, "expect": {"result": "NORMAL"}},
    ],
    "wingspan": [
        {"stage": "matching wing move boosted", "select": {"move": "HURRICANE", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "matching wing move boosted", "select": {"move": "BRAVEBIRD", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "non-matching move normal", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"result": "NORMAL"}},
    ],
    "infernalmaw": [
        {"stage": "biting move + ability", "select": {"move": "CRUNCH", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "non-biting move + ability", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"result": "NORMAL"}},
        {"stage": "biting move, no ability", "select": {"move": "CRUNCH", "ability": "false"}, "expect": {"result": "NORMAL"}},
    ],
    "magicalfists": [
        {"stage": "matching punching move with ability -> BOOSTED", "select": {"move": "MACHPUNCH", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "non-punching move with ability -> NORMAL", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"result": "NORMAL"}},
        {"stage": "punching move without ability -> NORMAL", "select": {"move": "MACHPUNCH", "ability": "false"}, "expect": {"result": "NORMAL"}},
    ],
    "mysticblades": [
        {"stage": "matching-slicing-move", "select": {"move": "NIGHTSLASH", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "matching-special-slicing-move", "select": {"move": "AIRSLASH", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "non-matching-move", "select": {"move": "TACKLE", "ability": "true"}, "expect": {"result": "NORMAL"}},
    ],
}
