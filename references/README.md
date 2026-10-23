# Reference implementations

Per-engine, per-version implementations of Ruleset **behaviors** — the engine-specific output
of porting a [behavior spec](../ruleset/behaviors/) into a real target. The Ruleset itself
stays engine-neutral.

They are a **growing library**: the first time a mechanic is implemented for an engine, its
port is captured here. The next time that engine is targeted, the port is near-mechanical
reuse instead of a fresh derivation.

Two storage models, because the engines differ:

- **pokeemerald** edits existing C in place, so a port is a **`.patch`** applied with `git apply`.
- **Essentials 16.2** adds a standalone Ruby plugin file, so a port is a **plugin** living under
  `essentials-harness/chrooked_<id>.rb`. `chrooked-pokedex apply --engine essentials` **installs**
  it (copies it into the target's `Scripts/`) and flips that mechanic's `DATA ONLY` report line to
  "mechanic installed" (issue #16). No `.patch` for Essentials — the plugin is additive, not a diff.
- **Essentials 21** also adds a standalone Ruby file, but it registers one entry in an Essentials 21
  handler registry instead of wrapping a method, and `apply --engine essentials` installs it into the
  target's `Data/Scripts/998_ChrookedMods/` (mjolnir NV-5). A mechanic in a proven shape has no file
  here: apply generates its port from the `template:` block in its behavior spec (mjolnir NV-8).
  Only a mechanic that fits no shape is captured as `essentials21-harness/chrooked_<id>.rb`. See
  `essentials21-harness/README.md`.

## Naming

- pokeemerald: `<chrooked_id>.pokeemerald-expansion-<version>.patch` (`git apply` from the fork root).
- essentials 16.2: `essentials-harness/chrooked_<chrooked_id>.rb` (installed on `apply --engine essentials`).
- essentials 21: a `template:` block in `ruleset/behaviors/<chrooked_id>.yaml` (generated on
  `apply --engine essentials`), or, for a mechanic no template fits,
  `essentials21-harness/chrooked_<chrooked_id>.rb` (installed on `apply --engine essentials`).

## How each was produced

The behavior-port loop (see `.claude/skills/port-behavior/SKILL.md`):

1. `chrooked-pokedex behaviors --mechanic <id> --engine <engine>` emits a self-contained packet.
2. A behavior-port agent implements it into a clean target **from the packet only**.
3. It is verified against the spec's acceptance tests: pokeemerald runs its battle test RED→GREEN;
   Essentials runs the log-oracle harness (`harness stage|verify <id>`, one human-played battle).
4. The port is captured here (a `.patch` for pokeemerald; a plugin under `essentials-harness/` for
   Essentials).

## Inventory

| mechanic | engine | storage | verified |
| --- | --- | --- | --- |
| innerfocus | pokeemerald-expansion 1.15.3 | `.patch` | `make check` RED→GREEN (battle test) + compiles |
| innerfocus | essentials 16.2 (Africanvs) | `essentials-harness/` plugin (installed on apply) | harness `verify innerfocus` 3/3 (log oracle) |
| kindle | essentials 16.2 (Africanvs) | `essentials-harness/` plugin (installed on apply) | harness `verify kindle` 3/3 (log oracle); Seam `pbModifyDamage` |
| kindle | essentials 21.99 (Pokémon Nova V3.0) | spec `template:` (`type_boost`), generated on apply into `Data/Scripts/998_ChrookedMods/` (NV-8; a hand port before) | `scripts/nova_selftest.sh kindle` 3/3, headless (AI vs AI); damage A/B Flamethrower 1.500x, Surf 1.000x; Seam `DamageCalcFromUser`. On thor (Kirin 0.3.5): the hand port 3/3, then the generated port 3/3 with the NV-8 batch, same numbers as the lab both times |
| bloom, cryomancer, deluge, overcharge | essentials 21.99 (Pokémon Nova V3.0) | spec `template:` (`type_boost`), generated on apply (NV-8); first translated from `rejuv-harness/` | `scripts/nova_selftest.sh` 3/3 each, lab, and on thor in the NV-8 batch (`nova_thor_selftest.sh`, same numbers); Seam `DamageCalcFromUser` |
| hammerfist, impale, martialartist, sledgehammer, striker | essentials 21.99 (Pokémon Nova V3.0) | spec `template:` (`flag_boost`) on the `Kicking` / `Hammer` / `Piercing` flags the dex writes (NV-7), generated on apply (NV-8) | `scripts/nova_selftest.sh` 3/3 each, lab, and on thor in the NV-8 batch (`nova_thor_selftest.sh`, same numbers); Seam `DamageCalcFromUser`, as Nova's Iron Fist |
| forestry, downpour, whiteout | essentials 21.99 (Pokémon Nova V3.0) | spec `template:` (`conditional_boost`), generated on apply (NV-9); Forestry hand-ported and proven first | `scripts/nova_selftest.sh` lab: forestry 3/3, downpour 4/4, whiteout 3/3; thor the same (NV-9 batch, identical numbers); Seam `DamageCalcFromUser`, as Nova's Sand Force (terrain, all moves) and Solar Power (weather, higher attacking stat) |
| mysticpower, violentblood | essentials 21.99 (Pokémon Nova V3.0) | spec `template:` (`stab_grant`), generated on apply (NV-10) | `scripts/nova_selftest.sh` 3/3 each, lab; Seam `DamageCalcFromUser`, the same final-damage 1.5x as Nova's own STAB, only when the user lacks the type |
| fullmoon, highnoon | essentials 21.99 (Pokémon Nova V3.0) | `essentials21-harness/` hand ports (NV-10): two effects each, a STAB grant plus a 3/4 heal on Moonlight / Morning Sun | `scripts/nova_selftest.sh` 3/3 each, lab (heal phase: 101 of 135 HP at half HP); Seams `DamageCalcFromUser` and `HealUserDependingOnWeather#pbOnStartUse` |
| frostbite | essentials 21.99 (Pokémon Nova V3.0) | `essentials21-harness/` hand port (NV-12): a status, freeze reskinned as the Ruleset's frostbite (method wrappers) | `scripts/nova_selftest.sh` 9/9, lab: no lost turns, special damage halved (Guts and Quick Feet exempt), 1/16 chip (Magic Guard exempt), thaw-flag moves cure, Ice immune |
| rimefang | essentials 21.99 (Pokémon Nova V3.0) | `essentials21-harness/` hand port (NV-12): Infernal Maw's build with frostbite | `scripts/nova_selftest.sh` 3/3, lab; Seams `DamageCalcFromUser` and `OnDealingHit` |
| infernalmaw | essentials 21.99 (Pokémon Nova V3.0) | `essentials21-harness/` hand port (NV-11): three effects, a 1.3x biting boost plus 30% burn and 30% flinch on hit | `scripts/nova_selftest.sh` 3/3, lab: rates over 400 rolls within 3 sigma (burn 0.308, flinch 0.305; Fire-type 0 burns); Seams `DamageCalcFromUser` and `OnDealingHit` |
| pyre, scaldingpulse | essentials 21.99 (Pokémon Nova V3.0) | spec `template:` (`hit_status`), generated on apply (NV-13); Pyre hand-ported and proven first | `scripts/nova_selftest.sh` 3/3 each, lab: burn 0.300 over 400 rolls on Ghost / Pulse hits, 0 on a Fire-type and on other moves; thor the same (NV-13 batch, identical lines); Seam `OnDealingHit`, as Nova's Poison Touch |
| nocturnal, wintercoat | essentials 21.99 (Pokémon Nova V3.0) | spec `template:` (`type_immunity`), generated on apply (NV-13); Nocturnal hand-ported and proven first | `scripts/nova_selftest.sh` 3/3 each, lab (defend phase): Dark / Ice moves IMMUNE, status moves included; thor the same (NV-13 batch, identical lines); Seam `MoveImmunity`, as Nova's Bulletproof |
| arcticariette, sacredtoll | essentials 21.99 (Pokémon Nova V3.0) | spec `template:` (`type_conversion` with `flags: [sound]`; Sacred Toll `from: any`), generated on apply (NV-13); Arctic Ariette hand-ported and proven first | `scripts/nova_selftest.sh` 3/3 each, lab: sound moves turn Ice / Psychic with the rider, others unchanged; thor the same (NV-13 batch, identical lines); Seams `ModifyMoveBaseType` and `DamageCalcFromUser`, as Nova's Aerilate |
| vampiric, soulsiphon | essentials 21.99 (Pokémon Nova V3.0) | spec `template:` (`hit_drain`), generated on apply (NV-14); Vampiric hand-ported and proven first | `scripts/nova_selftest.sh` 3/3 each, lab (drain phase): 25 of a 100-HP hit healed on contact / non-contact moves, 0 on the other kind, -25 against Liquid Ooze; Seam `OnDealingHit`, through Nova's drain path |
| carnivore, hubris | essentials 21.99 (Pokémon Nova V3.0) | spec `template:` (`ko_effect`), generated on apply (NV-14); Carnivore hand-ported and proven first | `scripts/nova_selftest.sh` 3/3 each, lab (ko phase): a knockout heals 1/4 below full HP / raises Sp. Atk one stage per knockout, capped at +6; Seam `OnEndOfUsingMove`, as Nova's Moxie |
| rapidcombustion | essentials 21.99 (Pokémon Nova V3.0) | spec `template:` (`priority_boost`), generated on apply (NV-14); hand-ported and proven first | `scripts/nova_selftest.sh` 3/3, lab (priority phase): Fire moves +1 at full HP only; Seam `PriorityChange`, as Nova's Gale Wings |
| updraft | essentials 21.99 (Pokémon Nova V3.0) | spec `template:` (`flag_boost`) on the `Wing` flag the dex writes (NV-9) and Nova's own `Wind` | `scripts/nova_selftest.sh` 3/3, lab, and on thor in the NV-9 batch (same numbers); Seam `DamageCalcFromUser`, as Nova's Iron Fist |
| chitinize, foliate, hydrate, immolate, martialize, mineralize, obfuscate, psyonize, spectralize, tectonize, venomize, wyvernize | essentials 21.99 (Pokémon Nova V3.0) | spec `template:` (`type_conversion`), generated on apply (NV-8); first translated from `rejuv-harness/` `register_ize` | `scripts/nova_selftest.sh` 3/3 each, lab, and on thor in the NV-8 batch (`nova_thor_selftest.sh`, same numbers); Seam `ModifyMoveBaseType` + `DamageCalcFromUser`, as Nova's Aerilate |
| soulsight | rejuv (Rejuvenation) | `rejuv-harness/` mod (installed on apply) | `ruby rejuv-harness/soulsight_check.rb` 20/20, RED 9/20 without the mechanic |
| percussion | rejuv (Rejuvenation) | `rejuv-harness/` mod (installed on apply) | `ruby rejuv-harness/percussion_check.rb` 16/16, RED 11/16 without the mechanic |
| finishingkick | rejuv (Rejuvenation) | `rejuv-harness/` mod (installed on apply); contact clause only, Speed Boost half via `behaviors: [finishingkick, speedboost]` composition | `ruby rejuv-harness/finishingkick_check.rb` 6/6, RED (nil handler) without the mechanic |
| sandguard | rejuv (Rejuvenation) | `rejuv-harness/` mod (installed on apply); new `CHROOKED_WEATHER_IMMUNE` table + `takesWeatherDamage?` wrapper in the core | static review only (no ruby harness); syntax OK in ruby:3.3; human plays one sand battle |
| thornedsucculent | rejuv (Rejuvenation) | composed `behaviors: [thornedsucculent, waterabsorb, ironbarbs]` (vanilla parts via `chrooked_zz_zcompose.rb`); own plugin carries only `CHROOKED_WEATHER_IMMUNE` sand clause | syntax OK in ruby:3.3; composition row confirmed in the generated compose mod; human plays one battle |

### innerfocus.pokeemerald-expansion-1.15.3

- **Seam:** `CanMoveSkipAccuracyCalc` in `src/battle_util.c` — 1.15.3's dedicated predicate
  for every "always hit" condition.
- **Note:** the agent chose this Seam over the sibling reference fork's older inline
  `return TRUE` in `GetTotalAccuracy`, by reading the 1.15.3 engine. The dumb patch-apply
  would have been wrong; the spec + engine knowledge produced a *better* port.
- Gated on the attacker's own `ABILITY_INNER_FOCUS` and `MOVE_FOCUS_BLAST` only, so it does
  not leak to other moves or to non-Inner-Focus users, and Mold Breaker (a target-bypass)
  cannot suppress it.
- **Battle test:** `test/battle/ability/inner_focus.c` gains three `SINGLE_BATTLE_TEST`s.
  The discriminator — *"Inner Focus makes the user's Focus Blast always hit"* — uses
  `PASSES_RANDOMLY(100, 100, RNG_ACCURACY)` on a 70%-base move. On the clean engine it
  failed at the true `0.69` hit rate; with the mechanic it passes 100/100. The other two
  assert the bypass does not leak to other moves or non-Inner-Focus users.

### innerfocus.essentials-16.2 (+ kindle)

- **Code home:** standalone Ruby plugins `essentials-harness/chrooked_innerfocus.rb` and
  `essentials-harness/chrooked_kindle.rb`, installed into the target's `Scripts/` by
  `apply --engine essentials` (issue #16), and auto-loaded by `load_order_shim.rb` (preloaded via
  `mkxp.json` → `preloadScript`; the shim globs `chrooked_*.rb`). NOT a `Scripts.rxdata` repack.
  kindle's Seam is `PokeBattle_Move#pbModifyDamage` (1.5× Fire, Blaze sans HP check).
- **Seam:** `PokeBattle_Move#pbAccuracyCheck(attacker, opponent)` in 16.2's
  `084_PokeBattle_Move`. NOTE: the spec's engine hint named `Battle::Move` — that is the
  modern (v19+/v21) class; 16.2 is `PokeBattle_Move`. Verified against the extracted scripts,
  not the hint.
- The plugin overrides `pbAccuracyCheck` to `return true` (always-hit, the engine's `:NOGUARD`
  convention) only when `attacker.hasWorkingAbility(:INNERFOCUS)` AND
  `isConst?(@id, PBMoves, :FOCUSBLAST)`, else it calls the original. It does NOT touch vanilla
  Inner Focus no-flinch, which lives in `PokeBattle_Battler#pbFlinch` (083) and already works.
- **Ruby 1.8 (no `prepend`, no `TracePoint`):** the override uses `alias_method` chaining, and the
  install is deferred via a one-shot hung on the native `Graphics.update` (the shim preloads BEFORE
  `Scripts.rxdata` defines the class; `Graphics` exists at preload and runs every frame, so the
  installer fires once the class appears, then flags itself done).
- **`STDERR` is a bad file descriptor** under the console-suppressed Wine build — all logging goes to
  a guarded `Scripts/chrooked_load.log`.
- **Verification (logfile oracle):** boot `scripts/africanvs_devloop.sh --no-apply`, confirm
  `[LOAD_ORDER_SHIM] active` + `installed on PokeBattle_Move` in the log. In-game evasion setup is
  impractical, so the plugin logs the gate decision per Focus Blast cast. Proven: Lucario (Inner
  Focus) ×3 → `ALWAYS-HIT`; Pidgeotto (no Inner Focus) ×3 → `normal accuracy`. The move-id gate
  structurally excludes the user's other moves.
