# Reference implementations

Per-engine, per-version implementations of Ruleset **behaviors**. The Ruleset itself stays
engine-neutral; these `.patch` files are the engine-specific output of porting a
[behavior spec](../ruleset/behaviors/) into a real target.

They are a **growing library**: the first time a mechanic is implemented for an engine, the
diff is captured here. The next time that engine is targeted, the port is near-mechanical
reuse instead of a fresh derivation.

## Naming

`<chrooked_id>.<engine>-<version>.patch` — e.g. `innerfocus.pokeemerald-expansion-1.15.3.patch`.

Apply with `git apply <file>` from the target fork's root (the path is relative to repo root).

## How each was produced

The behavior-port loop:

1. `chrooked-pokedex behaviors --mechanic <id> --engine <engine>` emits a self-contained packet.
2. A behavior-port agent implements it into a clean target **from the packet only**.
3. The edit is static-verified against the spec's acceptance tests and compiled.
4. The diff is captured here.

A reference patch carries BOTH the mechanic edit AND, for pokeemerald, its battle test —
the executable form of the spec's acceptance cases. Verification is RED→GREEN: the test
fails on the clean engine (proving it exercises the mechanic), then passes once the mechanic
is applied.

## Inventory

| mechanic | engine | verified |
| --- | --- | --- |
| innerfocus | pokeemerald-expansion 1.15.3 | `make check` RED→GREEN (battle test) + compiles |
| innerfocus | essentials 16.2 (Africanvs) | in-game (Wine debug) — logfile gate-decision oracle; loads + fires correctly |

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

### innerfocus.essentials-16.2

- **Code home:** a loose external Ruby plugin, `Scripts/chrooked_innerfocus.rb`, loaded by the
  Africanvs copy's `load_order_shim.rb` (preloaded via `mkxp.json` → `preloadScript`). NOT a
  `Scripts.rxdata` repack — the patch is plain text, mirroring the pokeemerald cache model.
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
