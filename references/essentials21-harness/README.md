# Essentials 21 harness assets

Ported mechanics for Pokémon Essentials 21 games (v21.1 and the 21.99 line;
first Target: Pokémon Nova V3.0, mkxp-z, Ruby 3.1), plus the lab-only scripts
that prove them. Built for mjolnir NV-5. Since NV-8 a mechanic in a proven shape
has no file here: `apply` generates its port from the `template:` block in its
behavior spec. The 16.2 counterpart is `../essentials-harness/`.

## The Seam: handler registries

Essentials 21 wires ability, item and move effects through lookup tables keyed
by ID, such as `Battle::AbilityEffects::DamageCalcFromUser` and
`AccuracyCalcFromUser` (defined in `011_Battle/007_Other battle code/008_Battle_AbilityEffects.rb`).
The battle code asks the table for the attacker's ability's entry and runs it,
only when `user.abilityActive?`. A port is therefore one `.add(:ID, proc)` call:

- no method is overridden, so a port cannot change any other ability;
- suppression (Gastro Acid, Neutralizing Gas) stays the engine's job;
- the AI's damage estimate (`Battle::AI::AIMove#rough_damage`) reads the same
  table, so it accounts for the port too.

The 16.2 ports needed `alias_method` chaining and a deferred install; these need
neither.

## Generated ports: templates (NV-8)

A behavior spec whose mechanic is one of the proven shapes carries a `template:`
block, and the dex generates the rest from it (`src/chrooked_pokedex/behavior/templates.py`):

    template:
      shape: flag_boost
      params: {flags: [kicking], multiplier: 1.3}
      probes:
        - {move: High Jump Kick, result: boosted}
        - {move: Tackle, result: normal}
        - {move: High Jump Kick, result: normal, holder: false}

| shape | params | the port | modelled on Nova's |
| --- | --- | --- | --- |
| `type_boost` | `type`, `multiplier`, optional `pinch`, `control` | `DamageCalcFromUser`: attack-stat multiplier on moves of the type; `pinch: true` adds `user.hp <= user.totalhp / 3` | Blaze (without its HP check unless `pinch`) |
| `type_conversion` | `type`, `multiplier` (default 1.2), optional `control` | `ModifyMoveBaseType` turns Normal moves into the type and sets `move.powerBoost`; a `DamageCalcFromUser` power rider reads that flag | Aerilate, Dragonize |
| `flag_boost` | `flags` (Ruleset move flags), `multiplier`, optional `control` | `DamageCalcFromUser`: power multiplier when the move carries one of the flags | Iron Fist |

`probes` hold one checkable probe per `test_cases` entry, in the same order: the
move (its display name), the outcome (`result: boosted|normal`, or `converted:
true|false`), and optionally `hp` (a fraction of max HP to set first) or
`holder: false` (a Pokémon without the ability). `control` is a vanilla ability,
by INTERNAL name, that the self-test measures beside the port. From the block,
for one target:

- **the port**, rendered by `apply` against the target's own PBS names. A probe,
  type or ability the game lacks blocks the port, says which, and keeps the
  ability's `DATA ONLY` line;
- **its self-test case**, which the port registers at load in
  `$chrooked_selftest_cases` (see the lab scripts below);
- **its harness checks**, one per probe, used instead of `harness_scenarios.py`
  on an Essentials 21 target.

A mechanic that fits no shape gets a hand-written `chrooked_<id>.rb` here. It must
register its own self-test case and have a scenario in `harness_scenarios.py`. A
spec with both a template and a file here is ambiguous, and apply blocks it.

## Install

`chrooked-pokedex apply --engine essentials` (the `behaviors` category, last in the
v21 tier order) writes each port into the target's
`Data/Scripts/998_ChrookedMods/`: generated from its spec's template, or copied
from a hand-written `chrooked_<id>.rb` here. Essentials loads every `.rb` under
`Data/Scripts/` in name order, files before folders, so that folder runs after
the game's battle code defines the registries and before `999_Main` starts the
game: a port registers at load, with no method override and no deferred install.
The dex owns the folder: an unchanged port is not rewritten, and a `chrooked_*.rb`
with no valid port behind it is removed and reported. Nothing else under
`Data/Scripts/` is touched. That matters on thor, where `998_ChrookedKirin/` holds
the controls shim.

