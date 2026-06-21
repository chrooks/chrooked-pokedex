# Port the innerfocus mechanic into Africanvs end-to-end (Essentials behavior tracer)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository keeps its ExecPlan format guide at `~/.claude/PLAN.md`. This document must be maintained in accordance with that guide.

## Purpose / Big Picture

Today the tool can write Pokémon **data** into the Essentials game Africanvs — a species' types, stats, abilities, moves, learnset, evolutions, type-chart — and it can do this faithfully. What it cannot do is make a **custom mechanic actually happen in battle**. When the Ruleset says an ability has a behavior the engine does not already have, the applier creates the ability's data row and prints a loud `DATA ONLY: implement mechanic` warning, then stops. The behavior is engine code (for Essentials, Ruby), and engine code cannot travel as data.

The completed pokeemerald track solved this with a "spec → port → verify" loop: a neutral behavior spec is rendered into a self-contained implementation packet, an agent ports it into the engine, the port is checked against the spec's acceptance tests, and the resulting diff is captured as a reusable reference patch. This ExecPlan does the **first end-to-end port for Essentials** — a tracer. After it, a person can run one command, hand an agent the innerfocus packet, watch a `# chrooked:innerfocus` Ruby plugin appear in the Africanvs copy, boot the game in the Wine debug build, fight a debug battle, and see the custom effect fire — the user's Focus Blast always hits — while the vanilla Inner Focus no-flinch behavior keeps working untouched.

The mechanic we port, **innerfocus**, is chosen on purpose. It is the only behavior spec that already carries an Essentials engine hint (`Battle::Move#pbAccuracyCheck`) and already has a proven pokeemerald twin, so if the Essentials port misbehaves we know the fault is in the new Essentials path, not in the spec. Its custom effect ("the user's Focus Blast never misses") is observable as a clean yes/no — a foe at +6 evasion either gets hit or does not — which matters because Essentials has no automated test harness and a human is the test oracle for this tracer.

