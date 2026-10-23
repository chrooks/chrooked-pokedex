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
| `type_conversion` | `type`, `multiplier` (default 1.2), optional `from` (`normal`, the default, or `any`), `flags`, `control` | `ModifyMoveBaseType` turns Normal moves (or, with `from: any`, every move) into the type and sets `move.powerBoost`; `flags` limits it to moves carrying one of them (NV-13). A `DamageCalcFromUser` power rider reads that flag | Aerilate, Dragonize; Normalize (`from: any`); the flag test as Liquid Voice reads Sound |
| `flag_boost` | `flags` (Ruleset move flags), `multiplier`, optional `control` | `DamageCalcFromUser`: power multiplier when the move carries one of the flags | Iron Fist |
| `stab_grant` (NV-10) | `types` (a list of type names, or `all`), optional `multiplier` (1.5), `control` | `DamageCalcFromUser`: the same 1.5x on final damage that Nova's own STAB (`pbCalcDamageMultipliersSTAB`) applies, for moves of those types, only when the user lacks the type (never double STAB); Struggle (type nil) gets none | Nova's STAB step; generalised from the hand-written Full Moon |
| `conditional_boost` (NV-9) | `weather` (rain, sun, sand, hail) or `terrain` (grassy, electric, psychic, misty), `multiplier`, `moves` (`all` or `higher_stat`), optional `control` | `DamageCalcFromUser`, gated on `user.effectiveWeather` (a Utility Umbrella clears sun and rain; hail counts Nova's `:Snowstorm`) or on the field's terrain plus `user.affectedByTerrain?`. `all` multiplies power; `higher_stat` multiplies the attacking stat behind the user's higher one (physical when Attack >= Sp. Atk) | Sand Force (`all`), Solar Power (`higher_stat`) |
| `hit_status` (NV-13) | `status` (`burn`, `poison`, `paralysis`), `chance` (a whole percent), and `type` or `flags` | `OnDealingHit`: after a hit that dealt damage, when the move as used (`move.calcType`) is of the type or carries one of the flags, a `chance`% roll to inflict the status. Never through Shield Dust or on a target unaffected by additional effects; `pbCan<Status>?` is asked before the roll. Nova's own message strings | Poison Touch; generalised from the hand-written Pyre |
| `type_immunity` (NV-13) | `type` | `MoveImmunity`: every move of the type aimed at the holder fails, status moves included ("It doesn't affect..."), unless Mold Breaker bypasses it; never a move the holder aims at itself | Bulletproof, keyed on the type; generalised from the hand-written Nocturnal |
| `hit_drain` (NV-14) | `fraction` (of the damage), `moves` (`contact` or `non_contact`) | `OnDealingHit`: after a hit that dealt damage, when the move does (or does not) make contact (`pbContactMove?`), the user heals round(fraction x the HP the target lost) through Nova's drain path, `pbRecoverHPFromDrain`: Big Root adds 30%, Heal Block and full HP stop it, a Liquid Ooze target reverses it. Silent when the user could not heal and the target has no Liquid Ooze | Nova's drain moves (Giga Drain); generalised from the hand-written Vampiric |
| `ko_effect` (NV-14) | `heal` (a fraction of max HP) or `stat` (`attack`, `defense`, `special_attack`, `special_defense`, `speed`) | `OnEndOfUsingMove`: after each move the holder uses, counting the targets whose damage state says they fainted; nothing if the knockout ended the battle. `heal`: once, while the user can heal, with Ice Body's message. `stat`: one stage per foe knocked out | Moxie; generalised from the hand-written Carnivore |
| `priority_boost` (NV-14) | `type`, optional `full_hp` | `PriorityChange`: +1 priority for moves whose own type (`move.type`) is the type, only at full HP when `full_hp` is true | Gale Wings; generalised from the hand-written Rapid Combustion |
| `damage_taken` (NV-20) | `rules`: a list of `{multiplier, type?, contact?}` (a multiplier may be a fraction, `"1/3"`) | `DamageCalcFromTarget`: the damage the holder takes, times every matching rule (contact by `pbContactMove?`); logs `factor` | Fluffy, Thick Fat |
| `type_absorb` (NV-20) | `type`, and `heal: true` or `stats` (a list) | `MoveImmunity`: a move of the type is absorbed: Nova's own `pbMoveImmunityHealingAbility` (a quarter of max HP) or `pbMoveImmunityStatRaisingAbility`, several stats in turn. The `defend` phase reports HEALED, RAISED or NONE | Volt Absorb, Sap Sipper |
| `struck_status` (NV-19) | `status`, `chance` | `OnBeingHit`: after a contact move damaged the holder, a `chance`% roll to give the ATTACKER the status, unless it is spared contact effects; measured by the self-test struck phase (side=struck) | Flame Body, Poison Point, Static |
| `type_resist` (NV-18) | `type`, `multiplier` | `DamageCalcFromTarget`: the damage the holder takes from moves of the type, times the multiplier (final damage, so a half is exact) | Thick Fat |
| `keeps` (NV-18, blocks only) | none | generates nothing: the game's own ability of that name already does the effect. Its probes (`measure: status|eor_status`, `status`) measure the ability against none | — |

`probes` hold one checkable probe per `test_cases` entry, in the same order: the
move (its display name), the outcome (`result: boosted|normal`, or `converted:
true|false`), and optionally `hp` (a fraction of max HP to set first) or
`holder: false` (a Pokémon without the ability). A conditional boost's probes set
the scene instead of `holder`: `field: false` (no weather or terrain), `item` (a
held item, weather only: `Utility Umbrella`), `airborne: true` (terrain only), and
`stats: physical|special` (which attacking stat is higher; required for
`higher_stat`). A STAB grant's probes may set the user's `types` (a list of type
names; otherwise the user is the neutral `???`), and a probe may name `Struggle`,
which Essentials builds in code. A hit status's probes say `inflicts: true|false`
(whether the roll can land) and may set `target_types` (a Fire type cannot be
burned); a type immunity's say `immune: true|false`. Neither takes `hp`. A hit
drain's say `drain: healed|none|reversed`, and `ooze: true` gives the target
Liquid Ooze. A knockout effect's name no move: `kos` (how many foes the move knocked
out, 0 for none), `effect: true|false`, and the user's `hp` (heal) or its `stage` in
the stat (stat). A priority boost's say `result: boosted|normal` and may set `hp`.
These three ports log the state that decides their outcome (`can_heal`, `hp_full`,
`stage`), and their checks select on it, because the harness scores the first
matching line. Validation refuses a probe that cannot happen: a heal from a Liquid
Ooze target, a heal at full HP, a raise past +6. `control` is a vanilla ability, by INTERNAL name,
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