Every port carries the small `ChrookedLog` module behind `unless defined?`, so each
file stands alone and the first one loaded defines it.

`scripts/nova_apply.sh` deploys the folder's `chrooked_*.rb` files to Nova's
live PC copy and to thor beside the compiled `.dat` files.

## Oracle: marker-gated

A port writes `chrooked_load.log` in the game folder only when
`chrooked-oracle.on` exists there at boot. Played copies stay silent unless a
proof run sets the marker. Errors are always written. Essentials evals each
script under a bare file name, so a port resolves both paths from the working
directory once, at load, while that is the game folder (on the PC and on Kirin).

    [chrooked:<id>] OBS key=value ...   a real battle event, scored by the harness
    [chrooked:<id>] EST key=value ...   an AI estimate, never scored

A line is `EST` when the handler was called from the AI's damage estimate
(`AIMove` in the caller's stack), `OBS` otherwise. A hand port's OBS keys match
the 16.2 ports', so `harness_scenarios.py` is shared; a templated spec's checks
are generated from its probes.
`python -m chrooked_pokedex.behavior.harness stage|verify <id> --target <game>`
detects the v21 dialect, reads the game-folder log, and `stage` sets the marker.

## Lab-only scripts (`lab/`)

Copied into the **lab copy's** `Data/Scripts/998_ChrookedDexLab/` by
`nova_apply.sh` and `nova_selftest.sh`. Never deployed to a played copy.

| file | role |
| --- | --- |
| `001_register_black_weather.rb` | Nova only: registers the `:Black` weather map 050 uses, so the PBS writer and compiler finish; lands the debug boot on the title screen |
| `002_lab_save_dir.rb` | points `SaveData::DIRECTORY` at the lab's own `LabSaves/`; lab and live share `Title=Nova`, so both otherwise save into the synced `%AppData%\Roaming\Nova` |
| `010_battle_selftest.rb` | headless self-test: when `chrooked-selftest.on` names a mechanic, it runs a measured damage A/B (same battlers and RNG seed, with the ability, with none, with a control) and one AI-vs-AI battle in `Battle::DebugSceneNoVisuals`, then logs `DONE`. It measures the cases the installed ports registered in `$chrooked_selftest_cases`, so a new port needs no edit here; it loads before `998_ChrookedMods/` but reads the cases only when it fires, after every port has loaded. Safe to arm briefly on a played copy: saves point at `chrooked-selftest-saves/` while it runs, the globals it sets are restored, it runs once per process, and errors (Hangup included) are logged, never raised |

### Why the self-test has four hooks

It runs at the first of `GameData.load_all`, `Game.set_up_system`, the title
screen's `Scene_Intro#main`, or the first frame after game data exists. On the PC
the first three all fire. On Kirin 0.3.5, `Game.set_up_system` is redefined after
the game's scripts load by a file named `[I need this] translation_patches.rb`,
which is in neither the game folder nor Kirin's shared folder, so it most likely
ships inside the Kirin app. Our title-screen wrapper never fired there either. The
`load_all` hook fired first and ran the test. Each hook logs where the two
methods are defined when it fires, so a runtime that swaps them out shows up in
the log.

## Verify a mechanic on thor (one boot)

    scripts/nova_apply.sh                       # the port must be deployed
    scripts/nova_thor_selftest.sh arm <id>      # self-test + markers onto thor
    # kill Kirin, launch Nova, stop at the title screen, do not load the save
    scripts/nova_thor_selftest.sh read <id>     # fetch thor's log, score it
    scripts/nova_thor_selftest.sh disarm        # take it all off; relaunch Kirin before playing

The one deliberate exception to "no lab scripts on a played copy", kept to a
folder of its own (`998_ChrookedSelfTest/`) and removed straight after.

## Verify a mechanic in the lab (no one playing)

    scripts/nova_selftest.sh <id>     # e.g. kindle
    scripts/nova_selftest.sh --all    # every port apply installed in the lab

Syncs the lab scripts, runs `apply --category behaviors` (renders generated
ports, copies hand ones, leaves unchanged ones alone), boots the lab once
(`nova_selftest.ps1`, about 6 s), and scores the OBS lines with the harness. A new
mechanic in a known shape needs only a `template:` block in its spec. A
hand-written one needs its port here, registering its own self-test case, and a
scenario in `harness_scenarios.py`.

## From the Rejuvenation ports (`../rejuv-harness/`)

Rejuvenation's engine has no ability registries, so its core
(`chrooked_00_core.rb`) wraps the battle methods once and keeps its own tables;
each Rejuvenation port is a lambda in one table, and the core multiplies **final
damage** by what a damage lambda returns. Essentials 21 ships the registries and
offers power, attack, defense and final multipliers, so a translation follows the
matching vanilla handler in Nova (Blaze, Torrent, Aerilate…), not the Rejuvenation
arithmetic.

| Rejuvenation table | Essentials 21 registry | status |
| --- | --- | --- |
| `CHROOKED_DAMAGE_MODS` (attacker ability) | `DamageCalcFromUser` | **verified** 2026-10-22: called from `Battle::Move#pbCalcDamageMultipliersAbilities` only `if user.abilityActive?`; 10 ports at PASS |
| `Chrooked.hammer_move?` / `kick_move?` / `piercing_move?` (hard-coded lists or Rejuvenation's `:kickmove`) | the move's own `Flags`: `Kicking`, `Hammer`, `Piercing`, written by the dex | **verified** 2026-10-22 (NV-7): the dex's v21 vocabulary writes them from the Ruleset's move flags; Nova's compiler keeps Flags as free strings |
| `register_ize` (`CHROOKED_TYPE_MODS` + 1.2x rider) | `ModifyMoveBaseType` + `DamageCalcFromUser` on `move.powerBoost` | **verified** 2026-10-22: the pair Nova's Aerilate and Dragonize use; damage identical to Aerilate; 12 ports at PASS |
| `CHROOKED_DEFENSE_MODS` | `DamageCalcFromTarget` | candidate, unverified |
| `CHROOKED_ON_DEAL`, `CHROOKED_ON_DEAL_DMG` | `OnDealingHit` | candidate, unverified |
| `CHROOKED_WHEN_HIT`, `CHROOKED_WHEN_HIT_DMG` | `OnBeingHit` | candidate, unverified |
| `CHROOKED_SWITCH_IN` | `OnSwitchIn` | candidate, unverified |
| `CHROOKED_ON_KO` | `OnEndOfUsingMove` | candidate, unverified |
| `CHROOKED_TYPE_IMMUNITY` | `MoveImmunity` | candidate, unverified |
| `CHROOKED_SURE_HIT`, `CHROOKED_ACCURACY_MODS` | `AccuracyCalcFromUser` | candidate, unverified |
| `CHROOKED_PRIORITY_MODS` | `PriorityChange` | candidate, unverified |
| `CHROOKED_SPEED_MODS` / `CHROOKED_CRIT_RATE` | `SpeedCalc` / `CriticalCalcFromUser` | candidate, unverified |
| `CHROOKED_TURN_END` | `EndOfRoundEffect` / `EndOfRoundHealing` | candidate, unverified |
| the rest (`STAT_SWAP`, `ADDED_TYPE`, `ABSORB_MODS`, `HEAL_OVERRIDE`, `TARGET_MODS`, `TYPEMOD_FLOOR`, `IMMUNITY_BYPASS`, `HP_LOSS_VETO`, `WEATHER_IMMUNE`, `WEATHER_FOR_USER`, `AFTER_MOVE`, `AI_HP_REFUND`) | no single registry; likely method-level work | unmapped |

A candidate becomes verified only after reading its call site in Nova's
`Data/Scripts/011_Battle/` and a port of it passing the self-test.

**Deferred from the first batch, and why:**

- *Move categories* — **resolved 2026-10-22 (NV-7, Chris's decision):** the dex
  now writes the Ruleset's `kicking`, `hammer` and `piercing` move flags into an
  Essentials 21 game's data as the custom flags `Kicking`, `Hammer`, `Piercing`
  (`appliers/essentials/vocab.py`). In Nova that is 17, 10 and 14 moves. The five
  ports that read them are in the table below. `wing`, `bone` and `ballistic`
  stay unwritten until a port needs them.
- *Simple multipliers without a harness scenario yet:* downpour, forestry,
  mysticpower, nightstalker, updraft, violentblood, whiteout. With templates they
  need probes in their specs, not scenarios, if they fit a shape.
- *Composition:* finishingkick, which borrows Speed Boost through
  `behaviors: [finishingkick, speedboost]`. Essentials 21 has no composition step
  yet; `HandlerHash#copy` might serve, unverified.
- *Every other table* above, and the 25 Nova abilities with no Rejuvenation port.

## Ported mechanics

All 22 are generated from their specs' `template:` blocks since 2026-10-22 (NV-8),
and no hand-written port remains here. Before the hand ports were deleted, the
regeneration was checked three ways: each generated port's code matched its hand
port line for line (comments and the self-test registration aside), its generated
checks matched the old scenario, and `nova_selftest.sh --all` scored 66/66 with
damage numbers identical to the hand ports' for 21 of the 22. Kindle is the
exception, by design (below).

| mechanics | template | verified |
| --- | --- | --- |
| kindle | `type_boost`, Fire 1.5x, control Blaze | Hand port, 2026-10-22: lab 3/3 (Flamethrower 1.500x, Surf and Tackle 1.000x, Ember at full HP 1.474x, Blaze unchanged at full HP); **thor**, same day, Kirin 0.3.5 (Ruby 3.1.0 aarch64-linux-android): harness 3/3 with identical damage numbers. Regenerated (NV-8): now measured neutral like the rest and logging `ability=true` instead of `kindle=true`; its second probe is Surf, as the spec says, not Tackle. Lab 3/3: Flamethrower 1.500x, Surf 1.000x, Ember 1.462x (a smaller hit without the same-type bonus, so the flat +2 weighs more) |
| bloom, cryomancer, deluge | `type_boost`, Grass / Ice / Water 1.5x | lab, 2026-10-22: 3/3 each; 1.500x on full hits, 1.417x on Vine Whip-sized hits, off-type 1.000x; Overgrow and Torrent unchanged at full HP |
| overcharge | `type_boost`, Electric 1.5x, `pinch` | lab, 2026-10-22: 3/3; Thunderbolt 1.500x at 1/4 HP, 1.000x at full HP; Ice Beam 1.000x at 1/4 HP |
| chitinize, foliate, hydrate, immolate, martialize, mineralize, obfuscate, psyonize, spectralize, tectonize, venomize, wyvernize | `type_conversion`, 1.2x, control Aerilate | lab, 2026-10-22: 3/3 each; Tackle converts and hits 17 vs 14 (1.214x), equal to Aerilate; already-typed moves unchanged. The foe-weak/foe-resists cases pass on `converted`/`boosted`; effectiveness itself was not measured (neutral `???` foe) |
| hammerfist, impale, martialartist, sledgehammer, striker | `flag_boost`, 1.3x on `Punching` / `Hammer` / `Kicking` / `Piercing` | lab, 2026-10-22: 3/3 each; Body Slam 1.300x, Wood Hammer and Megahorn 1.293x, High Jump Kick 1.289x, Tackle 1.000x; Sledgehammer leaves Mach Punch at 14 while the Iron Fist control gives 17. The "without the ability" cases (Impale, Striker) are measured by the self-test's `without` option, which logs `source=selftest`. Striker's now uses High Jump Kick, as its spec says (it was Blaze Kick): holder 58, Stench and no ability 45 |

On thor, only Kindle's hand port was ever proven; the generated ports are deployed
there but not yet proven on the device.

The CALC phase sets both battlers to the `???` type (`neutral: true`), so the ratio
is the ability alone: no same-type bonus, no type matchups.

A spec case about a Pokémon **without** the ability cannot be logged by an
Essentials 21 port, which only ever runs for its holder. The self-test's
`without:` moves measure it instead: the holder, a Stench holder (no damage
effect) and no ability, on the same battlers. The result is logged as the
mechanic's `OBS` line, tagged `source=selftest`. A scenario `select` may list
several move names (`["HIJUMPKICK", "HIGHJUMPKICK"]`) for moves 16.2 and
Essentials 21 name differently.
