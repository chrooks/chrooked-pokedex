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

## Naming

- pokeemerald: `<chrooked_id>.pokeemerald-expansion-<version>.patch` (`git apply` from the fork root).
- essentials 16.2: `essentials-harness/chrooked_<chrooked_id>.rb` (installed on `apply --engine essentials`).

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
| soulsight | rejuv (Rejuvenation) | `rejuv-harness/` mod (installed on apply) | `ruby rejuv-harness/soulsight_check.rb` 20/20, RED 9/20 without the mechanic |
| percussion | rejuv (Rejuvenation) | `rejuv-harness/` mod (installed on apply) | `ruby rejuv-harness/percussion_check.rb` 16/16, RED 11/16 without the mechanic |

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