**Blocks (NV-18).** A spec whose effects are several shapes lists them, one block
each, instead of one template. A block names the `effects` it generates and the
test `cases` its probes cover:

    template:
      - shape: type_immunity
        params: {type: Water}
        effects: [1]
        cases: [1]
        probes:
          - {move: Surf, immune: true}
      - shape: type_resist
        params: {type: Fire, multiplier: 0.5}
        effects: [2]
        cases: [2, 3]
        probes:
          - {move: Flamethrower, applies: true}
          - {move: Tackle, applies: false}

- **Coverage:** every effect and every test case belongs to exactly one block.
- **Registries:** each block is its own registry entry under the ability. Two
  blocks on one registry are refused.
- **Logging:** each block's log lines carry `block=<n>`, and its checks select it.
- **Kept effects:** a `keeps` block covers an effect the game's own ability already
  has (vanilla Immunity cannot be poisoned). Its probes show the port left it in
  place.
- **Mold Breaker:** a type immunity probe may set `mold_breaker: true`. The
  self-test's `defend` phase now goes through Nova's own `pbImmunityByAbility`, so
  the attacker's Mold Breaker lifts the immunity (Thermal Exchange).

A mechanic that fits no shape gets a hand-written `chrooked_<id>.rb` here. It must
register its own self-test case and have a scenario in `harness_scenarios.py`. A
spec with both a template and a file here is ambiguous, and apply blocks it. A new
shape starts the same way: hand-port one mechanic, prove it in the lab, then
generalise it (Forestry, NV-9).

