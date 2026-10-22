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
| `stab_grant` (NV-10) | `types` (a list of type names, or `all`), optional `multiplier` (1.5), `control` | `DamageCalcFromUser`: the same 1.5x on final damage that Nova's own STAB (`pbCalcDamageMultipliersSTAB`) applies, for moves of those types, only when the user lacks the type (never double STAB); Struggle (type nil) gets none | Nova's STAB step; generalised from the hand-written Full Moon |
| `conditional_boost` (NV-9) | `weather` (rain, sun, sand, hail) or `terrain` (grassy, electric, psychic, misty), `multiplier`, `moves` (`all` or `higher_stat`), optional `control` | `DamageCalcFromUser`, gated on `user.effectiveWeather` (a Utility Umbrella clears sun and rain; hail counts Nova's `:Snowstorm`) or on the field's terrain plus `user.affectedByTerrain?`. `all` multiplies power; `higher_stat` multiplies the attacking stat behind the user's higher one (physical when Attack >= Sp. Atk) | Sand Force (`all`), Solar Power (`higher_stat`) |

`probes` hold one checkable probe per `test_cases` entry, in the same order: the
move (its display name), the outcome (`result: boosted|normal`, or `converted:
true|false`), and optionally `hp` (a fraction of max HP to set first) or
`holder: false` (a Pokémon without the ability). A conditional boost's probes set
the scene instead of `holder`: `field: false` (no weather or terrain), `item` (a
held item, weather only: `Utility Umbrella`), `airborne: true` (terrain only), and
`stats: physical|special` (which attacking stat is higher; required for
`higher_stat`). A STAB grant's probes may set the user's `types` (a list of type
names; otherwise the user is the neutral `???`), and a probe may name `Struggle`,
which Essentials builds in code. `control` is a vanilla ability, by INTERNAL name,
that the self-test measures beside the port. From the block, for one target:

- **the port**, rendered by `apply` against the target's own PBS names. A probe,
  type or ability the game lacks blocks the port, says which, and keeps the
  ability's `DATA ONLY` line;
- **its self-test case**, which the port registers at load in
  `$chrooked_selftest_cases` (see the lab scripts below);
- **its harness checks**, one per probe, used instead of `harness_scenarios.py`
  on an Essentials 21 target.

**Every shape generates exactly one effect** (NV-9). A spec with more, such as
Infernal Maw (a biting boost *and* a burn chance *and* a flinch chance), cannot
take a template: `validate_spec` refuses it, at apply and on a web save (422),
because a boost-only port would mark the ability installed with most of it
missing. It needs a hand-written port, or a future shape that covers every effect.

A mechanic that fits no shape gets a hand-written `chrooked_<id>.rb` here. It must
register its own self-test case and have a scenario in `harness_scenarios.py`. A
spec with both a template and a file here is ambiguous, and apply blocks it. A new
shape starts the same way: hand-port one mechanic, prove it in the lab, then
generalise it (Forestry, NV-9).

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
| `010_battle_selftest.rb` | headless self-test: when `chrooked-selftest.on` names a mechanic, it runs a measured damage A/B (same battlers and RNG seed, with the ability, with none, with a control) and one AI-vs-AI battle in `Battle::DebugSceneNoVisuals`, then logs `DONE`. It measures the cases the installed ports registered in `$chrooked_selftest_cases`, so a new port needs no edit here; it loads before `998_ChrookedMods/` but reads the cases only when it fires, after every port has loaded. A CALC entry may carry a setup hash (`[move, hp, {weather:, terrain:, item:, airborne:, stats:, types:}]`), applied to the same battlers before every ability is measured (NV-9, NV-10); `:STRUGGLE` is built as a battle builds it. A `heal:` list (`[[:MOONLIGHT, 0.5]]`) measures what a healing move restores with the ability and without (HEAL lines, NV-10). A `chance:` list (`[[:CRUNCH, {status: :BURN, status_rate: 0.3, flinch_rate: 0.3}]]`) measures an on-hit chance: the damage A/B once, then the user's `OnDealingHit` handler fired 400 times on a fresh target with a fixed seed, the rates checked within 3 standard deviations (exactly 0 when 0 is expected) and logged as the mechanic's OBS line with `source=selftest` (NV-11). `setup:` may also set `target_types:`. Safe to arm briefly on a played copy: saves point at `chrooked-selftest-saves/` while it runs, the globals it sets are restored, it runs once per process, and errors (Hangup included) are logged, never raised |

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
  ports that read them are in the table below. `wing` followed in NV-9 for Updraft
  (8 moves); `bone` and `ballistic` stay unwritten until a port needs them.
- *Simple multipliers:* downpour, forestry, updraft and whiteout are generated
  since NV-9, mysticpower and violentblood since NV-10 (`stab_grant`).
  nightstalker has two effects (a darkness boost and a crit stage), so it needs a
  hand port or a shape covering both.
- *Two effects, hand-written (NV-10):* fullmoon and highnoon grant STAB *and* make
  Moonlight / Morning Sun heal 3/4. infernalmaw followed (NV-11, three effects).
- *frostbite and rimefang (NV-12, Chris's decision 2026-10-22):* the Ruleset's
  frostbite is ported to Nova as a reskin of freeze (`chrooked_frostbite.rb`), so
  every freeze in Nova is now frostbite. Rimefang inflicts it, built as Infernal
  Maw is.
- *Composition:* finishingkick, which borrows Speed Boost through
  `behaviors: [finishingkick, speedboost]`. Essentials 21 has no composition step
  yet; `HandlerHash#copy` might serve, unverified.
- *Every other table* above, and the 25 Nova abilities with no Rejuvenation port.

## Ported mechanics

33 in all. 28 are generated from their specs' `template:` blocks: 22 since
2026-10-22 (NV-8), four more (NV-9) and two more (NV-10) the same day. Five are
hand-written here:
- `chrooked_fullmoon.rb` and `chrooked_highnoon.rb` (NV-10) and
  `chrooked_infernalmaw.rb` (NV-11), because each has more than one effect;
- `chrooked_rimefang.rb` (NV-12), for the same reason;
- `chrooked_frostbite.rb` (NV-12), a status and not an ability: method wrappers
  rather than a registry entry.

Their
checks live in `SCENARIOS_ESSENTIALS21`, which an Essentials 21 target consults
before `SCENARIOS`. For the NV-8 22, before the hand ports were deleted, the
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
| forestry | `conditional_boost`, Grassy Terrain, `moves: all`, 1.3x | NV-9: hand-ported first, lab 3/3 (Tackle), then generated with identical code. Lab 3/3: Body Slam 1.300x on Grassy Terrain (grounded); 1.000x with no terrain and while airborne (Magnet Rise) |
| downpour, whiteout | `conditional_boost`, rain / hail, `moves: higher_stat`, 1.5x | NV-9, lab: Downpour 4/4, Whiteout 3/3. Body Slam 1.469x when Attack is higher, Hyper Voice 1.500x when Sp. Atk is higher, 1.000x for the other category; Downpour holding a Utility Umbrella in rain 1.000x |
| mysticpower, violentblood | `stab_grant`, `all` / `[Dark]` | NV-10, lab 3/3 each. Mystic Power: Flamethrower from a Water-type 1.500x; Surf (its own type) 36 vs 36, STAB once; Struggle unchanged. Violent Blood: Crunch from a Water/Dragon 1.500x; from a Dark-type 42 vs 42; Waterfall unchanged |
| fullmoon, highnoon (hand-written) | STAB grant for Dark+Fairy / Fire+Psychic, plus a 3/4 heal on Moonlight / Morning Sun (`HealUserDependingOnWeather#pbOnStartUse`, chained wrappers) | NV-10, lab 3/3 each. Dark Pulse (Full Moon) 1.478x and Flamethrower (High Noon) 1.500x from a Normal-type; the other type unchanged; the heal 101 of 135 HP at half HP (normally 68). In the AI battle, Numel's own-type Flamethrower under Full Moon logged `own=true` with no extra bonus |
| frostbite (hand-written; a status) | freeze reskinned, keeping `:FROZEN`. No lost turns or random thaw (`pbTryUseMove` with `@status` cleared around it, as Rejuvenation's port does; also the multi-hit cut-off and the AI's `can_attack?`). Special damage halved unless Guts or Quick Feet (beside burn's halving). A 1/16 end-of-round chip unless Magic Guard (after burn's chip). Cured by a move that thaws its user (Nova's `ThawsUser`). Its text and name say frostbite | NV-12, lab 9/9: 50 of 50 turns acted, never cured; Surf 12 vs 24; Tackle, Guts and Quick Feet unchanged; chip 8 of 135 HP, Magic Guard 0; Flame Wheel cures, Ember does not; Ice-types immune. Kept from Nova (the spec is silent): a Fire hit cures the target, harsh sun prevents it, the catch bonus, the FRZ icon, Pursuit's skip |
| rimefang (hand-written) | Infernal Maw's build with frostbite (`pbCanFreeze?`/`pbFreeze`) in place of burn | NV-12, lab 3/3: frostbite 0.308 and flinch 0.305 over 400 rolls; Ice-type 0 frostbite, flinch 0.300; Tackle 0 and 0; Crunch 36 vs 28 |
| infernalmaw (hand-written) | 1.3x on `Biting` (Strong Jaw's shape), plus a 30% burn and an independent 30% flinch in `OnDealingHit` (Poison Touch's shape and gates) | NV-11, lab 3/3. Crunch 36 vs 28 (Strong Jaw control 41); 400 rolls each: burn 0.308 and flinch 0.305 on a burnable target; on a Fire-type 0 burns and flinch 0.300; Tackle 0 and 0 |
| updraft | `flag_boost`, 1.3x on `Wing` / `Wind` | NV-9, lab 3/3: Brave Bird 1.293x (the dex's new `Wing` flag), Hurricane 1.300x (Nova's own `Wind`), Tackle 1.000x |
| hammerfist, impale, martialartist, sledgehammer, striker | `flag_boost`, 1.3x on `Punching` / `Hammer` / `Kicking` / `Piercing` | lab, 2026-10-22: 3/3 each; Body Slam 1.300x, Wood Hammer and Megahorn 1.293x, High Jump Kick 1.289x, Tackle 1.000x; Sledgehammer leaves Mach Punch at 14 while the Iron Fist control gives 17. The "without the ability" cases (Impale, Striker) are measured by the self-test's `without` option, which logs `source=selftest`. Striker's now uses High Jump Kick, as its spec says (it was Blaze Kick): holder 58, Stench and no ability 45 |

**thor, 2026-10-22 (NV-8):** all 22 generated ports were proven in one boot with
`nova_thor_selftest.sh arm|read|disarm` (Kirin 0.3.5, Ruby 3.1.0 aarch64-linux-android).
The score was 66/66, and all 52 damage measurements were identical to the PC lab's
(mjolnir runbook 31). The four NV-9 ports followed the same day in one boot:
13/13, every measurement identical to the lab's, including the first on-device run
of the self-test's scene setup (terrain, rain, hail, Utility Umbrella, Magnet
Rise). The four NV-10 ports followed in one boot: 12/12, every damage and heal
measurement identical to the lab's. Infernal Maw (NV-11) followed: 3/3, its 400-roll
chance lines identical to the lab's (the same seed gives the same rolls on ARM).
Frostbite and Rimefang (NV-12) are deployed; their device proof follows.

The CALC phase sets both battlers to the `???` type (`neutral: true`), so the ratio
is the ability alone: no same-type bonus, no type matchups.

A spec case about a Pokémon **without** the ability cannot be logged by an
Essentials 21 port, which only ever runs for its holder. The self-test's
`without:` moves measure it instead: the holder, a Stench holder (no damage
effect) and no ability, on the same battlers. The result is logged as the
mechanic's `OBS` line, tagged `source=selftest`. A scenario `select` may list
several move names (`["HIJUMPKICK", "HIGHJUMPKICK"]`) for moves 16.2 and
Essentials 21 name differently.
