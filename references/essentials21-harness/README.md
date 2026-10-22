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
| `010_battle_selftest.rb` | headless self-test: when `chrooked-selftest.on` names a mechanic, it runs a measured damage A/B (same battlers and RNG seed, with the ability, with none, with a control) and one AI-vs-AI battle in `Battle::DebugSceneNoVisuals`, then logs `DONE`. One `CASES` entry per mechanic |

## Verify a mechanic in the lab (no one playing)

    scripts/nova_selftest.sh <id>     # e.g. kindle

Syncs the lab scripts, installs the port if the lab's copy is stale, boots the
lab once (`nova_selftest.ps1`, about 6 s), and scores the OBS lines with the
harness. A new mechanic needs its port here, a `CASES` entry in
`lab/010_battle_selftest.rb`, and a scenario in `harness_scenarios.py`.

## Files

| file | Seam | verified |
| --- | --- | --- |
| `chrooked_kindle.rb` | `DamageCalcFromUser` (Blaze's shape, no HP check) | `nova_selftest.sh kindle` 3/3, 2026-10-22, Nova V3.0 lab: Flamethrower 1.500x, Surf and Tackle 1.000x, Ember at full HP 1.474x, Blaze unchanged at full HP |