## Composed abilities (NV-15)

A Ruleset ability may be built from parts, `behaviors: [carnivore, strongjaw]`:
Apex Predator is Carnivore's knockout heal plus Strong Jaw's biting boost. A part
is a Ruleset behavior with a generated port, or a vanilla ability the game ships.
Apply writes the composed ability its own file, `chrooked_<ability>.rb`
(`behavior/compose.py`), and the usual tooling treats it as one more port.

- **Wiring.** Essentials keys every battle effect by ability id in its registries,
  so the composed ability gets its parts' handlers. The wiring runs once, at the
  first `Battle.new`, when every port has loaded (the composed file sorts before
  `chrooked_carnivore.rb`), and logs `wired DamageCalcFromUser=strongjaw
  OnEndOfUsingMove=carnivore`.
- **Shared registries.** A registry one part uses gets that part's handler as it
  is. Parts sharing a registry are combined the way its trigger in
  `008_Battle_AbilityEffects.rb` reads the result:
  - `EACH` (damage multipliers, on-hit, on-knockout, on-entry) runs every part;
  - `THREAD` (speed, priority, move type, critical stage) passes the value
    through each part;
  - `ANY` (move and stat-loss immunity) is yes when any part says yes.

  Any other shared registry logs an ERROR and runs only the first part. Razor
  Edge (Sharpness + Tough Claws) and Serrated Jaw (Strong Jaw + Sharpness) prove
  `EACH`.
- **Logging.** While a part runs for the composed ability, its port's lines are
  re-tagged as the composed ability's, with `part=<id>`. AI calls stay `EST`.
- **By name (NV-16).** Some parts have no handler. The battle code asks
  `hasActiveAbility?(:LEVITATE)` instead (Levitate through `airborne?`, Guts in
  burn's halving, Scrappy in the type matchup, Suction Cups, Gorilla Tactics's
  lock). A composed battler answers yes for each of its parts as well, unless its
  ability is suppressed. The AI's `has_active_ability?` delegates to it, so it sees
  them too.
- **Proof.**
  - A ported part's own probes run under the composed ability, and its checks
    select `part=`.
  - A vanilla part gets `compare:` entries, `[move, part, kind, setup]`. One value
    is measured with the composed ability, with the part alone and with none; the
    first two must match, and the last must differ. The kinds:
    - `hit`: a hit's damage (Crunch: 41 with Apex Predator, 41 with Strong Jaw,
      28 with none; Tackle burned under Guts 22, 22, 7);
    - `airborne`: Levitate;
    - `forced_out`: Suction Cups;
    - `stat_drop`: Clear Body;
    - `locked`: Gorilla Tactics, locked into Tackle and unable to pick Growl;
    - `ko`: Moxie, Attack 0 to 1;
    - NV-17, measured as the foe's target or on a field: `speed` (Slush Rush in
      hail, 110 against 55), `immune` (Soundproof on Hyper Voice, Bulletproof on
      Shadow Ball), `crit_taken` (Battle Armor, -1), `switch_in` (Grassy Surge
      leaves Grassy Terrain), `hit_taken` (Grass Pelt on Grassy Terrain, 24
      against 36).
  - A part checked by name also gets an `identity:` entry: its holder's
    `hasActiveAbility?` must say yes for the part, alone and in a list, and no for
    Stench.
  - `VANILLA_PARTS` in `compose.py` holds each vanilla part's proofs.
- **Not composed yet** (the ability stays DATA ONLY, with no report line):
  - a vanilla part with no `VANILLA_PARTS` entry;
  - a Ruleset part with no template;
  - an ability that lists itself (Finishing Kick, Web Weaver, Unattainable,
    Thorned Succulent).
