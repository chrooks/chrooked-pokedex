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
        # 16.2 names the move HIJUMPKICK; Essentials 21 (Nova) names it HIGHJUMPKICK.
        {"stage": "curated kick move with ability -> BOOSTED", "select": {"move": ["HIJUMPKICK", "HIGHJUMPKICK"], "ability": "true"}, "expect": {"result": "BOOSTED"}},
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
    # Priority abilities log at turn-order time (PokeBattle_Battle#pbPriority), one
    # OBS line per move the ability-holder selects. result=BOOSTED means the +1 was
    # applied; NORMAL means the gate failed. Eyeball the actual turn order too — the
    # OBS confirms the bump, the battle confirms it reordered the turn.
    "rapidcombustion": [
        {"stage": "At FULL HP, use a Fire move (e.g. Flamethrower) against a faster foe — your Fire move should move first.",
         "select": {"move": "FLAMETHROWER", "fullhp": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "Take damage so you are BELOW full HP, then use any Fire move (Flamethrower/Ember) — normal speed order.",
         "select": {"type": "FIRE", "fullhp": "false"}, "expect": {"result": "NORMAL"}},
        {"stage": "Back at FULL HP, use a NON-Fire move (e.g. Water Gun) — normal speed order.",
         "select": {"move": "WATERGUN", "type": "other"}, "expect": {"result": "NORMAL"}},
    ],
    "stampede": [
        {"stage": "KO a foe, then next turn use a CONTACT move (e.g. Tackle) — it should move first within its bracket.",
         "select": {"move": "TACKLE", "armed": "true", "contact": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "KO a foe, then use a NON-contact move (e.g. Water Gun) — no boost, the arming stays for later.",
         "select": {"move": "WATERGUN", "armed": "true", "contact": "false"}, "expect": {"result": "NORMAL"}},
        {"stage": "Without having KO'd anything (start of battle / fresh switch-in), use a contact move (Tackle) — no boost.",
         "select": {"move": "TACKLE", "armed": "false", "contact": "true"}, "expect": {"result": "NORMAL"}},
    ],
    "sacredtoll": [
        {"stage": "With your Sacred Toll user, use a sound move (e.g. Hyper Voice) on the foe — it becomes Psychic and hits ~20% harder.",
         "select": {"move": "HYPERVOICE", "ability": "true"}, "expect": {"result": "BOOSTED"}},
        {"stage": "With the SAME user, use a NON-sound move (e.g. Tackle) — no type change, no boost.",
         "select": {"move": "TACKLE", "ability": "true"}, "expect": {"result": "NORMAL"}},
        {"stage": "With the SAME user, use a sound move (Hyper Voice) into a DARK-type foe — Psychic typing means it does 0 (the OBS confirms the Psychic conversion that drives the 0x).",
         "select": {"move": "HYPERVOICE", "converted": "PSYCHIC"}, "expect": {"result": "BOOSTED"}},
    ],
    # chloroplast logs a hook-specific OBS per sun-gated move it touches.
    "chloroplast": [
        {"stage": "In CLEAR weather, use Solar Beam — it should fire the same turn (no charge), no real sun set.",
         "select": {"move": "SOLARBEAM"}, "expect": {"effect": "nocharge"}},
        {"stage": "In CLEAR weather, use Weather Ball — it should be Fire-type (and double power).",
         "select": {"move": "WEATHERBALL"}, "expect": {"type": "FIRE"}},
        {"stage": "In CLEAR weather, use Fire Blast — it should be sun-boosted (x1.5) per the sun-for-moves rule.",
         "select": {"move": "FIREBLAST", "weather": "clear"}, "expect": {"result": "SUN_BOOSTED"}},
        {"stage": "Make it RAIN (foe Rain Dance, or a Drizzle lead), then use a Fire move (Fire Blast/Ember) — still sun-boosted, overriding the rain.",
         "select": {"type": "FIRE", "weather": "rain"}, "expect": {"result": "SUN_BOOSTED"}},
        {"stage": "Below full HP, in clear weather, use Synthesis (or Morning Sun / Moonlight) — restores the sun 2/3, not 1/2.",
         "select": {"move": "SYNTHESIS"}, "expect": {"heal": "sun_2_3"}},
        {"stage": "Use Growth — Attack and Sp.Atk rise by 2 each (the sun amount), not 1.",
         "select": {"move": "GROWTH"}, "expect": {"increment": "2"}},
    ],
    "petalbarrier": [
        {"stage": "Switch a Petal Barrier user in, then hit it with any damaging move (Surf, Tackle, ...) — ~0.5x damage and 'petals scattered'.",
         "select": {"ability": "true", "armed": "true"}, "expect": {"result": "HALVED"}},
        {"stage": "Hit it again without switching — full damage, no message.",
         "select": {"ability": "true", "armed": "false"}, "expect": {"result": "NORMAL"}},
        {"stage": "Switch it out and back in, then hit it — halved again.",
         "select": {"event": "rearm", "ability": "true"}, "expect": {"armed": "true"}},
    ],
    "mountaineer": [
        {"stage": "Hit the Mountaineer user with a ROCK move (e.g. Rock Slide) — fully absorbed, 0 damage.",
         "select": {"type": "ROCK", "ability": "true"}, "expect": {"result": "ABSORBED"}},
        {"stage": "Set Stealth Rock on the Mountaineer user's side, then switch it in — no entry damage.",
         "select": {"event": "entry", "ability": "true"}, "expect": {"effect": "stealthrock_waived"}},
        {"stage": "Hit the Mountaineer user with a GROUND move (e.g. Earthquake) — normal damage (only Rock is blocked).",
         "select": {"type": "GROUND", "ability": "true"}, "expect": {"result": "PASS"}},
    ],
}

# Essentials 21 hand ports (mjolnir NV-10, NV-11): checks for an Essentials 21
# target, consulted there before SCENARIOS. A templated spec needs none (its checks
# are generated from its probes); a hand port with several effects does, and its
# keys can differ from another engine's port of the same mechanic (Infernal Maw's
# Rejuvenation scenario above predates its burn and flinch). The chance cases are
# many rolls, counted by the lab self-test and logged with source=selftest.
SCENARIOS_ESSENTIALS21: dict[str, list[dict[str, object]]] = {
    # A status (NV-12): freeze reskinned as frostbite, every case measured by the
    # lab self-test (case=turn|damage|chip).
    "frostbite": [
        {"stage": "A frostbitten Pokemon tries its move, many times.", "select": {"case": "turn", "source": "selftest"}, "expect": {"result": "ACTS"}},
        {"stage": "A frostbitten Pokemon uses Surf (special).", "select": {"case": "damage", "move": "SURF", "ability": "none", "source": "selftest"}, "expect": {"result": "HALVED"}},
        {"stage": "A frostbitten Pokemon uses Tackle (physical).", "select": {"case": "damage", "move": "TACKLE", "ability": "none", "source": "selftest"}, "expect": {"result": "NORMAL"}},
        {"stage": "A frostbitten Pokemon with Guts uses Surf.", "select": {"case": "damage", "move": "SURF", "ability": "GUTS", "source": "selftest"}, "expect": {"result": "NORMAL"}},
        {"stage": "A frostbitten Pokemon with Quick Feet uses Surf.", "select": {"case": "damage", "move": "SURF", "ability": "QUICKFEET", "source": "selftest"}, "expect": {"result": "NORMAL"}},
        {"stage": "A frostbitten Pokemon ends the round.", "select": {"case": "chip", "ability": "none", "source": "selftest"}, "expect": {"result": "CHIP"}},
        {"stage": "A frostbitten Pokemon with Magic Guard ends the round.", "select": {"case": "chip", "ability": "MAGICGUARD", "source": "selftest"}, "expect": {"result": "NONE"}},
        # Any Fire-type move cures it (Chris, 2026-10-22); Ember is a plain one,
        # with no thaw flag. The self-test also logs Flame Wheel, Scald and Tackle.
        {"stage": "A frostbitten Pokemon uses Ember.", "select": {"case": "cure", "move": "EMBER", "source": "selftest"}, "expect": {"cured": "true"}},
        {"stage": "Frostbite is inflicted on an Ice-type.", "select": {"case": "immune", "target_types": "ICE", "source": "selftest"}, "expect": {"result": "IMMUNE"}},
    ],
    "fullmoon": [
        {"stage": "Full Moon user (pure Normal type) uses Dark Pulse.", "select": {"move": "DARKPULSE", "ability": "true", "user_types": "NORMAL"}, "expect": {"result": "BOOSTED"}},
        {"stage": "Full Moon user (pure Normal type) uses Flamethrower.", "select": {"move": "FLAMETHROWER", "ability": "true", "user_types": "NORMAL"}, "expect": {"result": "NORMAL"}},
        {"stage": "Full Moon user at half HP uses Moonlight.", "select": {"move": "MOONLIGHT", "ability": "true"}, "expect": {"result": "BOOSTED"}},
    ],
    "highnoon": [
        {"stage": "High Noon user (pure Normal type) uses Flamethrower.", "select": {"move": "FLAMETHROWER", "ability": "true", "user_types": "NORMAL"}, "expect": {"result": "BOOSTED"}},
        {"stage": "High Noon user (pure Normal type) uses Dark Pulse.", "select": {"move": "DARKPULSE", "ability": "true", "user_types": "NORMAL"}, "expect": {"result": "NORMAL"}},
        {"stage": "High Noon user at half HP uses Morning Sun.", "select": {"move": "MORNINGSUN", "ability": "true"}, "expect": {"result": "BOOSTED"}},
    ],
    "infernalmaw": [
        {"stage": "Infernal Maw user bites (Crunch) a burnable foe, many times.", "select": {"move": "CRUNCH", "ability": "true", "source": "selftest", "target_types": "QMARKS"}, "expect": {"damage": "BOOSTED", "status_ok": "true", "flinch_ok": "true"}},
        {"stage": "Infernal Maw user uses Tackle, many times.", "select": {"move": "TACKLE", "ability": "true", "source": "selftest"}, "expect": {"damage": "NORMAL", "status_ok": "true", "flinch_ok": "true"}},
        {"stage": "Infernal Maw user bites (Crunch) a Fire-type foe, many times.", "select": {"move": "CRUNCH", "ability": "true", "source": "selftest", "target_types": "FIRE"}, "expect": {"damage": "BOOSTED", "status_ok": "true", "flinch_ok": "true"}},
    ],
    "rimefang": [
        {"stage": "Rimefang user bites (Crunch) a foe that can be frostbitten, many times.", "select": {"move": "CRUNCH", "ability": "true", "source": "selftest", "target_types": "QMARKS"}, "expect": {"damage": "BOOSTED", "status_ok": "true", "flinch_ok": "true"}},
        {"stage": "Rimefang user uses Tackle, many times.", "select": {"move": "TACKLE", "ability": "true", "source": "selftest"}, "expect": {"damage": "NORMAL", "status_ok": "true", "flinch_ok": "true"}},
        {"stage": "Rimefang user bites (Crunch) an Ice-type foe, many times.", "select": {"move": "CRUNCH", "ability": "true", "source": "selftest", "target_types": "ICE"}, "expect": {"damage": "BOOSTED", "status_ok": "true", "flinch_ok": "true"}},
    ],
    # NV-21 hand ports: entry and end-of-round effects, measured by the self-test's scenes.
    "dilation": [
        {"stage": 'Switch your Dilation Pokemon in with no Trick Room up.', "select": {'case': 'entry', 'label': 'calm', 'source': 'selftest'}, "expect": {'trick_room': '5'}},
        {"stage": 'Switch your Dilation Pokemon in under Trick Room.', "select": {'case': 'entry', 'label': 'twisted', 'source': 'selftest'}, "expect": {'trick_room': '0'}},
    ],
    "dualaegis": [
        {"stage": 'Switch your Dual Aegis Pokemon in with no screens up.', "select": {'case': 'entry', 'label': 'bare', 'source': 'selftest'}, "expect": {'reflect': '5', 'light_screen': '5'}},
        {"stage": 'Switch it in with Reflect already up.', "select": {'case': 'entry', 'label': 'reflect_up', 'source': 'selftest'}, "expect": {'reflect': '3', 'light_screen': '5'}},
        {"stage": 'Switch it in holding Light Clay.', "select": {'case': 'entry', 'label': 'light_clay', 'source': 'selftest'}, "expect": {'reflect': '8', 'light_screen': '8'}},
    ],
    "waterveil": [
        {"stage": 'Switch your Water Veil Pokemon in.', "select": {'case': 'entry', 'label': 'fresh', 'source': 'selftest'}, "expect": {'aqua_ring': 'true'}},
        {"stage": 'Baton Pass Aqua Ring to your Water Veil Pokemon.', "select": {'ability': 'true', 'entry': 'true', 'aqua_ring_before': 'true'}, "expect": {'set': 'false'}},
        {"stage": 'Switch it out and back in.', "select": {'case': 'entry', 'label': 'reentry', 'source': 'selftest'}, "expect": {'aqua_ring': 'true'}},
        {"stage": 'Use Will-O-Wisp on it.', "select": {'case': 'keeps', 'kind': 'status', 'status': 'BURN', 'source': 'selftest'}, "expect": {'changed': 'true'}},
        {"stage": 'Have it use Aqua Ring after entering.', "select": {'case': 'entry', 'label': 'fresh', 'source': 'selftest'}, "expect": {'aqua_ring_move_fails': 'true'}},
    ],
    "selfsufficient": [
        {"stage": 'End a turn with your Self Sufficient Pokemon damaged.', "select": {'case': 'eor', 'label': 'damaged', 'source': 'selftest'}, "expect": {'holder_change': '8'}},
        {"stage": 'End a turn with it at full HP.', "select": {'case': 'eor', 'label': 'full', 'source': 'selftest'}, "expect": {'holder_change': '0'}},
        {"stage": 'End a turn with a very low-level holder damaged.', "select": {'case': 'eor', 'label': 'tiny', 'source': 'selftest'}, "expect": {'holder_change': '1'}},
        {"stage": 'End a turn with it damaged and holding Leftovers.', "select": {'case': 'eor', 'label': 'leftovers', 'source': 'selftest'}, "expect": {'holder_change': '16'}},
    ],
    "heavyfumes": [
        {"stage": 'End a turn against a Normal-type foe.', "select": {'case': 'eor', 'label': 'normal', 'source': 'selftest'}, "expect": {'foe_change': '-14'}},
        {"stage": 'End a turn against a Poison-type foe.', "select": {'case': 'eor', 'label': 'poison', 'source': 'selftest'}, "expect": {'foe_change': '0'}},
        {"stage": 'End a turn against a Magic Guard foe.', "select": {'case': 'eor', 'label': 'guarded', 'source': 'selftest'}, "expect": {'foe_change': '0'}},
        {"stage": 'End a turn against a foe behind a Substitute.', "select": {'case': 'eor', 'label': 'substitute', 'source': 'selftest'}, "expect": {'foe_change': '-14'}},
    ],
    # NV-22 hand ports: on-hit effects, recoil, PP and status-move effects.
    "exhaust": [
        {"stage": 'Hit with Tackle, many times.', "select": {'case': 'hit_rolls', 'source': 'selftest', 'move': 'TACKLE', 'preset': 'none'}, "expect": {'ok': 'true'}},
        {"stage": 'Hit with Tackle, many times (the misses).', "select": {'case': 'hit_rolls', 'source': 'selftest', 'move': 'TACKLE', 'preset': 'none'}, "expect": {'ok': 'true'}},
        {"stage": 'Hit with Water Gun, many times.', "select": {'case': 'hit_rolls', 'source': 'selftest', 'move': 'WATERGUN'}, "expect": {'ok': 'true'}},
        {"stage": 'Hit a foe at -6 accuracy with Tackle.', "select": {'case': 'hit_rolls', 'source': 'selftest', 'move': 'TACKLE', 'preset': 'stages'}, "expect": {'ok': 'true'}},
    ],
    "deathgrip": [
        {"stage": 'Hit with Tackle, many times.', "select": {'case': 'hit_rolls', 'source': 'selftest', 'move': 'TACKLE', 'preset': 'none'}, "expect": {'ok': 'true'}},
        {"stage": 'Hit with Water Gun, many times.', "select": {'case': 'hit_rolls', 'source': 'selftest', 'move': 'WATERGUN'}, "expect": {'ok': 'true'}},
        {"stage": 'Hit a trapped foe with Tackle.', "select": {'case': 'hit_rolls', 'source': 'selftest', 'move': 'TACKLE', 'preset': 'trapped'}, "expect": {'ok': 'true'}},
    ],
    "riposte": [
        {"stage": 'Take a 100-HP contact hit.', "select": {'case': 'recoil', 'source': 'selftest', 'label': 'contact'}, "expect": {'foe_change': '-25'}},
        {"stage": 'Take a 100-HP non-contact hit.', "select": {'case': 'recoil', 'source': 'selftest', 'label': 'no_contact'}, "expect": {'foe_change': '0'}},
        {"stage": 'Take a contact hit on a substitute.', "select": {'case': 'recoil', 'source': 'selftest', 'label': 'substitute'}, "expect": {'foe_change': '0'}},
        {"stage": 'Take a contact hit from a Protective Pads holder.', "select": {'case': 'recoil', 'source': 'selftest', 'label': 'pads'}, "expect": {'foe_change': '0'}},
        {"stage": 'Take a 2-HP contact hit.', "select": {'case': 'recoil', 'source': 'selftest', 'label': 'graze'}, "expect": {'foe_change': '-1'}},
    ],
    "mindwipe": [
        {"stage": 'Hit a foe that last used Recover (10 PP).', "select": {'case': 'pp', 'source': 'selftest', 'label': 'recover'}, "expect": {'erased': '4'}},
        {"stage": 'Hit a foe that has not moved.', "select": {'case': 'pp', 'source': 'selftest', 'label': 'unmoved'}, "expect": {'erased': '0'}},
        {"stage": 'Hit a foe whose last move has 0 PP.', "select": {'case': 'pp', 'source': 'selftest', 'label': 'empty'}, "expect": {'erased': '0'}},
        {"stage": 'Land three hits on a foe whose last move has 16 PP.', "select": {'case': 'pp', 'source': 'selftest', 'label': 'three_hits'}, "expect": {'erased': '12'}},
    ],
    "insidious": [
        {"stage": 'Use Swords Dance.', "select": {'case': 'used', 'source': 'selftest', 'move': 'SWORDSDANCE', 'preset': 'none'}, "expect": {'raised': 'SPEED:0->1'}},
        {"stage": 'Use Tackle.', "select": {'case': 'used', 'source': 'selftest', 'move': 'TACKLE'}, "expect": {'raised': 'none'}},
        {"stage": 'Use Swords Dance at +6 Speed.', "select": {'case': 'used', 'source': 'selftest', 'move': 'SWORDSDANCE', 'preset': 'stages'}, "expect": {'raised': 'none'}},
    ],
    # NV-24 hand ports: a status's own chip and damage penalty.
    "flareboost": [
        {"stage": 'While burned, use Swift.', "select": {'case': 'status_hit', 'label': 'special', 'source': 'selftest'}, "expect": {'vs_none': 'HIGHER'}},
        {"stage": 'While burned, use Tackle.', "select": {'case': 'status_hit', 'label': 'physical', 'source': 'selftest'}, "expect": {'vs_none': 'SAME'}},
        {"stage": 'End a turn burned.', "select": {'case': 'eor_status', 'label': 'burned', 'source': 'selftest'}, "expect": {'with': '0'}},
    ],
    "toxicboost": [
        {"stage": 'While poisoned, use Tackle.', "select": {'case': 'status_hit', 'label': 'physical', 'source': 'selftest'}, "expect": {'vs_none': 'HIGHER'}},
        {"stage": 'While poisoned, use Swift.', "select": {'case': 'status_hit', 'label': 'special', 'source': 'selftest'}, "expect": {'vs_none': 'SAME'}},
        {"stage": 'End a turn badly poisoned.', "select": {'case': 'eor_status', 'label': 'toxic', 'source': 'selftest'}, "expect": {'with': '0'}},
    ],
    "quickfeet": [
        {"stage": 'While burned, use Tackle.', "select": {'case': 'status_hit', 'label': 'burned_physical', 'source': 'selftest'}, "expect": {'vs_healthy': 'SAME'}},
        {"stage": 'While frostbitten, use Swift.', "select": {'case': 'status_hit', 'label': 'frostbitten_special', 'source': 'selftest'}, "expect": {'vs_healthy': 'SAME'}},
        {"stage": 'While paralyzed, outspeed the foe.', "select": {'case': 'speed', 'label': 'paralyzed', 'source': 'selftest'}, "expect": {'result': 'RAISED'}},
    ],
    # NV-25 hand ports, each measured by its own check procs (case=check).
    "illusion": [
        {"stage": 'Lead with it, a Pikachu last in the party.', "select": {'case': 'check', 'label': 'entry', 'source': 'selftest'}, "expect": {'disguised': 'true', 'shown': 'PIKACHU'}},
        {"stage": 'Attack while disguised.', "select": {'case': 'check', 'label': 'disguised_hit', 'source': 'selftest'}, "expect": {'boosted': 'true'}},
        {"stage": 'Take a hit, then attack.', "select": {'case': 'check', 'label': 'broken', 'source': 'selftest'}, "expect": {'disguised': 'false', 'boosted': 'false'}},
    ],
    "nightstalker": [
        {"stage": 'At night, with Attack higher, use Cross Poison.', "select": {'case': 'check', 'label': 'night_physical', 'source': 'selftest'}, "expect": {'boosted': 'true', 'crit_stage': '1'}},
        {"stage": 'At night, with Attack higher, use Air Cutter.', "select": {'case': 'check', 'label': 'night_special', 'source': 'selftest'}, "expect": {'boosted': 'false', 'crit_stage': '1'}},
        {"stage": 'By day, with Sp. Atk higher, use Air Slash.', "select": {'case': 'check', 'label': 'day', 'source': 'selftest'}, "expect": {'boosted': 'false', 'crit_stage': '0'}},
        {"stage": 'At night, use Cross Poison on a Shell Armor foe.', "select": {'case': 'check', 'label': 'shell_armor', 'source': 'selftest'}, "expect": {'boosted': 'true', 'crits': '0'}},
    ],
    "sandguard": [
        {"stage": 'In a sandstorm, take a Surf.', "select": {'case': 'check', 'label': 'special_sand', 'source': 'selftest'}, "expect": {'halved': 'true'}},
        {"stage": 'In a sandstorm, take an Earthquake.', "select": {'case': 'check', 'label': 'physical_sand', 'source': 'selftest'}, "expect": {'halved': 'false'}},
        {"stage": 'In clear weather, take a Thunderbolt.', "select": {'case': 'check', 'label': 'special_clear', 'source': 'selftest'}, "expect": {'halved': 'false'}},
    ],
    "fixation": [
        {"stage": 'Use Flamethrower.', "select": {'case': 'check', 'label': 'boost', 'source': 'selftest'}, "expect": {'boosted': 'true'}},
        {"stage": 'Use Tackle.', "select": {'case': 'check', 'label': 'physical', 'source': 'selftest'}, "expect": {'boosted': 'false'}},
        {"stage": 'Use Flamethrower, then try to pick Psychic.', "select": {'case': 'check', 'label': 'locked', 'source': 'selftest'}, "expect": {'locked_to': 'FLAMETHROWER', 'flamethrower': 'true', 'psychic': 'false'}},
    ],
    "blitz": [
        {"stage": 'Send it out and act that turn.', "select": {'case': 'check', 'label': 'first_speed', 'source': 'selftest'}, "expect": {'faster': 'true'}},
        {"stage": 'On its first turn, use Tackle.', "select": {'case': 'check', 'label': 'first_physical', 'source': 'selftest'}, "expect": {'boosted': 'true'}},
        {"stage": 'On its second turn, use Tackle.', "select": {'case': 'check', 'label': 'second_turn', 'source': 'selftest'}, "expect": {'faster': 'false', 'boosted': 'false'}},
        {"stage": 'On its first turn, use Swift.', "select": {'case': 'check', 'label': 'first_special', 'source': 'selftest'}, "expect": {'boosted': 'false'}},
    ],
}
