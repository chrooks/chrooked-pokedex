# Essentials 21 harness assets

Ported mechanics for Pokémon Essentials 21 games (v21.1 and the 21.99 line;
first Target: Pokémon Nova V3.0, mkxp-z, Ruby 3.1), plus the lab-only scripts
that prove them. Built for mjolnir NV-5. The 16.2 counterpart is
`../essentials-harness/`.

## The Seam: handler registries

Essentials 21 wires ability, item and move effects through lookup tables keyed
by ID, such as `Battle::AbilityEffects::DamageCalcFromUser` and
`AccuracyCalcFromUser` (defined in `011_Battle/007_Other battle code/008_Battle_AbilityEffects.rb`).
The battle code asks the table for the attacker's ability's entry and runs it,
only when `user.abilityActive?`. A port is therefore one `.add(:ID, proc)` call:

- no method is overridden, so a port cannot change any other ability;
- suppression (Gastro Acid, Neutralizing Gas) stays the engine's job;
- the AI's damage estimate reads the same table, so it accounts for the port too.

The 16.2 ports needed `alias_method` chaining and a deferred install; these need
neither.

## Install

`chrooked-pokedex apply --engine essentials` (the `behaviors` category, last in the
v21 tier order) copies each valid `chrooked_<id>.rb` into the target's
`Data/Scripts/998_ChrookedMods/`. Essentials loads every `.rb` under
`Data/Scripts/` in name order, files before folders, so that folder runs after
the game's battle code and before `999_Main` starts the game. The dex owns the
folder: an unchanged port is not rewritten, and a `chrooked_*.rb` with no valid
port behind it is removed and reported. Nothing else under `Data/Scripts/` is
touched. That matters on thor, where `998_ChrookedKirin/` holds the controls shim.

`scripts/nova_apply.sh` deploys the folder's `chrooked_*.rb` files to Nova's
live PC copy and to thor beside the compiled `.dat` files.

## Oracle: marker-gated

A port writes `chrooked_load.log` in the game folder only when
`chrooked-oracle.on` exists there at boot. Played copies stay silent unless a
proof run sets the marker. Errors are always written.

    [chrooked:<id>] OBS key=value ...   a real battle event, scored by the harness
    [chrooked:<id>] EST key=value ...   an AI estimate, never scored

The OBS keys match the 16.2 ports', so `harness_scenarios.py` is shared.
`python -m chrooked_pokedex.behavior.harness stage|verify <id> --target <game>`
detects the v21 dialect, reads the game-folder log, and `stage` sets the marker.

## Lab-only scripts (`lab/`)

Copied into the **lab copy's** `Data/Scripts/998_ChrookedDexLab/` by
`nova_apply.sh` and `nova_selftest.sh`. Never deployed to a played copy.

| file | role |
| --- | --- |
| `001_register_black_weather.rb` | Nova only: registers the `:Black` weather map 050 uses, so the PBS writer and compiler finish; lands the debug boot on the title screen |
| `002_lab_save_dir.rb` | points `SaveData::DIRECTORY` at the lab's own `LabSaves/`; lab and live share `Title=Nova`, so both otherwise save into the synced `%AppData%\Roaming\Nova` |
| `010_battle_selftest.rb` | headless self-test: when `chrooked-selftest.on` names a mechanic, it runs a measured damage A/B (same battlers and RNG seed, with the ability, with none, with a control) and one AI-vs-AI battle in `Battle::DebugSceneNoVisuals`, then logs `DONE`. One `CASES` entry per mechanic. Safe to arm briefly on a played copy: saves point at `chrooked-selftest-saves/` while it runs, the globals it sets are restored, it runs once per process, and errors (Hangup included) are logged, never raised |

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

Syncs the lab scripts, installs the port if the lab's copy is stale, boots the
lab once (`nova_selftest.ps1`, about 6 s), and scores the OBS lines with the
harness. A new mechanic needs its port here, a `CASES` entry in
`lab/010_battle_selftest.rb`, and a scenario in `harness_scenarios.py`.

## Files

| file | Seam | verified |
| --- | --- | --- |
| `chrooked_kindle.rb` | `DamageCalcFromUser` (Blaze's shape, no HP check) | `nova_selftest.sh kindle` 3/3, 2026-10-22, Nova V3.0 lab: Flamethrower 1.500x, Surf and Tackle 1.000x, Ember at full HP 1.474x, Blaze unchanged at full HP. **thor**, same day, Kirin 0.3.5 (Ruby 3.1.0 aarch64-linux-android): harness 3/3 with identical damage numbers |