- **Blocked:** a target lacking a vanilla part, or its proof move.

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
| `010_battle_selftest.rb` | headless self-test: when `chrooked-selftest.on` names a mechanic, it runs a measured damage A/B (same battlers and RNG seed, with the ability, with none, with a control) and one AI-vs-AI battle in `Battle::DebugSceneNoVisuals`, then logs `DONE`. It measures the cases the installed ports registered in `$chrooked_selftest_cases`, so a new port needs no edit here; it loads before `998_ChrookedMods/` but reads the cases only when it fires, after every port has loaded. A CALC entry may carry a setup hash (`[move, hp, {weather:, terrain:, item:, airborne:, stats:, types:}]`), applied to the same battlers before every ability is measured (NV-9, NV-10); `:STRUGGLE` is built as a battle builds it. A `heal:` list (`[[:MOONLIGHT, 0.5]]`) measures what a healing move restores with the ability and without (HEAL lines, NV-10). A `chance:` list (`[[:CRUNCH, {status: :BURN, status_rate: 0.3, flinch_rate: 0.3}]]`) measures an on-hit chance: the damage A/B once, then the user's `OnDealingHit` handler fired 400 times on a fresh target with a fixed seed, the rates checked within 3 standard deviations (exactly 0 when 0 is expected) and logged as the mechanic's OBS line with `source=selftest` (NV-11). `setup:` may also set `target_types:`. A `defend:` list (`[:KNOCKOFF, :TAUNT]`) asks the ability's `MoveImmunity` handler about each move aimed at the holder, typed as used, and logs DEFEND lines; the port's own OBS line is what is scored (NV-13). Three more phases drive a registry directly and log what changed, the port's OBS line being scored (NV-14): `drain:` (`[[:TACKLE, {hp_lost: 100, target_ability: :LIQUIDOOZE}]]`) hands a hit that took `hp_lost` HP to `OnDealingHit` with the user at half HP (DRAIN lines); `ko:` (`[{kos: 1, hp: 0.5, stages: {SPECIAL_ATTACK: 6}}]`) ends the user's move with `kos` foes marked fainted for `OnEndOfUsingMove`, the one foe listed once per knockout and never really fainted, so the battle is not over (KO lines); `priority:` (`[[:FLAMETHROWER, 0.5]]`) asks `PriorityChange` at that HP fraction (PRIORITY lines). It builds `$PokemonSystem` among its throwaway globals when the game has not loaded it yet, because Nova's drain message reads the language from it. Safe to arm briefly on a played copy: saves point at `chrooked-selftest-saves/` while it runs, the globals it sets are restored, it runs once per process, and errors (Hangup included) are logged, never raised |

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
| `CHROOKED_ON_DEAL`, `CHROOKED_ON_DEAL_DMG` | `OnDealingHit` | **verified** 2026-10-22 (NV-11, NV-13, NV-14): called for the user's ability only after a hit that dealt damage and missed any substitute, with `target.damageState.hpLost` already set (the damage-aware `_DMG` table needs nothing more); Infernal Maw, Rimefang, Pyre, Scalding Pulse, Vampiric and Soul Siphon at PASS |
| `CHROOKED_WHEN_HIT`, `CHROOKED_WHEN_HIT_DMG` | `OnBeingHit` | candidate, unverified |
| `CHROOKED_SWITCH_IN` | `OnSwitchIn` | candidate, unverified |
| `CHROOKED_ON_KO` | `OnEndOfUsingMove` | **verified** 2026-10-22 (NV-14): called from `pbEffectsAfterMove` for the user's ability with the move's targets, whose damage states say which fainted (Nova's Moxie counts them); Carnivore and Hubris at PASS |
| `CHROOKED_TYPE_IMMUNITY` | `MoveImmunity` | **verified** 2026-10-22 (NV-13): asked from `Battle::Move#pbImmunityByAbility` for every move aimed at the holder, typed as used, unless Mold Breaker; Nocturnal and Winter Coat at PASS |
| `CHROOKED_SURE_HIT`, `CHROOKED_ACCURACY_MODS` | `AccuracyCalcFromUser` | candidate, unverified |
| `CHROOKED_PRIORITY_MODS` | `PriorityChange` | **verified** 2026-10-22 (NV-14): asked by `pbCalculatePriority` for each battler's chosen move while its ability is active, and by the AI (`AIMove`); Rapid Combustion at PASS |
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
- *Composition:* **resolved 2026-10-22 (NV-15)**, above. Not yet composed:
  finishingkick, which lists itself (`behaviors: [finishingkick, speedboost]`),
  and the compositions whose parts have no proof yet.
- *Every other table* above, and the 25 Nova abilities with no Rejuvenation port.

## Ported mechanics

61 ports and 13 compositions. 51 ports are generated from their specs' `template:` blocks: 22 since
2026-10-22 (NV-8), four more (NV-9), two more (NV-10), six more (NV-13) and five
more (NV-14) the same day. NV-13's three new shapes were each hand-ported and proven
first (Pyre, Nocturnal, Arctic Ariette), then generated with the same code apart
from two message strings, which now use Nova's own. NV-14's were too (Vampiric,
Carnivore, Rapid Combustion), the generated code differing only in writing a
quarter as `* 0.25`. Ten are hand-written here:
- `chrooked_fullmoon.rb` and `chrooked_highnoon.rb` (NV-10) and
  `chrooked_infernalmaw.rb` (NV-11), because each has more than one effect;
- `chrooked_rimefang.rb` (NV-12), for the same reason;
- `chrooked_dilation.rb`, `chrooked_dualaegis.rb`, `chrooked_waterveil.rb`,
  `chrooked_selfsufficient.rb`, `chrooked_heavyfumes.rb` (NV-21), entry and end-of-round
  effects each unique to its ability, proven by the self-test's `entry` and `eor`
  scenes;
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
| frostbite (hand-written; a status) | freeze reskinned, keeping `:FROZEN`. No lost turns or random thaw (`pbTryUseMove` with `@status` cleared around it, as Rejuvenation's port does; also the multi-hit cut-off and the AI's `can_attack?`). Special damage halved unless Guts or Quick Feet (beside burn's halving). A 1/16 end-of-round chip unless Magic Guard (after burn's chip). Cured by any Fire-type move or a move that thaws its user (Chris, 2026-10-22). Its text and name say frostbite | NV-12, lab 9/9: 50 of 50 turns acted, never cured; Surf 12 vs 24; Tackle, Guts and Quick Feet unchanged; chip 8 of 135 HP, Magic Guard 0; Ember, Flame Wheel and Scald cure (any Fire move, or a move that thaws its user), Tackle does not; Ice-types immune. Kept from Nova (the spec is silent): a Fire hit cures the target, harsh sun prevents it, the catch bonus, the FRZ icon, Pursuit's skip |
| rimefang (hand-written) | Infernal Maw's build with frostbite (`pbCanFreeze?`/`pbFreeze`) in place of burn | NV-12, lab 3/3: frostbite 0.308 and flinch 0.305 over 400 rolls; Ice-type 0 frostbite, flinch 0.300; Tackle 0 and 0; Crunch 36 vs 28 |
| infernalmaw (hand-written) | 1.3x on `Biting` (Strong Jaw's shape), plus a 30% burn and an independent 30% flinch in `OnDealingHit` (Poison Touch's shape and gates) | NV-11, lab 3/3. Crunch 36 vs 28 (Strong Jaw control 41); 400 rolls each: burn 0.308 and flinch 0.305 on a burnable target; on a Fire-type 0 burns and flinch 0.300; Tackle 0 and 0 |
| pyre, scaldingpulse | `hit_status`, 30% burn, on Ghost moves / on `Pulse` moves | NV-13, lab 3/3 each, 400 rolls: Shadow Ball (Pyre) and Dragon Pulse (Scalding Pulse) burn 0.300; on a Fire-type 0; Flamethrower (Pyre) and Tackle (Scalding Pulse) 0. No damage change |
| nocturnal, wintercoat | `type_immunity`, Dark / Ice | NV-13, lab 3/3 each: Knock Off and Taunt (Dark, a status move) IMMUNE, Shadow Ball NORMAL; Blizzard, Freeze-Dry and Icicle Crash IMMUNE |
| arcticariette, sacredtoll | `type_conversion` on `Sound`: Ice 1.3x from Normal / Psychic 1.2x from any type, control Aerilate | NV-13, lab 3/3 each. Arctic Ariette: Hyper Voice turns Ice, 32 vs 24 (a small hit; Aerilate 30); Bug Buzz and Body Slam unchanged. Sacred Toll: Hyper Voice and Bug Buzz turn Psychic, 30 vs 24 (1.250x, equal to Aerilate on Hyper Voice); Tackle unchanged. Sacred Toll's Dark-target case is checked as the conversion to Psychic; the 0x itself was not measured (neutral foe) |
| vampiric, soulsiphon | `hit_drain`, 1/4 of the damage, on contact / non-contact moves | NV-14, lab 3/3 each: a 100-HP hit heals 25 (67 to 92 of 135) on Tackle (Vampiric) and Water Gun (Soul Siphon), 0 on the other move, and costs 25 against a Liquid Ooze target |
| carnivore, hubris | `ko_effect`, heal 1/4 / Sp. Atk per knockout | NV-14, lab 3/3 each. Carnivore: a knockout at half HP heals 33 (67 to 100 of 135); no knockout or full HP, nothing. Hubris: Sp. Atk +1 for one knockout, +2 for two, nothing at +6 |
| rapidcombustion | `priority_boost`, Fire, `full_hp` | NV-14, lab 3/3: Flamethrower priority 0 to 1 at full HP, 0 at half HP; Surf 0 |
| wingspan, liquidvoice, hydrophyte (blocks) | Ground immunity + `flag_boost` wing/wind 1.3x / `type_conversion` of sound moves to Water at 1.3x (one block, both effects) / Water immunity + `type_resist` Fire 0.5 | NV-18, lab 3/3, 2/2, 3/3: Earthquake immune, Hurricane 1.300x, Tackle 1.000x; Hyper Voice turns Water 32 vs 24, Surf unchanged; Surf immune, Flamethrower taken 24 vs 48, Tackle 36 vs 36 |
| liquified, virtualized, stonebark, flytrap (blocks) | `damage_taken` contact 1/2 + Water 2 / contact 1/3 + Dark 2 / `type_absorb` Grass heal + Water 1.25 / `type_absorb` Bug, Attack and Sp. Atk | NV-20, lab 3/3, 4/4, 3/3, 3/3: Close Combat taken 0.500 / 0.337, Scald and Dark Pulse 2.000, Liquidation 1.000, Crunch 0.671; Energy Ball heals Stonebark, Surf 1.250; Bug Buzz raises Flytrap, not at +6 |
| dilation, dualaegis, waterveil (hand-written) | `OnSwitchIn`: Trick Room toggle / Reflect and Light Screen / Aqua Ring beside Nova's own Water Veil | NV-21, lab 2/2, 3/3, 5/5 (entry scene): Trick Room 5 from calm, 0 when up; screens 5 and 5, Reflect left at 3, 8 and 8 with Light Clay; Aqua Ring on entry, not twice, the move then fails, still cannot be burned |
| selfsufficient, heavyfumes (hand-written) | `EndOfRoundHealing` 1/16 at least 1 / `EndOfRoundEffect` foes 1/16 (Bad Dreams' shape) | NV-21, lab 4/4 each (eor scene): +8 of 135, 0 at full, +1 at 12 max HP, +16 with Leftovers; a Normal foe -14 of 235, Poison and Magic Guard 0, -14 through a Substitute |
| venomous, frostbody (blocks) | `struck_status` + `hit_status` gated on contact; poison / frostbite, 30% | NV-19, lab 3/3, 4/4: 30% both ways over 400 rolls; never on Water Gun; never on an Ice-type. Cold Snap (Tough Claws + Frost Body) composes, 5/5 |
| immunity, poisonheal, thermalexchange (blocks) | `keeps` + Poison immunity / `keeps` + Poison immunity / Fire immunity + `keeps` | NV-18, lab 3/3 each: Sludge Bomb and Toxic immune; Immunity still cannot be poisoned; Poison Heal +16 HP at end of round (none -16); Thermal Exchange still cannot be burned, and an attacker's Mold Breaker lifts its Fire immunity |
| apexpredator (composed) | Carnivore + Strong Jaw | NV-15, lab 4/4: Carnivore's three knockout cases, re-tagged (67 to 100 HP); Crunch 41, as Strong Jaw alone (none 28) |
| serratedjaw, razoredge (composed) | Strong Jaw + Sharpness / Sharpness + Tough Claws, sharing `DamageCalcFromUser` | NV-15, lab 2/2 each: Crunch 41 as Strong Jaw alone, Air Slash 31 as Sharpness alone (none 21), Tackle 19 as Tough Claws alone (none 14) |
| requiem (composed) | Pyre + Spectralize | NV-15, lab 6/6: Pyre's burn rates and Spectralize's conversion, each scored on its re-tagged lines |
| witchinghour, kickboxer (composed) | Nocturnal + Levitate / Striker + Scrappy | NV-16, lab 5/5 each: the part's own probes, plus airborne (true, true, false) / Tackle on a Ghost 14, 14, 1, and identity |
| gyroscope, brawlersspirit, compulsion (composed) | Clear Body + Suction Cups / Guts + Moxie / Gorilla Tactics | NV-16, lab 3/3 each: Attack not lowered and not forced out; a burned Tackle 22 as Guts alone (7 with none) and Attack +1 on a knockout; Tackle 22 (14) and locked into it; identity for Suction Cups, Guts and Gorilla Tactics |
| iceskater, heavilyarmored, breadbasket (composed) | Winter Coat + Slush Rush / Soundproof + Bulletproof + Battle Armor / Grassy Surge + Grass Pelt | NV-17, lab 4/4, 4/4, 2/2: Winter Coat's probes and Speed 110 in hail (55); Hyper Voice and Shadow Ball blocked through one `MoveImmunity` (`ANY`), crit stage -1, identity for Soundproof; Grassy Terrain on entry and Tackle taken 24 (36) |
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
Frostbite and Rimefang (NV-12) followed: 9/9 and 3/3, then frostbite again 9/9
after the any-Fire-move cure, every line identical to the lab's. All 33 are proven
on thor. The six NV-13 ports followed in one boot: 18/18, all 18 measurement lines
identical to the lab's, the first device runs of a generated status chance and of
the `defend` phase. The five NV-14 ports followed in one boot: 15/15, all 15 DRAIN,
KO and PRIORITY lines identical to the lab's (the AI battle's turn counts are not a
measurement: it is not reseeded, so they depend on what ran before it). All 44 are
proven on thor. The four NV-15 compositions followed: 14/14, their wiring and all
their measurement lines identical to the lab's (the game booted twice before the
read, and both runs matched line for line). All 48 are proven on thor. The five
NV-16 compositions (and the four, rebuilt with the by-name answer) wait for a boot.

The CALC phase sets both battlers to the `???` type (`neutral: true`), so the ratio
is the ability alone: no same-type bonus, no type matchups.

A spec case about a Pokémon **without** the ability cannot be logged by an
Essentials 21 port, which only ever runs for its holder. The self-test's
`without:` moves measure it instead: the holder, a Stench holder (no damage
effect) and no ability, on the same battlers. The result is logged as the
mechanic's `OBS` line, tagged `source=selftest`. A scenario `select` may list
several move names (`["HIJUMPKICK", "HIGHJUMPKICK"]`) for moves 16.2 and
Essentials 21 name differently.
