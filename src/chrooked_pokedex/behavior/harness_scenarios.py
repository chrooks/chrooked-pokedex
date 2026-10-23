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
    # NV-26 hand ports: hazards, weather and indirect damage.
    "impenetrable": [
        {"stage": 'End a turn burned, in a sandstorm.', "select": {'case': 'check', 'label': 'burn_sand', 'source': 'selftest'}, "expect": {'burn_with': '0', 'sand_with': '0', 'spared': 'true'}},
        {"stage": 'Switch in onto Stealth Rock.', "select": {'case': 'check', 'label': 'stealth_rock', 'source': 'selftest'}, "expect": {'rock_with': '0', 'spared': 'true'}},
        {"stage": 'Use Head Smash.', "select": {'case': 'check', 'label': 'head_smash', 'source': 'selftest'}, "expect": {'recoil_with': '0', 'spared': 'true'}},
    ],
    "mountaineer": [
        {"stage": 'Take a Rock Slide.', "select": {'move': 'ROCKSLIDE', 'ability': 'true'}, "expect": {'result': 'IMMUNE'}},
        {"stage": 'Switch in onto Stealth Rock.', "select": {'case': 'check', 'label': 'stealth_rock', 'source': 'selftest'}, "expect": {'rock_with': '0', 'spared': 'true'}},
        {"stage": 'Take an Earthquake.', "select": {'move': 'EARTHQUAKE', 'ability': 'true'}, "expect": {'result': 'NORMAL'}},
    ],
    "bioturbation": [
        {"stage": 'Switch an Ice/Water holder in onto Stealth Rock.', "select": {'case': 'check', 'label': 'ice_water_rock', 'source': 'selftest'}, "expect": {'neutral': 'true', 'own_rock': 'false', 'foe_rock': 'true'}},
        {"stage": 'Switch in onto three Spikes and Stealth Rock.', "select": {'case': 'check', 'label': 'spikes_rock', 'source': 'selftest'}, "expect": {'own_spikes': '0', 'foe_spikes': '3', 'foe_rock': 'true'}},
        {"stage": 'Switch in onto two Spikes and Stealth Rock, three Spikes on the foes.', "select": {'case': 'check', 'label': 'capped', 'source': 'selftest'}, "expect": {'own_spikes': '0', 'foe_spikes': '3', 'own_rock': 'false', 'foe_rock': 'true'}},
    ],
    "repulsion": [
        {"stage": 'Switch in; the foe uses Earthquake.', "select": {'case': 'check', 'label': 'earthquake', 'source': 'selftest'}, "expect": {'magnet_rise': '5', 'airborne': 'true', 'ground_immune': 'true'}},
        {"stage": 'Switch in; the foe uses Smack Down.', "select": {'case': 'check', 'label': 'smack_down', 'source': 'selftest'}, "expect": {'magnet_rise': '0', 'airborne': 'false'}},
        {"stage": 'Switch in with Magnet Rise already up (3 turns left).', "select": {'case': 'check', 'label': 'already_rising', 'source': 'selftest'}, "expect": {'magnet_rise': '3'}},
    ],
    "thornedsucculent": [
        {"stage": 'At half HP, take a Surf.', "select": {'case': 'check', 'label': 'surf', 'source': 'selftest'}, "expect": {'immune': 'true', 'foe_change': '0'}},
        {"stage": 'Take a Poison Jab.', "select": {'case': 'check', 'label': 'poison_jab', 'source': 'selftest'}, "expect": {'contact': 'true', 'eighth': 'true'}},
        {"stage": 'End a turn in a sandstorm.', "select": {'case': 'check', 'label': 'sandstorm', 'source': 'selftest'}, "expect": {'sand_with': '0', 'spared': 'true'}},
    ],
    # NV-27 hand ports: armed and streak states, each in the battler's chrooked_state.
    "coilup": [
        {"stage": 'Switch in, then use Crunch twice.', "select": {'case': 'check', 'label': 'entry_crunch', 'source': 'selftest'}, "expect": {'priorities': 'CRUNCH:1,CRUNCH:0'}},
        {"stage": 'Switch in, use Glare, then Crunch twice.', "select": {'case': 'check', 'label': 'glare_first', 'source': 'selftest'}, "expect": {'priorities': 'GLARE:0,CRUNCH:1,CRUNCH:0'}},
        {"stage": 'Spend the coil, switch out and back in, use Crunch.', "select": {'case': 'check', 'label': 'reentry', 'source': 'selftest'}, "expect": {'priorities': 'CRUNCH:1,CRUNCH:0,reentered,CRUNCH:1'}},
    ],
    "stampede": [
        {"stage": 'Knock a foe out, then use Tackle twice.', "select": {'case': 'check', 'label': 'ko_then_contact', 'source': 'selftest'}, "expect": {'priorities': 'KO:0,TACKLE:1,TACKLE:0'}},
        {"stage": 'Knock a foe out, use Water Gun, then Tackle.', "select": {'case': 'check', 'label': 'ko_then_water_gun', 'source': 'selftest'}, "expect": {'priorities': 'KO:0,WATERGUN:0,TACKLE:1'}},
        {"stage": 'Use Tackle twice without a knockout.', "select": {'case': 'check', 'label': 'no_ko', 'source': 'selftest'}, "expect": {'priorities': 'TACKLE:0,TACKLE:0'}},
    ],
    "sporulation": [
        {"stage": 'Switch in and use Spore.', "select": {'case': 'check', 'label': 'first_spore', 'source': 'selftest'}, "expect": {'priorities': 'SPORE:1'}},
        {"stage": 'Use Spore again.', "select": {'case': 'check', 'label': 'second_spore', 'source': 'selftest'}, "expect": {'priorities': 'SPORE:1,SPORE:0'}},
        {"stage": 'Use Sleep Powder, then Spore.', "select": {'case': 'check', 'label': 'sleep_powder', 'source': 'selftest'}, "expect": {'priorities': 'SLEEPPOWDER:0,SPORE:1'}},
        {"stage": 'Spend it, switch out and back in, use Spore.', "select": {'case': 'check', 'label': 'reentry', 'source': 'selftest'}, "expect": {'priorities': 'SPORE:1,reentered,SPORE:1'}},
    ],
    "starfall": [
        {"stage": 'On its first turn in, use Psybeam.', "select": {'case': 'check', 'label': 'first', 'source': 'selftest'}, "expect": {'streak': '0', 'boosted': 'false'}},
        {"stage": 'After one attacking turn, use Psybeam.', "select": {'case': 'check', 'label': 'second', 'source': 'selftest'}, "expect": {'streak': '1', 'boosted': 'true'}},
        {"stage": 'After four attacking turns, use Psybeam.', "select": {'case': 'check', 'label': 'fifth', 'source': 'selftest'}, "expect": {'streak': '3', 'boosted': 'true'}},
        {"stage": 'Attack twice, use Recover, then Psybeam.', "select": {'case': 'check', 'label': 'after_recover', 'source': 'selftest'}, "expect": {'streak': '0', 'boosted': 'false'}},
        {"stage": 'Attack three times, switch out and back, then Psybeam.', "select": {'case': 'check', 'label': 'after_switch', 'source': 'selftest'}, "expect": {'streak': '0', 'boosted': 'false'}},
        {"stage": 'After three attacking turns, use Tackle.', "select": {'case': 'check', 'label': 'physical', 'source': 'selftest'}, "expect": {'streak': '3', 'boosted': 'false'}},
    ],
    "savant": [
        {"stage": 'Use Psychic twice.', "select": {'case': 'check', 'label': 'twice', 'source': 'selftest'}, "expect": {'uses': 'PSYCHIC:BOOSTED,PSYCHIC:NORMAL'}},
        {"stage": 'Use Psychic, then Shadow Ball.', "select": {'case': 'check', 'label': 'two_moves', 'source': 'selftest'}, "expect": {'uses': 'PSYCHIC:BOOSTED,SHADOWBALL:BOOSTED'}},
        {"stage": 'Use Psychic, switch out and back, use Psychic.', "select": {'case': 'check', 'label': 'reentry', 'source': 'selftest'}, "expect": {'uses': 'PSYCHIC:BOOSTED,reentered,PSYCHIC:BOOSTED'}},
    ],
    "spitefulblock": [
        {"stage": 'Survive a hit, then use Bite twice.', "select": {'case': 'check', 'label': 'hit_then_bite', 'source': 'selftest'}, "expect": {'steps': 'hit,BITE:BOOSTED,BITE:NORMAL'}},
        {"stage": 'Use Bite without being hit first.', "select": {'case': 'check', 'label': 'no_hit', 'source': 'selftest'}, "expect": {'steps': 'BITE:NORMAL'}},
        {"stage": 'Survive a hit, use Tackle, then Bite.', "select": {'case': 'check', 'label': 'hit_then_tackle', 'source': 'selftest'}, "expect": {'steps': 'hit,TACKLE:NORMAL,BITE:BOOSTED'}},
    ],
    "battery": [
        {"stage": 'Switch in uncharged, then use Thunderbolt.', "select": {'case': 'check', 'label': 'entry_thunderbolt', 'source': 'selftest'}, "expect": {'charge': '2', 'spdef': '1', 'doubled': 'true'}},
        {"stage": 'Switch in already charged.', "select": {'case': 'check', 'label': 'already_charged', 'source': 'selftest'}, "expect": {'charge': '1', 'spdef': '0'}},
        {"stage": 'Not in this game.', "absent": "Nova has no field effects, and its Charge raises Sp. Def by 1 on any terrain", "select": {}, "expect": {}},
        {"stage": 'Switch in, then use Bug Buzz.', "select": {'case': 'check', 'label': 'bug_move', 'source': 'selftest'}, "expect": {'doubled': 'false'}},
    ],
    "finishingkick": [
        {"stage": 'At Speed 0, use Quick Attack.', "select": {'case': 'check', 'label': 'quick_attack_0', 'source': 'selftest'}, "expect": {'boosted': 'false'}},
        {"stage": 'At Speed +1, use Wild Charge.', "select": {'case': 'check', 'label': 'wild_charge_1', 'source': 'selftest'}, "expect": {'boosted': 'true'}},
        {"stage": 'At Speed +2, use Thunderbolt.', "select": {'case': 'check', 'label': 'thunderbolt_2', 'source': 'selftest'}, "expect": {'boosted': 'false'}},
        {"stage": 'At Speed +6, use Crunch.', "select": {'case': 'check', 'label': 'crunch_6', 'source': 'selftest'}, "expect": {'boosted': 'true'}},
    ],
    # NV-28 hand ports: entry effects, trapping, an added type.
    "frighten": [
        {"stage": 'Switch in against one foe.', "select": {'case': 'check', 'label': 'single', 'source': 'selftest'}, "expect": {'foe_spatk': '-1'}},
        {"stage": 'Switch in with no foe on the field.', "select": {'case': 'check', 'label': 'empty', 'source': 'selftest'}, "expect": {'foe_spatk': '0', 'foes': '0'}},
        {"stage": 'In a double battle, switch in against two foes.', "select": {'case': 'check', 'label': 'doubles', 'source': 'selftest'}, "expect": {'foe_spatk': '-1', 'second_foe_spatk': '-1'}},
    ],
    "deadlock": [
        {"stage": 'Switch in against a foe.', "select": {'case': 'check', 'label': 'entry', 'source': 'selftest'}, "expect": {'foe_speed': '-1'}},
        {"stage": 'Have the foe try to switch.', "select": {'case': 'check', 'label': 'trapped', 'source': 'selftest'}, "expect": {'can_switch': 'false'}},
        {"stage": 'Faint or leave, then have the foe switch.', "select": {'case': 'check', 'label': 'holder_gone', 'source': 'selftest'}, "expect": {'can_switch': 'true'}},
        {"stage": 'Have a Ghost-type foe switch.', "select": {'case': 'check', 'label': 'ghost', 'source': 'selftest'}, "expect": {'can_switch': 'true'}},
        {"stage": 'Have a Shed Shell foe switch.', "select": {'case': 'check', 'label': 'shed_shell', 'source': 'selftest'}, "expect": {'can_switch': 'true'}},
        {"stage": 'Switch in against a Clear Body foe.', "select": {'case': 'check', 'label': 'clear_body', 'source': 'selftest'}, "expect": {'foe_speed': '0', 'can_switch': 'false'}},
        {"stage": 'Switch in twice.', "select": {'case': 'check', 'label': 'twice', 'source': 'selftest'}, "expect": {'foe_speed': '-2'}},
    ],
    "pheromone": [
        {"stage": 'Have a foe try to switch.', "select": {'case': 'check', 'label': 'trapped', 'source': 'selftest'}, "expect": {'can_switch': 'false'}},
        {"stage": 'Have a Ghost-type, then a Shed Shell foe switch.', "select": {'case': 'check', 'label': 'ghost_or_shed', 'source': 'selftest'}, "expect": {'ghost_can_switch': 'true', 'shed_can_switch': 'true'}},
        {"stage": 'Have the foe use U-turn.', "select": {'case': 'check', 'label': 'trapped', 'source': 'selftest'}, "expect": {'u_turn_can_switch': 'true'}},
    ],
    "pressure": [
        {"stage": 'Switch in against a foe at +2 Attack and -1 Speed.', "select": {'case': 'check', 'label': 'mixed', 'source': 'selftest'}, "expect": {'foe_attack': '0', 'foe_speed': '-1'}},
        {"stage": 'In a double battle, switch in against two boosted foes.', "select": {'case': 'check', 'label': 'doubles', 'source': 'selftest'}, "expect": {'boosts_left': '0'}},
        {"stage": 'Switch in against a foe with no boosts.', "select": {'case': 'check', 'label': 'no_boosts', 'source': 'selftest'}, "expect": {'changed': 'false'}},
        {"stage": 'Have the foe use Tackle on it.', "select": {'case': 'check', 'label': 'pp', 'source': 'selftest'}, "expect": {'pp_used': '2'}},
    ],
    "frisk": [
        {"stage": 'Switch in against a foe holding Leftovers.', "select": {'case': 'check', 'label': 'leftovers', 'source': 'selftest'}, "expect": {'embargo_on_entry': '2', 'item_works': 'false'}},
        {"stage": 'Switch in against a foe under a 5-round Embargo.', "select": {'case': 'check', 'label': 'longer_embargo', 'source': 'selftest'}, "expect": {'embargo_on_entry': '5'}},
        {"stage": 'Let two rounds end after entry.', "select": {'case': 'check', 'label': 'three_rounds', 'source': 'selftest'}, "expect": {'item_works': 'true'}},
    ],
    "phantom": [
        {"stage": 'Lead with an Electric/Fire holder.', "select": {'case': 'check', 'label': 'electric_fire', 'source': 'selftest'}, "expect": {'types': 'ELECTRIC/FIRE/GHOST', 'tackle_fails': 'true', 'karate_chop_fails': 'true'}},
        {"stage": 'Use Shadow Ball.', "select": {'case': 'check', 'label': 'shadow_ball_stab', 'source': 'selftest'}, "expect": {'stab': 'true'}},
        {"stage": 'Switch out and back in.', "select": {'case': 'check', 'label': 'reentry', 'source': 'selftest'}, "expect": {'ghost_while_out': 'false', 'ghost_again': 'true'}},
        {"stage": 'Switch in an Electric/Ghost holder.', "select": {'case': 'check', 'label': 'already_ghost', 'source': 'selftest'}, "expect": {'extra_type': 'none'}},
        {"stage": "Have the foe use Forest's Curse on it.", "select": {'case': 'check', 'label': 'forests_curse', 'source': 'selftest'}, "expect": {'types': 'ELECTRIC/FIRE/GRASS'}},
        {"stage": 'Have the foe use Trick-or-Treat on it.', "select": {'case': 'check', 'label': 'trick_or_treat', 'source': 'selftest'}, "expect": {'fails': 'true'}},
        {"stage": 'Let the AI weigh switching it in after a Tackle.', "select": {'case': 'check', 'label': 'ai_switch', 'source': 'selftest'}, "expect": {'ghost_weighed': 'true'}},
    ],
    "ordertaker": [
        {"stage": 'Lead with a healthy Tatsugiri in the back.', "select": {'case': 'check', 'label': 'tatsugiri', 'source': 'selftest'}, "expect": {'stages': '1/1/1/1/1'}},
        {"stage": 'Switch in with the only Tatsugiri fainted.', "select": {'case': 'check', 'label': 'fainted', 'source': 'selftest'}, "expect": {'stages': '0/0/0/0/0'}},
        {"stage": 'Switch in with no Tatsugiri.', "select": {'case': 'check', 'label': 'none', 'source': 'selftest'}, "expect": {'stages': '0/0/0/0/0'}},
        {"stage": "In a multi battle, only the ally trainer has a Tatsugiri.", "select": {'case': 'check', 'label': 'multi', 'source': 'selftest'}, "expect": {'stages': '0/0/0/0/0', 'own_team': '1'}},
        {"stage": 'Re-enter at +6 in all five.', "select": {'case': 'check', 'label': 'maxed', 'source': 'selftest'}, "expect": {'stages': '6/6/6/6/6'}},
        {"stage": 'Not in this game.', "absent": "Nova's AI rates a switch-in without its entry ability; it does not model Intrepid Sword either", "select": {}, "expect": {}},
    ],
    "webweaver": [
        {"stage": 'Switch in with no Sticky Web on the foes.', "select": {'case': 'check', 'label': 'lays_web', 'source': 'selftest'}, "expect": {'web': 'true', 'web_messages': '1'}},
        {"stage": 'Switch in with Sticky Web already on the foes.', "select": {'case': 'check', 'label': 'already_webbed', 'source': 'selftest'}, "expect": {'web': 'true', 'web_messages': '0'}},
        {"stage": 'Have a grounded foe try to switch.', "select": {'case': 'check', 'label': 'grounded_trapped', 'source': 'selftest'}, "expect": {'can_switch': 'false'}},
        {"stage": 'Have a Flying-type foe switch.', "select": {'case': 'check', 'label': 'flying_free', 'source': 'selftest'}, "expect": {'can_switch': 'true'}},
        {"stage": 'Have a Shed Shell foe switch.', "select": {'case': 'check', 'label': 'shed_shell', 'source': 'selftest'}, "expect": {'can_switch': 'true'}},
    ],
    "unattainable": [
        {"stage": 'Take many Tackles from a male foe.', "select": {'case': 'check', 'label': 'same_gender', 'source': 'selftest'}, "expect": {'ok': 'true'}},
        {"stage": 'Take many Tackles from a Magnezone.', "select": {'case': 'check', 'label': 'genderless', 'source': 'selftest'}, "expect": {'ok': 'true'}},
        {"stage": 'Take Tackles from an Oblivious, then an Aroma Veil foe.', "select": {'case': 'check', 'label': 'oblivious_aroma_veil', 'source': 'selftest'}, "expect": {'never': 'true'}},
        {"stage": 'Take Water Guns, then Tackles from a Protective Pads foe.', "select": {'case': 'check', 'label': 'non_contact_pads', 'source': 'selftest'}, "expect": {'never': 'true'}},
        {"stage": 'Take Tackles from a foe already in love.', "select": {'case': 'check', 'label': 'already', 'source': 'selftest'}, "expect": {'changed': '0'}},
        {"stage": 'Take a Tackle from a foe at +6 Attack.', "select": {'case': 'check', 'label': 'unaware', 'source': 'selftest'}, "expect": {'ignored': 'true'}},
    ],
    # NV-29 hand ports: absorbing and drawing moves, sound and pulse spread.
    "aerodynamic": [
        {"stage": 'Take an Air Slash.', "select": {'case': 'check', 'label': 'air_slash', 'source': 'selftest'}, "expect": {'immune': 'true', 'speed': '1'}},
        {"stage": 'Take a Tackle.', "select": {'case': 'check', 'label': 'tackle', 'source': 'selftest'}, "expect": {'immune': 'false', 'speed': '0'}},
        {"stage": "In a double battle, a foe aims Air Slash at the holder's ally.", "select": {'case': 'check', 'label': 'redirect', 'source': 'selftest'}, "expect": {'drawn_to': '0'}},
    ],
    "airborne": [
        {"stage": 'Take an Air Slash.', "select": {'case': 'check', 'label': 'air_slash', 'source': 'selftest'}, "expect": {'immune': 'true', 'speed': '1'}},
        {"stage": 'Take an Earthquake.', "select": {'case': 'check', 'label': 'earthquake', 'source': 'selftest'}, "expect": {'misses_airborne': 'true', 'speed': '0'}},
        {"stage": 'Take an Earthquake under Gravity, after Smack Down, from a Mold Breaker.', "select": {'case': 'check', 'label': 'earthquake_cancelled', 'source': 'selftest'}, "expect": {'gravity_hits': 'true', 'smack_down_hits': 'true', 'mold_breaker_hits': 'true'}},
        {"stage": 'Take a Tackle.', "select": {'case': 'check', 'label': 'tackle', 'source': 'selftest'}, "expect": {'hits': 'true', 'speed': '0'}},
        {"stage": "In a double battle, a foe aims Air Slash, then Drill Run, at the holder's ally.", "select": {'case': 'check', 'label': 'redirect', 'source': 'selftest'}, "expect": {'flying_to': '0', 'ground_to': '2'}},
    ],
    "pastelveil": [
        {"stage": 'Take a Sludge Bomb.', "select": {'move': 'SLUDGEBOMB', 'type': 'POISON', 'ability': 'true'}, "expect": {'result': 'IMMUNE'}},
        {"stage": "In a double battle, a foe uses Sludge Bomb on the holder's ally.", "select": {'case': 'check', 'label': 'ally', 'source': 'selftest'}, "expect": {'ally_immune': 'false', 'ally_can_be_poisoned': 'false'}},
        {"stage": 'Take a Toxic.', "select": {'move': 'TOXIC', 'ability': 'true'}, "expect": {'result': 'IMMUNE'}},
    ],
    "amplifier": [
        {"stage": 'Use Hyper Voice.', "select": {'move': 'HYPERVOICE', 'ability': 'true'}, "expect": {'sound': 'true'}},
        {"stage": 'Use Tackle.', "select": {'move': 'TACKLE', 'ability': 'true'}, "expect": {'sound': 'false'}},
        {"stage": 'With a Pokemon without Amplifier, use Hyper Voice.', "select": {'move': 'HYPERVOICE', 'ability': 'false', 'source': 'selftest'}, "expect": {'result': 'NORMAL'}},
        {"stage": 'In a double battle, use Bug Buzz.', "select": {'case': 'check', 'label': 'doubles', 'source': 'selftest'}, "expect": {'holder_target': 'AllNearFoes', 'ally_target': 'NearOther'}},
    ],
    "barrage": [
        {"stage": 'In a double battle, use Water Pulse on a foe at +6 evasion.', "select": {'case': 'check', 'label': 'water_pulse', 'source': 'selftest'}, "expect": {'target': 'AllNearFoes', 'never_misses': 'true'}},
        # The Ruleset marks Hydro Pump a pulse move, so Fire Blast stands in for "not a pulse move".
        {"stage": 'Use Fire Blast on a foe at +6 evasion.', "select": {'case': 'check', 'label': 'not_pulse', 'source': 'selftest'}, "expect": {'target': 'NearOther', 'never_misses': 'false'}},
    ],
    # NV-30 hand ports: one-offs, and the move Gastric Snare that Corrosion's case needs.
    "angerpoint": [
        {"stage": 'Camerupt takes a critical hit.', "select": {'case': 'check', 'label': 'camerupt', 'source': 'selftest'}, "expect": {'attack': '0', 'spatk': '6'}},
        {"stage": 'Primeape takes a critical hit.', "select": {'case': 'check', 'label': 'primeape', 'source': 'selftest'}, "expect": {'attack': '6', 'spatk': '0'}},
        {"stage": 'Mew (equal Attack and Sp. Atk) takes a critical hit.', "select": {'case': 'check', 'label': 'tie', 'source': 'selftest'}, "expect": {'attack': '6', 'spatk': '0'}},
        {"stage": 'Camerupt at +6 Sp. Atk takes a critical hit.', "select": {'case': 'check', 'label': 'spatk_maxed', 'source': 'selftest'}, "expect": {'attack': '0', 'spatk': '6'}},
        {"stage": 'Camerupt takes a hit that is not critical.', "select": {'case': 'check', 'label': 'not_critical', 'source': 'selftest'}, "expect": {'attack': '0', 'spatk': '0'}},
    ],
    "bonebreaker": [
        {"stage": 'Use Bone Rush on a Flying-type.', "select": {'case': 'check', 'label': 'flying', 'source': 'selftest'}, "expect": {'connects': 'true'}},
        {"stage": 'Use Bone Rush on a Levitate, then an Earth Eater foe.', "select": {'case': 'check', 'label': 'levitate_absorb', 'source': 'selftest'}, "expect": {'levitate_connects': 'true', 'earth_eater_connects': 'true'}},
        {"stage": 'Use Tackle on a Ghost-type.', "select": {'case': 'check', 'label': 'tackle_ghost', 'source': 'selftest'}, "expect": {'connects': 'false'}},
    ],
    "corrosion": [
        {"stage": 'Use Poison Jab on Steelix.', "select": {'case': 'check', 'label': 'steelix', 'source': 'selftest'}, "expect": {'factor': '1.00'}},
        {"stage": 'Use Gunk Shot on Registeel.', "select": {'case': 'check', 'label': 'registeel', 'source': 'selftest'}, "expect": {'factor': '2.00'}},
        {"stage": 'Use Gastric Snare on Scizor.', "select": {'case': 'check', 'label': 'scizor', 'source': 'selftest'}, "expect": {'factor': '4.00'}},
        {"stage": 'With a Pokemon without Corrosion, use Poison Jab on Registeel.', "select": {'case': 'check', 'label': 'without', 'source': 'selftest'}, "expect": {'factor': '0.00'}},
        {"stage": 'Use Toxic on Registeel.', "select": {'case': 'check', 'label': 'toxic', 'source': 'selftest'}, "expect": {'status': 'POISON', 'toxic': 'true'}},
        {"stage": 'Use Razor Leaf on Registeel.', "select": {'case': 'check', 'label': 'razor_leaf', 'source': 'selftest'}, "expect": {'factor': '0.50'}},
    ],
    "gastricsnare": [
        {"stage": 'Use Gastric Snare on Caterpie.', "select": {'case': 'check', 'label': 'caterpie', 'source': 'selftest'}, "expect": {'factor': '2.00'}},
        {"stage": 'Use Gastric Snare on Scyther.', "select": {'case': 'check', 'label': 'scyther', 'source': 'selftest'}, "expect": {'factor': '2.00'}},
        {"stage": 'Use Gastric Snare on Kangaskhan.', "select": {'case': 'check', 'label': 'kangaskhan', 'source': 'selftest'}, "expect": {'factor': '1.00'}},
        {"stage": 'Use Gastric Snare on a Caterpie already paralyzed, many times.', "select": {'case': 'check', 'label': 'statused_bug', 'source': 'selftest'}, "expect": {'factor': '2.00', 'ok': 'true'}},
        {"stage": 'With Corrosion, use Gastric Snare on Scizor.', "select": {'case': 'check', 'label': 'scizor_corrosion', 'source': 'selftest'}, "expect": {'factor': '4.00'}},
    ],
    "deeprooted": [
        {"stage": 'Drain 50 HP with Giga Drain.', "select": {'case': 'check', 'label': 'giga_drain', 'source': 'selftest'}, "expect": {'recovered': '65'}},
        {"stage": 'Receive 10 HP from Leech Seed.', "select": {'case': 'check', 'label': 'leech_seed', 'source': 'selftest'}, "expect": {'recovered': '13'}},
        {"stage": 'Use Tackle.', "select": {'case': 'check', 'label': 'tackle', 'source': 'selftest'}, "expect": {'recovered': '0'}},
    ],
    "nematocyst": [
        {"stage": 'Use Surf on Chansey, many times.', "select": {'case': 'check', 'label': 'surf_chansey', 'source': 'selftest'}, "expect": {'ok': 'true', 'all_toxic': 'true'}},
        {"stage": 'Use Poison Sting on Snorlax, many times.', "select": {'case': 'check', 'label': 'poison_sting', 'source': 'selftest'}, "expect": {'all_toxic': 'true'}},
        {"stage": 'Use Surf on Toxapex, many times.', "select": {'case': 'check', 'label': 'surf_toxapex', 'source': 'selftest'}, "expect": {'poisoned': '0'}},
    ],
    "soulsight": [
        {"stage": 'At -6 accuracy, use Aura Sphere on a Sand Veil foe in a sandstorm.', "select": {'case': 'check', 'label': 'aura_sphere_sand_veil', 'source': 'selftest'}, "expect": {'never_misses': 'true'}},
        {"stage": 'Use Focus Blast.', "select": {'case': 'check', 'label': 'focus_blast', 'source': 'selftest'}, "expect": {'never_misses': 'true'}},
        {"stage": 'Use Aura Sphere on a Ghost-type.', "select": {'case': 'check', 'label': 'aura_sphere_ghost', 'source': 'selftest'}, "expect": {'factor': '1.00', 'never_misses': 'true'}},
        {"stage": 'Take a Fake Out.', "select": {'case': 'check', 'label': 'fake_out', 'source': 'selftest'}, "expect": {'flinched': 'false', 'flinched_without': 'true'}},
    ],
    "deadeye": [
        {"stage": 'Use Hydro Pump on a +6 evasion Sand Veil foe in a sandstorm.', "select": {'case': 'check', 'label': 'hydro_pump_evasive', 'source': 'selftest'}, "expect": {'never_misses': 'true'}},
        {"stage": 'Use Snipe Shot on a foe at +2 Sp. Def.', "select": {'case': 'check', 'label': 'snipe_shot_raised', 'source': 'selftest'}, "expect": {'same_as_zero': 'true'}},
        {"stage": 'Use Snipe Shot on a foe at -1 Sp. Def.', "select": {'case': 'check', 'label': 'snipe_shot_lowered', 'source': 'selftest'}, "expect": {'same_as_zero': 'false'}},
        {"stage": 'At -2 accuracy, use Liquidation on a foe at +2 Defense.', "select": {'case': 'check', 'label': 'liquidation_contact', 'source': 'selftest'}, "expect": {'never_misses': 'false', 'same_as_zero': 'false'}},
        {"stage": 'Use Hydro Pump on a foe mid-Dive.', "select": {'case': 'check', 'label': 'hydro_pump_dive', 'source': 'selftest'}, "expect": {'hits': '0'}},
    ],
    "truant": [
        {"stage": 'On a loaf turn, use Bulk Up.', "select": {'case': 'check', 'label': 'bulk_up', 'source': 'selftest'}, "expect": {'acted': 'true', 'next_turn_acts': 'true'}},
        {"stage": 'On a loaf turn, use Double-Edge.', "select": {'case': 'check', 'label': 'double_edge', 'source': 'selftest'}, "expect": {'acted': 'false'}},
        {"stage": 'Recharge after Giga Impact, trying Bulk Up.', "select": {'case': 'check', 'label': 'recharge', 'source': 'selftest'}, "expect": {'acted': 'false', 'next_turn_acts': 'true'}},
        {"stage": 'On a loaf turn, use Metronome, which calls a damaging move.', "select": {'case': 'check', 'label': 'metronome', 'source': 'selftest'}, "expect": {'metronome_acted': 'true', 'called_damaging_acted': 'false'}},
        {"stage": "Let the AI pick a move on the holder's loaf turn.", "select": {'case': 'check', 'label': 'ai_slack_off', 'source': 'selftest'}, "expect": {'predicted_fail': 'DOUBLEEDGE:true,SLACKOFF:false'}},
        {"stage": 'With a Pokemon without Truant, use Double-Edge.', "select": {'case': 'check', 'label': 'not_truant', 'source': 'selftest'}, "expect": {'acted': 'true'}},
    ],
    # NV-31 hand ports: sun, sleep and petals; Daylily and Heliotrope compose from them.
    "daydreamer": [
        {"stage": 'Use Dream Eater on an awake foe.', "select": {'case': 'check', 'label': 'dream_eater', 'source': 'selftest'}, "expect": {'fails': 'false', 'healed': '20'}},
        {"stage": 'Use Nightmare on an awake foe, then end the round.', "select": {'case': 'check', 'label': 'nightmare', 'source': 'selftest'}, "expect": {'fails': 'false', 'nightmare': 'true', 'quarter_lost': 'true'}},
        {"stage": 'Leave the field; the awake foe under Nightmare ends a round.', "select": {'case': 'check', 'label': 'holder_gone', 'source': 'selftest'}, "expect": {'nightmare': 'false', 'lost': '0'}},
        {"stage": 'Use Hypnosis, then Yawn.', "select": {'case': 'check', 'label': 'hypnosis_yawn', 'source': 'selftest'}, "expect": {'hypnosis_fails': 'false', 'yawn_fails': 'false'}},
        {"stage": 'Use Snore while awake.', "select": {'case': 'check', 'label': 'snore_sleep_talk', 'source': 'selftest'}, "expect": {'snore_usable_awake': 'false'}},
        {"stage": 'With an ally without Daydreamer, use Dream Eater on an awake foe.', "select": {'case': 'check', 'label': 'ally_without', 'source': 'selftest'}, "expect": {'dream_eater_fails': 'true'}},
    ],
    "sunbask": [
        {"stage": 'End a round in sun, below full HP.', "select": {'case': 'check', 'label': 'sun', 'source': 'selftest'}, "expect": {'eighth_healed': 'true'}},
        {"stage": 'In sun, Giga Drain for 80.', "select": {'case': 'check', 'label': 'sun', 'source': 'selftest'}, "expect": {'drained': '80'}},
        {"stage": 'In clear weather, Giga Drain for 80, then end the round.', "select": {'case': 'check', 'label': 'clear', 'source': 'selftest'}, "expect": {'drained': '40', 'round_end_heal': '0'}},
        {"stage": 'In sun under Air Lock, then holding a Utility Umbrella.', "select": {'case': 'check', 'label': 'air_lock_umbrella', 'source': 'selftest'}, "expect": {'air_lock_drained': '40', 'air_lock_heal': '0', 'umbrella_drained': '40', 'umbrella_heal': '0'}},
    ],
    "chloroplast": [
        {"stage": 'In clear weather, use Solar Beam.', "select": {'case': 'check', 'label': 'solar_beam', 'source': 'selftest'}, "expect": {'charges': 'false'}},
        {"stage": 'In clear weather, use Weather Ball.', "select": {'case': 'check', 'label': 'weather_ball', 'source': 'selftest'}, "expect": {'type': 'FIRE', 'power': '100'}},
        {"stage": 'Use Fire Blast.', "select": {'case': 'check', 'label': 'fire_blast', 'source': 'selftest'}, "expect": {'sun_boosted': 'true'}},
        {"stage": 'In rain, use Fire Blast.', "select": {'case': 'check', 'label': 'fire_in_rain', 'source': 'selftest'}, "expect": {'sun_boosted': 'true'}},
        {"stage": 'In clear weather, use Synthesis.', "select": {'case': 'check', 'label': 'synthesis', 'source': 'selftest'}, "expect": {'two_thirds_healed': 'true'}},
        {"stage": 'Use Growth.', "select": {'case': 'check', 'label': 'growth', 'source': 'selftest'}, "expect": {'attack': '2', 'spatk': '2'}},
    ],
    "petalbarrier": [
        {"stage": 'Switch in and take a Surf.', "select": {'case': 'check', 'label': 'first_hit', 'source': 'selftest'}, "expect": {'hits': 'enter,SURF:HALF'}},
        {"stage": 'Take a second Surf.', "select": {'case': 'check', 'label': 'second_hit', 'source': 'selftest'}, "expect": {'hits': 'enter,SURF:HALF,SURF:FULL'}},
        {"stage": "Take Double Kick's two hits.", "select": {'case': 'check', 'label': 'double_kick', 'source': 'selftest'}, "expect": {'hits': 'enter,DOUBLEKICK:HALF,DOUBLEKICK:FULL'}},
        {"stage": 'Take a Surf, wait two rounds unhit, take another.', "select": {'case': 'check', 'label': 'no_regrow', 'source': 'selftest'}, "expect": {'hits': 'enter,SURF:HALF,wait,wait,SURF:FULL'}},
        {"stage": 'Take a Surf, switch out and back in, take another.', "select": {'case': 'check', 'label': 'reentry', 'source': 'selftest'}, "expect": {'hits': 'enter,SURF:HALF,enter,SURF:HALF'}},
    ],
    "flowergift": [
        {"stage": 'Cherrim (Grass) uses Petal Dance in rain.', "select": {'case': 'check', 'label': 'petal_dance_rain', 'source': 'selftest'}, "expect": {'boosted': 'false'}},
        {"stage": 'Cherrim Sunshine (Fire/Fairy) uses Solar Beam in sun.', "select": {'case': 'check', 'label': 'solar_beam_sun', 'source': 'selftest'}, "expect": {'boosted': 'true'}},
        {"stage": 'Use Morning Sun in a sandstorm.', "select": {'case': 'check', 'label': 'morning_sun_sand', 'source': 'selftest'}, "expect": {'three_quarters_healed': 'true'}},
    ],
}