"Tracer" means a thin slice that proves the whole path works end-to-end before we widen it. After this plan, [#15](https://github.com/chrooks/chrooked-pokedex/issues/15) attempts a headless Ruby battle harness for real automated RED→GREEN, and [#16](https://github.com/chrooks/chrooked-pokedex/issues/16) drives the loop across more mechanics and flips the `DATA ONLY` boundary so the applier can point at a resolvable port.

## Progress

- [x] (2026-06-21) M0 — Load path CONFIRMED. `mkxp.json` was MISSING; authored it. Boot log shows `[LOAD_ORDER_SHIM] active` + `[chrooked:innerfocus] installed on PokeBattle_Move`. The preload→shim→plugin→deferred-install path works on the real Wine build.
- [x] (2026-06-21) M1 — `Scripts/chrooked_innerfocus.rb` against the REAL extracted 16.2 API (`PokeBattle_Move#pbAccuracyCheck`, gated on `:INNERFOCUS` + `:FOCUSBLAST`). Rewritten Ruby-1.8-safe: `alias_method` chaining (no `prepend`) + `Graphics.update` one-shot deferral (no `TracePoint`). Vanilla no-flinch (`pbFlinch`, 083) untouched.
- [x] (2026-06-21) M2 — Verified via log oracle (in-game evasion setup was impractical). Lucario(Inner Focus) Focus Blast ×3 → `ALWAYS-HIT`; Pidgeotto(no Inner Focus) Focus Blast ×3 → `normal accuracy`. Gate honors the ability; move-id gate excludes other moves.
- [x] (2026-06-21) M3 — Captured `references/innerfocus.essentials-16.2.patch` (`git apply --check` OK), README row + note, extended the `port-behavior` SKILL's Essentials arm with code-home + version-string + the 16.2 gotchas.

## Surprises & Discoveries

- Observation: The autoload question (does the 32-bit Wine mkxp-z build honor an external `Scripts/` directory?) was already partly tackled by the `africanvs-dev-loop` work.
  Evidence: `feature_requests/africanvs-dev-loop-throughline.md` records that an `mkxp.json` (`preloadScript`) plus `Scripts/load_order_shim.rb` were placed in the external game copy, and that the check is to look for `[LOAD_ORDER_SHIM] active` on first debug boot — left as NEEDS-HUMAN. This plan turns that open check into M0.

- Observation: `mkxp.json` was MISSING from the current copy — only the shim + `load_order.txt` survived. The preload path was unwired.
  Evidence: `ls` of the copy root showed no `mkxp.json`; `Game.ini` is stock `Library=RGSS104E.dll`. Authored a fresh `mkxp.json` with `preloadScript: ["Scripts/load_order_shim.rb"]`. M0 still needs a human boot to confirm this 32-bit Wine build honors it.

- Observation: The spec's Essentials engine hint named the WRONG class for 16.2.
  Evidence: the hint says `Battle::Move#pbAccuracyCheck` (modern v19+/v21), but extracting `Data/Scripts.rxdata` (228 scripts, Marshal + Zlib) showed the 16.2 method is `PokeBattle_Move#pbAccuracyCheck(attacker,opponent)` in `084_PokeBattle_Move.rb:490`. Verified `FOCUSBLAST` (moves.txt id 87, base acc 70) and `INNERFOCUS` (abilities.txt id 39) both exist, and vanilla no-flinch is `PokeBattle_Battler#pbFlinch` (083:733). The port was written against ground truth, not the hint.

- Observation: The preload shim loads scripts BEFORE the engine class exists, so a plain alias/prepend fails or gets clobbered.
  Evidence: `load_order_shim.rb` runs at mkxp-z `preloadScript` time, before `Scripts.rxdata`. The plugin installs lazily once `PokeBattle_Move` is defined.

- Observation: The engine is Ruby 1.8 — `Module#prepend` AND `TracePoint` are BOTH Ruby 2.0+ and do not exist here. First boot crashed on `STDERR` (EBADF, console suppressed); second on `uninitialized constant TracePoint`.
  Evidence: dialog "uninitialized constant TracePoint"; `docs/africanvs-dev-loop.md:10` ("Wine Game.exe bundles Ruby 1.8"). Fix: override via `alias_method` chaining; defer via a one-shot installer hung on the native `Graphics.update` (defined at preload, called every frame, and Essentials' own `Graphics.update` aliases chain so our hook survives). All STDERR writes routed to a guarded logfile (`Scripts/chrooked_load.log`).

- Observation: In-game it is impractical to set a foe to +6 evasion, and Focus Blast's 70% accuracy makes raw hit-counts an unreliable oracle (a no-Inner-Focus mon hitting 5/5 has ~17% odds).
  Evidence: Chris reported both a Lucario (Inner Focus) and a Pidgeotto (no Inner Focus) hitting 5/5. Resolution: made the plugin log the gate decision per Focus Blast cast. The log then read cleanly — Lucario ×3 `ALWAYS-HIT`, Pidgeotto ×3 `normal accuracy` — settling it deterministically without evasion control. Diagnostic logging then trimmed to a fire-only line.

## Decision Log

- Decision: Ported mechanics live as external `# chrooked:<id>` plugin `.rb` files, captured as text patches; never hand-edit the binary `Scripts.rxdata`.
  Rationale: Only option that preserves the proven text-patch/cache architecture from pokeemerald and is forward-compatible with Essentials v21's native `Plugins/` autoload. The known risk — the Wine build not autoloading external scripts — is exactly what M0 settles; fall back to the PBS-FunctionCode + Ruby-handler hybrid only if autoload genuinely fails.
  Date/Author: 2026-06-21 / grill (#12 throughline Q1)

- Decision: The tracer gates on a manual playtest checklist, honestly labeled; automated RED→GREEN is deferred to #15.
  Rationale: The tracer proves the *port path*, not a test runner. Essentials has no built-in harness, and the project's honesty stance forbids claiming runtime verification we did not run. A human runs the numbered test_cases in the debug battle. The first mechanic is simple enough to eyeball.
  Date/Author: 2026-06-21 / grill (#12 throughline Q2)

- Decision: The first tracer mechanic is `innerfocus`.
  Rationale: Only mechanic with an Essentials engine hint already written and a proven pokeemerald twin, so failures isolate to the path not the spec; binary hit/miss oracle; the intentional vanilla overlap proves the agent ports only the custom delta.
  Date/Author: 2026-06-21 / grill (#12 throughline Q3)

- Decision: Generalize by extending the one `port-behavior` skill with an Essentials arm, not a separate skill.
  Rationale: The cache-first flow, patch naming, capture/restore discipline, and packet rendering are already engine-neutral and partly documented for Essentials in the SKILL. Only the code-home convention, version-string source, and a once-proven path are new.
  Date/Author: 2026-06-21 / grill (#12 throughline Q4)

## Outcomes & Retrospective

To be written at completion. Compare against the purpose: can a person run the loop, see a `# chrooked:innerfocus` plugin load in Africanvs, and watch Focus Blast always hit in a debug battle while vanilla no-flinch survives?

## Code Review Findings

Populated after code review — leave blank until review is complete.

### High Risk

### Medium Risk

### Low Risk

## Context and Orientation

The reader needs to know four things: where the game is, how it runs, where the spec lives, and how the porting loop already works for the other engine.

**The game (Africanvs).** It is a Pokémon Essentials 16.2 fan game. It is not in this repository; its filesystem path is read at runtime from `targets.json` (gitignored) by `scripts/africanvs_devloop.sh`, which picks the entry whose `engine` is `essentials` and whose `label` contains "africanvs". "Essentials 16.2" means the game's data lives in flat text "PBS" files (`PBS/pokemon.txt`, `PBS/moves.txt`, etc.) and its logic lives in Ruby scripts. The applier already edits the PBS files faithfully (issues #20–#23).

**How it runs.** The game must be launched through the bundled **Wine `Game.exe`**, which carries Ruby 1.8 — the 16.2 scripts need it. The native macOS "Z-universal" binary uses a modern Ruby and crashes on 16.2 syntax; do not use it. `scripts/africanvs_devloop.sh` runs the applier then opens the copy's `Play Copy (Wine Debug).command`, which sets `MKXPZ_WINDOWS_CONSOLE=0` and boots through LaunchServices so the game window keeps keyboard focus. "mkxp-z" is the open-source RPG Maker XP runtime the game ships; "debug" boot exposes an in-game Debug menu that can spawn a Pokémon at a chosen level, set abilities/moves, and start a battle — that is the manual test bench.

**Where Ruby scripts load from.** The game's `Game.ini` sets `Scripts=Data\Scripts.rxdata` — a single binary archive of all Ruby scripts. Editing that archive for every port would be opaque and fragile. The `africanvs-dev-loop` work placed an `mkxp.json` with a `preloadScript` entry plus a `Scripts/load_order_shim.rb` in the external copy, intending to load loose `.rb` files from an external `Scripts/` directory so a port is a plain text file, not a binary repack. Whether this 32-bit Wine mkxp-z build actually honors that is the one empirical unknown — M0.

**The behavior spec.** `ruleset/behaviors/innerfocus.yaml` is the neutral, engine-agnostic description of the mechanic. It has two effects: a vanilla one ("prevents flinching") and a custom one ("the user's Focus Blast never misses"). It carries an `engine_hints.essentials` pointer (`Battle::Move#pbAccuracyCheck — return true early when user has Inner Focus and move is Focus Blast`) and three `test_cases` that are the portable Contract:

    1. Inner Focus user uses Focus Blast at a foe with +6 evasion → the move hits.
    2. Inner Focus user uses Hydro Pump → normal accuracy applies (no always-hit).
    3. A Pokémon without Inner Focus uses Focus Blast → normal 70% accuracy applies.

**The porting loop (already built for pokeemerald).** The `port-behavior` skill (`.claude/skills/port-behavior/SKILL.md`) is cache-first: it resolves the spec, computes a target version, and looks for `references/<id>.<engine>-<version>.patch`. On a cache hit it is a plain `git apply`. On a miss it emits a self-contained packet (`chrooked-pokedex behaviors --mechanic <id> --engine <engine>`), spawns a behavior-port subagent given only that packet, static-verifies the returned diff against the spec, verifies at runtime, captures the diff as a reference patch, restores the target, and surfaces for human approval. The SKILL already documents an Essentials branch in prose (use the game's version string; emit test_cases as a manual checklist). What it does not yet pin down — and what this tracer settles — is the **code home** (where the `.rb` plugin goes) and the **version string source** for Essentials. The proven pokeemerald example is `references/innerfocus.pokeemerald-expansion-1.15.3.patch`, whose Seam was `CanMoveSkipAccuracyCalc` in `src/battle_util.c`.

**Vanilla Inner Focus already exists in Essentials.** Stock Essentials ships the no-flinch Inner Focus. So the port must add **only** the custom Focus-Blast-always-hit delta and must not re-implement or disturb the vanilla no-flinch. Confirming the port respects that is part of acceptance.

## Architecture Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Code home for ported mechanics | External `# chrooked:<id>` Ruby plugin file loaded from the copy's `Scripts/` dir | Text-patchable; mirrors pokeemerald cache; forward-compatible with v21 `Plugins/` |
| Verification gate (tracer) | Manual numbered playtest checklist in the debug battle | Essentials has no automated harness; honesty stance forbids false runtime claims |
| First mechanic | `innerfocus` | Has Essentials hint + proven pokeemerald twin; binary oracle; intentional vanilla-overlap |
| Skill shape | Extend the one `port-behavior` skill | Shared scaffolding already engine-neutral; only code-home + version-string are new |
| Reference patch name | `references/innerfocus.essentials-16.2.patch` | Per-engine, per-version naming convention already established |
| Fallback if autoload fails | PBS-FunctionCode + Ruby-handler hybrid (reuses #22), never binary `Scripts.rxdata` edit | Keeps the apply text-based even if the external-Scripts route is unsupported |

## File Changes

### New Files

- In the **external Africanvs copy** (outside this repo, path from `targets.json`): `Scripts/chrooked_innerfocus.rb` — the ported mechanic, a small `pbAccuracyCheck` override tagged `# chrooked:innerfocus`. This is the artifact captured into the reference patch.
- `references/innerfocus.essentials-16.2.patch` — the captured port (the `.rb` plugin's content), reusable on the next Essentials port of innerfocus.

### Modified Files

- `.claude/skills/port-behavior/SKILL.md` — add the Essentials code-home convention (external `Scripts/<chrooked_id>.rb` plugin) and the Essentials version-string source (the dialect label `essentials-16.2`), so the next port is mechanical.
- `references/README.md` — add the inventory row for innerfocus on Essentials with the manual-verification note.
- `feature_requests/essentials-behavior-tracer-plan.md` — this living document, updated as milestones complete.
- `feature_requests/essentials-behavior-port-throughline.md` — frontmatter `acceptance_criteria`, `stage`, `next_action` kept current.

### Deleted Files

- None.

## Data & API Changes

No data or API changes. The tracer adds an engine-side Ruby plugin and reference/skill documentation; it does not change the neutral schema, the CLI surface, or the PBS appliers.

## Plan of Work

The work proceeds as four milestones, each independently verifiable. The order is forced by dependency: nothing downstream is trustworthy until M0 confirms loose `.rb` plugins actually load.

**M0 — Confirm the external-Scripts load path.** Boot the Africanvs copy in Wine debug via `scripts/africanvs_devloop.sh --no-apply`. Watch the mkxp-z console for `[LOAD_ORDER_SHIM] active` (the marker the shim prints when honored). If present, loose external `.rb` files load and the whole text-patch architecture holds. If absent, diagnose the `mkxp.json` `preloadScript` config; if this 32-bit Wine build genuinely cannot honor external load order, record that in the Decision Log and switch the code home to the fallback (a `FunctionCode` in `PBS/moves.txt` written by the existing applier plus a Ruby handler class), then re-run M0's check against that route. M0 ends when there is a proven way to land custom Ruby that the running game executes.

**M1 — Port the innerfocus custom delta.** Run the extended skill: `/port-behavior innerfocus --engine essentials --target <africanvs-copy-path>`. On the expected cache miss it emits the packet and spawns a behavior-port subagent given only that packet. The subagent explores the copy's Ruby scripts, finds `Battle::Move#pbAccuracyCheck` (the hint), and writes `Scripts/chrooked_innerfocus.rb`: a minimal override that returns an always-hit early **only** when the move's user has Inner Focus and the move is Focus Blast, tagged `# chrooked:innerfocus`. It must not touch the vanilla no-flinch path. The milestone ends with the plugin file present and a static review argument for each of the three test_cases.

**M2 — Manually verify in a debug battle.** Apply nothing new; just relaunch debug (`scripts/africanvs_devloop.sh --no-apply`). Using the Debug menu, stage each test_case and record the outcome: (1) an Inner Focus user repeatedly uses Focus Blast against a foe set to +6 evasion and hits every time (5/5); (2) the same user's Hydro Pump uses normal accuracy and can miss at +6 evasion; (3) a non-Inner-Focus user's Focus Blast uses normal 70% accuracy. Record the observed results as evidence in this plan's Artifacts section. Because the human is the oracle, label the result as manual verification — do not claim automated runtime proof.

**M3 — Capture and document.** Save the plugin's content as `references/innerfocus.essentials-16.2.patch` and add the inventory row to `references/README.md` with the manual-verification note. Extend `.claude/skills/port-behavior/SKILL.md`'s Essentials arm with the code-home convention discovered in M0 and the version-string source, so the next Essentials port does not rediscover them. Restore the copy to a known state if needed. The milestone ends when `git apply --check references/innerfocus.essentials-16.2.patch` succeeds against a clean copy.

## Concrete Steps

All commands run from the repository root `/Users/cdbrooks/Development/Games/chrooked-pokedex` unless noted. The Africanvs copy path is whatever `targets.json` records; below it is written as `<copy>`.

M0 — load-path check:

    scripts/africanvs_devloop.sh --no-apply
    # In the mkxp-z console window, expect a line:
    #   [LOAD_ORDER_SHIM] active
    # Present  -> external Scripts/ plugins load; proceed.
    # Absent   -> inspect <copy>/mkxp.json preloadScript; if unsupported, take the fallback (Decision Log).

M1 — port (cache miss path):

    git -C <copy> status --porcelain          # confirm clean (untracked OK); the copy may not be a git repo — if not, snapshot the Scripts/ dir instead
    chrooked-pokedex behaviors --mechanic innerfocus --engine essentials   # the packet the subagent receives
    # /port-behavior innerfocus --engine essentials --target <copy>
    # subagent writes <copy>/Scripts/chrooked_innerfocus.rb tagged # chrooked:innerfocus

M2 — manual verification:

    scripts/africanvs_devloop.sh --no-apply
    # Debug menu: give a test mon Inner Focus + Focus Blast + Hydro Pump; set foe evasion +6; battle.
    # Record: Focus Blast 5/5 hits; Hydro Pump can miss; non-Inner-Focus Focus Blast ~70%.

M3 — capture:

    cp <copy>/Scripts/chrooked_innerfocus.rb /tmp/chrooked_innerfocus.rb   # source of the patch body
    # produce references/innerfocus.essentials-16.2.patch from the plugin content
    git apply --check references/innerfocus.essentials-16.2.patch          # must succeed on a clean copy

## Validation and Acceptance

Acceptance is behavior a human observes in the running game, plus the static guarantees that the port is clean and reusable. The five criteria below each carry a proof method; they are mirrored into the Throughline frontmatter.

AC1 — A loose external Ruby plugin loads and executes in the Africanvs Wine debug build (the autoload caveat is settled, or the documented fallback is in force).
Proof: manual — boot debug; observe `[LOAD_ORDER_SHIM] active` (or, on the fallback route, a `# chrooked` debug print) in the mkxp-z console.

AC2 — The custom innerfocus delta works: an Inner Focus user's Focus Blast always hits a +6-evasion foe.
Proof: manual debug battle — Focus Blast hits 5/5 against a foe set to +6 evasion, where without the plugin it misses some of the time; plus static review that the override gates on the user's ability AND the move being Focus Blast.

AC3 — The effect does not leak and vanilla survives: the user's other moves use normal accuracy, a non-Inner-Focus user's Focus Blast uses normal accuracy, and vanilla no-flinch is untouched.
Proof: manual debug battle — (a) Inner Focus user's Hydro Pump can miss at +6 evasion; (b) a non-Inner-Focus user's Focus Blast uses ~70% accuracy; plus static review that `Scripts/chrooked_innerfocus.rb` adds no no-flinch code.

AC4 — The port is captured as a reusable, deterministically re-appliable reference.
Proof: `references/innerfocus.essentials-16.2.patch` exists and `git apply --check` succeeds against a clean copy; `references/README.md` has the inventory row.

AC5 — The next Essentials port is mechanical: the skill documents the code home and version string.
Proof: `.claude/skills/port-behavior/SKILL.md` contains the external-`Scripts/` code-home convention and the `essentials-16.2` version-string source; a reviewer can follow it without rediscovering M0.

### Manual Verification Steps

1. From the repo root run `scripts/africanvs_devloop.sh --no-apply` and confirm the game boots in Wine debug with the mkxp-z console visible.
2. Confirm `[LOAD_ORDER_SHIM] active` appears in the console (AC1).
3. Open the Debug menu, create a test Pokémon with the ability Inner Focus and the moves Focus Blast and Hydro Pump, and start a battle against a foe.
4. Raise the foe's evasion to +6 (use a debug move or repeated evasion boosts).
5. Use Focus Blast five times; confirm it hits all five (AC2).
6. Use Hydro Pump several times; confirm it can miss (AC3a).
7. Repeat with a Pokémon that does NOT have Inner Focus; confirm its Focus Blast misses sometimes (AC3b).
8. Inspect `Scripts/chrooked_innerfocus.rb`; confirm it is tagged `# chrooked:innerfocus` and contains no no-flinch logic (AC3 static).

## Testing Plan

### Unit Tests

- None at the engine layer — Essentials has no automated battle harness, which is the explicit reason this tracer's gate is manual. (The headless Ruby harness is #15, out of scope here.) If M0 takes the PBS-FunctionCode fallback, add/confirm the existing applier's unit coverage for writing that move's `FunctionCode` column, but write no new neutral-schema logic.

### Integration Tests

- None new. The data appliers this rides on are already covered (#20–#23).

### E2E Tests

- The end-to-end flow IS the manual debug-battle checklist above; it is the project's accepted E2E shape for Essentials mechanics until #15 automates it.

## Idempotence and Recovery

The loop is safe to repeat. Re-running `/port-behavior` on a cache hit is a plain re-apply of the same plugin file; on a clean copy it overwrites `Scripts/chrooked_innerfocus.rb` deterministically. If a step half-fails, delete `<copy>/Scripts/chrooked_innerfocus.rb` and re-run M1. The external copy is the only thing mutated outside the repo; keep a snapshot of its `Scripts/` dir before M1 so M0's baseline can be restored. Building/booting is non-destructive; the PBS files are not touched by this plan.

## Artifacts and Notes

To be filled during execution: the mkxp-z console line proving the load path (M0), the `chrooked_innerfocus.rb` diff (M1), and the recorded hit/miss tallies from the debug battle (M2).

## Interfaces and Dependencies

- Skill entry point (existing, extended): `/port-behavior <id> --engine essentials --target <copy>` in `.claude/skills/port-behavior/SKILL.md`.
- Packet renderer (existing, reused): `chrooked-pokedex behaviors --mechanic innerfocus --engine essentials`, implemented in `src/chrooked_pokedex/behavior/packet.py`.
- Behavior spec (existing): `ruleset/behaviors/innerfocus.yaml`, model `src/chrooked_pokedex/model/behavior_spec.py`.
- Dev loop (existing): `scripts/africanvs_devloop.sh`, doc `docs/africanvs-dev-loop.md`.
- Engine Seam to override in the port: `Battle::Move#pbAccuracyCheck` in the Africanvs copy's Ruby scripts.
- Reference library convention (existing): `references/<chrooked_id>.<engine>-<version>.patch`, here `references/innerfocus.essentials-16.2.patch`.

## Revision note

2026-06-21 — Initial plan authored from the #12 grill Decision Ledger (Q1–Q4). Scope is the tracer sub-issue #14 only; #15 (headless harness) and #16 (port loop + DATA-ONLY flip) are out of scope and referenced for continuity.
