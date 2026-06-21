# Generalize the Essentials acceptance-test harness (#15)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository keeps its ExecPlan format guide at `~/.claude/PLAN.md`. This document must be maintained in accordance with that guide. It builds on the completed tracer plan `feature_requests/essentials-behavior-tracer-plan.md` (sub-issue #14); where that plan is referenced, the relevant facts are repeated here so this document stands alone.

## Purpose / Big Picture

The tracer (#14) proved one custom mechanic — **innerfocus** — actually fires inside the Essentials 16.2 game **Africanvs**: an Inner Focus user's Focus Blast always hits, vanilla survives. But the way it was proven was hand-built for that one mechanic. The plugin printed a single tagged line to the game console each time Focus Blast was cast (`[chrooked:innerfocus] ALWAYS-HIT` versus `normal accuracy`), and a human read those lines off the mkxp-z console and decided pass or fail by eye. Nothing about that reader is reusable: a second mechanic would need a brand-new hand-built check.

After this change, any behavior spec's neutral `test_cases` can be turned into a **machine-checked PASS/FAIL run** against Africanvs, not just innerfocus. A person runs one command, the harness boots the game (or a slimmer Ruby entry point — see M0), drives the scripted scenario each `test_case` describes, and prints one readable line per case: `PASS innerfocus :: Inner Focus user uses Focus Blast at a foe with +6 evasion` or a `FAIL` line naming the spec and the case that broke. This is what turns "I ported it" into "the spec verifies it on Essentials," and it is the runner that sub-issue #16 reuses to drive the whole port loop.

"Behavior spec" means one of the engine-neutral YAML files under `ruleset/behaviors/` (for example `ruleset/behaviors/innerfocus.yaml`). Each carries a list of `test_cases`, where every case is a `given:` sentence describing a battle setup and an `expect:` sentence describing the observable outcome. Those sentences are plain English written for a human; turning each into something a machine can run is the core of this work, and the honest limit on it (English is not auto-runnable) is addressed head-on in M1.

"Oracle" means the thing that decides pass or fail. The tracer's oracle was a human reading a log line. This plan replaces the human with code.

## Context and Orientation

A reader who knows nothing about this repo needs these facts, all established by the tracer (#14) and verified on the real machine:

- **Africanvs** is an on-disk copy of a Pokémon Essentials **16.2** fan-game (mkxp-z, RGSS), launched via `Game.exe`. It is the Target. Its path is machine-specific.
- **This machine (2026-06-21): WSL host, native Windows game.** The clone lives on the Windows D: drive at `D:\Games\Pokemon FanGames\Pok-mon-Africanvs-Definitive-Edition` = WSL `/mnt/d/Games/Pokemon FanGames/Pok-mon-Africanvs-Definitive-Edition` (mind the space). `Game.exe` is a **native Windows** mkxp-z binary — launch it via WSL interop (run the `/mnt/d/...Game.exe` directly or `cmd.exe /c`), **not Wine**. The tracer's "Wine debug build" wording is stale here; the Ruby-1.8 / preload-shim / external-`Scripts/` facts below are the engine, not the OS, so they are expected to carry — M0 re-confirms that on the Windows build.
- **No dev-copy exists on this machine yet.** The dev-copy (what `apply` and the harness write into) must be created from the D: clone before any boot, and should live on the **D: drive** (e.g. beside the original) so the Windows `Game.exe` runs against native FS rather than the slow `\\wsl$` bridge. The WSL repo applies into `/mnt/d/...` via DrvFs. Register it in `targets.json` (gitignored, machine-specific — never commit).
- The tracer used a dev-loop script `scripts/africanvs_devloop.sh` (`--no-apply` boots without re-running the applier). It was written for the Linux+Wine setup; M0 confirms or adapts its launch/path handling for the WSL→native-Windows shape.
- **The engine is Ruby 1.8.** `Module#prepend` and `TracePoint` do **not** exist. Method overrides must use `alias_method` chaining. This bit the tracer twice (first boot crashed on `STDERR` EBADF, second on `uninitialized constant TracePoint`); do not repeat those mistakes.
- **External Ruby loads through a preload shim.** The copy root has an `mkxp.json` with `preloadScript: ["Scripts/load_order_shim.rb"]`. The shim runs *before* `Data/Scripts.rxdata` (the compiled engine, 228 scripts, Marshal+Zlib), so any plugin that touches an engine class must install **lazily** once that class is defined. The tracer defers installation by hanging a one-shot off the native `Graphics.update` (defined at preload, called every frame, alias-chain-safe). Look for `[LOAD_ORDER_SHIM] active` on the console to confirm the preload path is live.
- **The real 16.2 classes** (extracted from `Data/Scripts.rxdata`, ground truth — not the spec's `engine_hints`, which name the wrong modern classes): move logic is `PokeBattle_Move` (e.g. `pbAccuracyCheck(attacker,opponent)` at `084_PokeBattle_Move.rb:490`); the battle object is `PokeBattle_Battle`; flinch is `PokeBattle_Battler#pbFlinch` (`083:733`); abilities are checked with `hasWorkingAbility(:SYMBOL)`; damage calc lives in `PokeBattle_Move#pbCalcDamage` / the multiplier hooks in sections 082–084.
- **STDERR is unsafe** in this build (console suppressed; raw writes crash with EBADF). The tracer routes all plugin output to a guarded logfile `Scripts/chrooked_load.log` *and* the in-game console when available. The harness reads that logfile.
- **Existing reusable pieces:** `Scripts/chrooked_innerfocus.rb` (the tracer's ported plugin, gated on `:INNERFOCUS` + `:FOCUSBLAST`), `references/innerfocus.essentials-16.2.patch` (captured port), `references/README.md` (inventory), and the `port-behavior` skill at `.claude/skills/port-behavior/SKILL.md` (its Essentials arm documents the code-home convention and the `essentials-16.2` version string).
- **The Python side:** behavior specs are loaded by `src/chrooked_pokedex/model/behavior_spec.py`; packets render via `src/chrooked_pokedex/behavior/packet.py`. The harness driver added here is the first Python code that *reads back* an Essentials run result.

There is **no existing "pokeemerald Slice 3 harness" file** to copy — that track verified through the same spec→port→verify shape, not a standalone runner. "Mirror pokeemerald Slice 3" therefore means *match that shape* (a spec's `test_cases` decide acceptance), not port a file that does not exist.

## The one empirical unknown

The tracer's oracle was a **log line**, because setting a foe to +6 evasion in a live battle is impractical and Focus Blast's 70% accuracy makes raw hit-counts unreliable. That same constraint governs this plan. There are two ways to build a reusable oracle, and which is feasible is the unknown M0 settles:

- **Route A — headless Ruby `Battle`.** Instantiate `PokeBattle_Battle` directly with scripted Pokémon, run a turn, assert on the outcome in Ruby. This is the cleanest RED→GREEN, but it is unproven that the 16.2 mkxp-z/Wine build can construct a `PokeBattle_Battle` without the full graphics/input/scene stack. If it needs the scene loop, Route A is dead weight.
- **Route B — generalized log oracle (the proven path).** Keep booting the real game in a scripted debug battle, but standardize what every chrooked plugin logs (`[chrooked:<id>] <case-id> <PASS|FAIL|observed-value>`) and add a Python driver that reads `Scripts/chrooked_load.log` and maps lines to `test_cases`. This reuses exactly what already works for innerfocus; the only new code is the standard log format plus the Python reader.

M0 spikes Route A cheaply. If `PokeBattle_Battle.new(...)` boots and runs one turn without the scene stack, M1 builds on Route A. Otherwise M1 builds Route B. **Either way the harness Surface is identical** — `harness run <mechanic-id>` prints PASS/FAIL per `test_case` — so the rest of the plan does not branch.

## Architecture Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Oracle mechanism | Spike Route A (headless `Battle`); fall back to Route B (generalized log oracle) | Route B is already proven by the tracer; Route A is only adopted if the spike shows it boots cheaply. No speculative runner. |
| test_case → assertion | One tiny per-mechanic Ruby scenario encodes its `test_cases`; the runner is generic | English `test_cases` are not auto-runnable. Honest minimum: encode each mechanic's cases once, in Ruby, beside its plugin. The *runner* is general; the *scenario* is per-mechanic — same division the ports already use. |
| Harness Surface | `harness run <mechanic-id>` → one `PASS`/`FAIL` line per case | Stable Surface so #16 can call it in a loop regardless of which route won. |
| Second mechanic (generality proof) | `kindle` (proposed; the one open decision) | Hits a *different* Seam than innerfocus — damage-calc multiplier (1.5x Fire when ability is Kindle) vs accuracy — so passing proves the harness is not innerfocus-shaped. Binary, log-observable. Final pick set at approval. |
| Where harness lives | Ruby runner under the copy's `Scripts/` (`chrooked_harness.rb`); Python driver under `src/chrooked_pokedex/behavior/` | Mirrors the plugin code-home; keeps the only result-reader on the Python side with the rest of the behavior layer. |

## Milestones

### M0 — Stand up a dev-copy on this machine, then spike whether a headless `PokeBattle_Battle` boots

Scope: this machine has no dev-copy and a *native Windows* `Game.exe` under WSL, so M0 has two parts.

First, **create and register the dev-copy**: copy the D: clone (`/mnt/d/Games/Pokemon FanGames/Pok-mon-Africanvs-Definitive-Edition`) to the dev-copy `/mnt/d/Games/Pokemon FanGames/Pok-mon-Africanvs-Definitive-Edition - devcopy` (`D:\Games\Pokemon FanGames\Pok-mon-Africanvs-Definitive-Edition - devcopy` — sibling on the **D: drive**, so the Windows exe runs against native FS, not `\\wsl$`), register it in `targets.json`, place the `mkxp.json` preload + `Scripts/load_order_shim.rb`, boot it once, and confirm `[LOAD_ORDER_SHIM] active` appears in `Scripts/chrooked_load.log` — i.e. that the external-`Scripts/` autoload that held on Wine also holds on the native Windows mkxp-z build. Launch is via WSL interop (run the `/mnt/d/...Game.exe` directly), not Wine; adapt `scripts/africanvs_devloop.sh` if its launch/path handling assumes Wine.

Second, **spike the oracle route**: a preload-loaded Ruby snippet that, once the engine classes exist, tries to construct a minimal `PokeBattle_Battle` with two scripted Pokémon and step one turn, logging either `[chrooked:harness] battle-boot OK` or the exception class. Read `Scripts/chrooked_load.log`.

What exists at the end: a registered, bootable dev-copy on this machine with the preload path confirmed; and a recorded decision — Route A (headless) or Route B (log oracle) — in this plan's Decision Log, with the probe's log output pasted as evidence. No production harness yet.

Acceptance: `[LOAD_ORDER_SHIM] active` confirmed on the native Windows build; **and** the log shows either a clean battle-boot line (→ Route A) or a captured failure proving the scene stack is required (→ Route B, the proven fallback). Either oracle outcome passes M0; the point is a *settled, evidenced* choice.

### M1 — The generic runner + innerfocus re-proved through it

Scope: build `harness run <mechanic-id>` on the route M0 chose, and re-verify the tracer mechanic *through the new generic runner* (not the old one-off). Standardize the log line every chrooked plugin emits to `[chrooked:<id>] <case-index> <PASS|FAIL>`; encode innerfocus's three `test_cases` as a tiny scenario; add the Python driver in `src/chrooked_pokedex/behavior/` that invokes the run and parses results into per-case PASS/FAIL.

What exists at the end: running the harness on `innerfocus` reproduces the tracer's result — case 1 (Focus Blast at +6 evasion) PASS, case 2 (Hydro Pump normal accuracy) PASS, case 3 (non-Inner-Focus Focus Blast normal accuracy) PASS — printed as three readable lines, with zero innerfocus-specific code in the runner.

Acceptance: `harness run innerfocus` prints 3/3 PASS; the runner file contains no `innerfocus`/`focusblast` literals.

### M2 — Prove generality with a second mechanic

Scope: port the chosen second mechanic (proposed `kindle`) as a `# chrooked:<id>` plugin if not already present, encode its `test_cases` as a scenario, and run it through the *same* harness. This exercises a different Seam (damage-calc multiplier, not accuracy), which is what proves the harness is general.

What exists at the end: `harness run kindle` (or the chosen mechanic) prints its `test_cases` as PASS, with the only new code being the mechanic's plugin + scenario — the runner untouched since M1.

Acceptance: the second mechanic's cases report PASS through the unchanged runner; the diff to the runner between M1 and M2 is empty.

### M3 — Readable failure reporting + reuse documentation

Scope: confirm failures read clearly and document the harness so #16 can drive it cold. Deliberately break the second mechanic's port (e.g. flip the gate), run the harness, observe a FAIL line that names the spec and the failing `test_case`, then restore. Extend `.claude/skills/port-behavior/SKILL.md`'s Essentials arm with the harness entry point and the "add a mechanic" steps (write plugin → write scenario → `harness run <id>`).

What exists at the end: an honest, reusable verification gate for Essentials ports, documented where the next porter will find it.

Acceptance: a broken port yields a FAIL line naming spec + case; the SKILL names the harness command and the add-a-mechanic steps.

## File Changes

### New Files
- `<africanvs-copy>/Scripts/chrooked_harness.rb` — generic Ruby runner: given a mechanic id, load its scenario, run it (Route A or B), emit `[chrooked:<id>] <case> <PASS|FAIL>` lines. (Lives in the on-disk game copy, captured as a reference patch like the plugins.)
- `<africanvs-copy>/Scripts/chrooked_<mechanic>_cases.rb` — per-mechanic scenario encoding its `test_cases` (one for innerfocus, one for the second mechanic).
- `src/chrooked_pokedex/behavior/harness.py` — Python driver: invoke the boot, read `Scripts/chrooked_load.log`, map lines to a spec's `test_cases`, return/print per-case PASS/FAIL.
- `references/<mechanic2>.essentials-16.2.patch` — captured second-mechanic port (if M2 produces a new one).

### Modified Files
- `<africanvs-copy>/Scripts/chrooked_innerfocus.rb` — emit the standardized harness log line (additive; vanilla path untouched).
- `.claude/skills/port-behavior/SKILL.md` — Essentials arm: harness command + add-a-mechanic steps.
- `references/README.md` — inventory row for the second mechanic if ported.
- `feature_requests/essentials-behavior-port-throughline.md` — control file: stage/ACs for #15.

### Deleted Files
- None.

## Data & API Changes

No data or API changes. The harness is a developer tool; it adds no endpoints and no Ruleset schema changes.

## Validation and Acceptance

Run from the repo root unless noted. The harness needs the on-disk Africanvs copy (machine-specific, reached via `scripts/africanvs_devloop.sh`); on a machine without it, the harness is auto-skipped, exactly like the existing `integration`-marked tests.

### Manual Verification Steps

1. M0: boot `scripts/africanvs_devloop.sh --no-apply`, then read `<copy>/Scripts/chrooked_load.log`; confirm a `battle-boot OK` line (Route A) or a recorded failure (Route B). Either is a pass for M0.
2. M1: run the harness on `innerfocus`; expect three lines, all `PASS`, naming each `test_case`.
3. M2: run the harness on the second mechanic; expect its cases `PASS`.
4. M3: edit the second mechanic's plugin to break the gate; re-run; expect a `FAIL` line naming the spec + case; restore the plugin and re-run to green.

### Expected transcript (illustrative)

        $ <harness invocation> innerfocus
        PASS innerfocus :: Inner Focus user uses Focus Blast at a foe with +6 evasion
        PASS innerfocus :: Inner Focus user uses Hydro Pump (normal accuracy)
        PASS innerfocus :: a Pokemon without Inner Focus uses Focus Blast (normal 70%)

## Testing Plan

### Unit Tests
- `harness.py` log-line parser: given a sample `chrooked_load.log`, maps lines to a spec's `test_cases` and yields correct PASS/FAIL. Hermetic (`unit` marker) — no game needed, feed a captured log fixture.

### Integration Tests
- `harness run innerfocus` and `harness run <mechanic2>` against the real copy (`integration` marker, auto-skipped when absent).

### E2E Tests
- The M3 break-and-restore is the end-to-end flow; it doubles as the failure-reporting proof.

## Idempotence and Recovery

The harness only reads the game and writes its own logfile; re-running is safe. Plugin edits are additive and captured as text patches (`git apply --check` re-appliable, per the tracer's discipline). Breaking a port in M3 is reverted by restoring the plugin file from its reference patch. Never hand-edit the binary `Scripts.rxdata`.

## Progress

- [x] (2026-06-21) M0 — Dev-copy created at `…- devcopy` (rsync, .git/Z-universal/.DS_Store excluded, 1.1 GB) + registered in `targets.json`. Harness assets placed (`mkxp.json`, `Scripts/load_order_shim.rb`, `Scripts/chrooked_harness_probe.rb`). Booted `Game.exe debug` via PowerShell `Start-Process`; `chrooked_load.log` showed `[LOAD_ORDER_SHIM] active`, the glob-loader loading the probe, and `PokeBattle_Battle #initialize arity=5`. Route decided: **Route B (generalized log oracle)** — arity-5 constructor means a headless battle needs a full mock scene, not cheap. Bonus: the general glob-loader shim is proven (M1 loader piece done early).
- [x] (2026-06-21) M1 — Generic runner done. `src/chrooked_pokedex/behavior/harness.py` (stage/verify, mechanic-agnostic) + `harness_scenarios.py` (per-mechanic data) + upgraded `chrooked_innerfocus.rb` (uniform `OBS move=… if=… result=…` per accuracy check). `tests/test_harness.py` 4/4 (unit, hermetic). In-game: staged + played one debug battle; `verify innerfocus` → 3/3 PASS through the new runner, correctly ignoring opponent move noise (TACKLE/STRINGSHOT/SCRATCH). `grep` confirms no innerfocus/focusblast literals in harness.py logic (only docstring examples).
- [x] (2026-06-21) M2 — `kindle` (1.5x Fire damage) ported at a NEW Seam: `PokeBattle_Move#pbModifyDamage` (the engine's final-damage multiplier hook; mirrors Blaze sans HP check, verified against extracted Scripts.rxdata). Added `chrooked_kindle.rb` + a `kindle` entry in `harness_scenarios.py` + one KINDLE ability row (id 299) in the devcopy abilities.txt fixture. `harness.py` UNCHANGED. In-game `verify kindle` → 3/3 PASS through the same runner. (Case 2 "non-Fire = no boost" witnessed by a Tackle cast rather than Surf — equivalent, since Kindle only boosts Fire; noted in the scenario.) Bonus discovery: the harness honestly reported FAIL "not observed" when Surf was first skipped — readable-failure evidence for AC4.
- [x] (2026-06-21) M3 — AC4 readable failures: proven organically (live `verify kindle` printed `FAIL kindle :: a Kindle user uses Surf (Water) (not observed ...)` when the action was skipped) PLUS the hermetic `test_fail_when_delta_leaks_to_other_move` (wrong-result FAIL with `expected/observed`). No separate staged break needed — both failure modes (missing action, wrong result) are already demonstrated. AC5 docs: extended `.claude/skills/port-behavior/SKILL.md` Essentials arm with the `harness stage|verify` commands, the add-a-mechanic steps (plugin OBS format → scenario entry), the glob-loader (no `load_order.txt`), `references/essentials-harness/` asset home, and the WSL/native-Windows launch line.

## Surprises & Discoveries

- Observation: Runtime moved from the tracer's Linux+Wine setup to WSL host + native Windows `Game.exe`, and no dev-copy exists on this machine.
  Evidence: Chris, 2026-06-21 — clone at `D:\Games\Pokemon FanGames\Pok-mon-Africanvs-Definitive-Edition`. Implication folded into M0 (create D:-drive dev-copy, launch via WSL interop, re-confirm the preload/autoload path on the Windows build). Captured in memory `africanvs-target-env`.

- Observation: `Game.exe` (the mkxp-z Windows binary) DOES support `preloadScript`/`mkxp.json` — so external-`Scripts/` autoload is viable here, contradicting `docs/africanvs-dev-loop.md` which claims the Wine `Game.exe` "predates preloadScript and silently ignores mkxp.json." The tracer's finding (preload worked once mkxp.json was authored) is the correct one.
  Evidence: `strings Game.exe | grep -iE 'preloadScript|mkxp.json'` → both present. The doc's negative result was likely the macOS-Wine layer or the then-missing mkxp.json, not the binary. M0 still empirically confirms `[LOAD_ORDER_SHIM] active` on this machine.

- Observation: The D: clone is the macOS copy synced over — carries `.DS_Store`, `Z-universal.app` (macOS binary, useless on Windows), `.command` launchers — and its `.git` is 847 MB of the 2.0 GB. The tracer's dev-loop assets are gone: `Scripts/` holds only an empty `load_order.txt`; no `mkxp.json`, no `load_order_shim.rb`, no `chrooked_innerfocus.rb`.
  Evidence: `ls` of clone root + `Scripts/`. Implication: copy excludes `.git`/`Z-universal.app`/`.DS_Store` (~1.2 GB net); the preload shim, `mkxp.json`, and the innerfocus plugin (re-apply from `references/innerfocus.essentials-16.2.patch`) are recreated in M0/M1. `Game.ini` is stock `Library=RGSS104E.dll` (vestigial under mkxp-z).

## Decision Log

- Decision: Spike Route A (headless `PokeBattle_Battle`) before committing to it; Route B (generalized log oracle) is the proven fallback.
  Rationale: The tracer already proved the log-oracle path; a headless Battle is cleaner but unproven under the 16.2 Wine scene stack. Spiking first avoids building a runner on an assumption.
  Date/Author: 2026-06-21 / plan (#15)

- Decision: M0 RESOLVED → **Route B (generalized log oracle)**. Route A dropped.
  Rationale: The M0 probe reported `PokeBattle_Battle#initialize arity=5` (scene, p1party, p2party, player, opponent). A headless battle would require constructing/mocking a full `PokeBattle_Scene` plus two parties and two trainers — clearly not the cheap path. Route B (each plugin logs its gate decision; a Python driver reads `chrooked_load.log`) is already proven end-to-end by the tracer and is reused. Harness Surface is unchanged either way.
  Date/Author: 2026-06-21 / M0 (#15)

- Decision: Launch on this machine is `powershell.exe Start-Process -FilePath Game.exe -WorkingDirectory <D: devcopy> -ArgumentList debug`, NOT the macOS `open`/`.command` flow and NOT `cmd /c start` (which errors on the WSL UNC cwd).
  Rationale: Start-Process sets the Windows working dir cleanly from WSL; the probe fires at the title screen (scripts load at boot, Graphics.update ticks), so M0 needed no human battle.
  Date/Author: 2026-06-21 / M0 (#15)

- Decision: Encode each mechanic's `test_cases` as a tiny per-mechanic Ruby scenario; keep the runner generic.
  Rationale: The `test_cases` are English, not machine-runnable. Auto-compiling English is out of scope and unnecessary; the honest minimum is one small scenario per mechanic beside its plugin, exactly mirroring the existing per-mechanic plugin/per-engine-runner split.
  Date/Author: 2026-06-21 / plan (#15)

- Decision: Proposed second mechanic is `kindle` (1.5x Fire damage when ability is Kindle).
  Rationale: Different Seam than innerfocus (damage calc vs accuracy), so passing proves harness generality rather than re-testing one hook; binary and log-observable. Final pick confirmed at approval.
  Date/Author: 2026-06-21 / plan (#15)

## Outcomes & Retrospective

- **Done (2026-06-21).** #15 delivered: a reusable Route-B log-oracle harness. `harness.py`
  (generic stage/verify) + `harness_scenarios.py` (per-mechanic data) + the general glob-loader shim.
  innerfocus re-proved 3/3 through the new runner; kindle (a different Seam, `pbModifyDamage`) proved
  3/3 with the runner untouched. Readable failures shown live + hermetically. SKILL Essentials arm
  documents the harness + add-a-mechanic steps. All 5 ACs pass.
- **What changed vs the plan.** Route A (headless Battle) was dropped at M0 on hard evidence
  (`PokeBattle_Battle` arity=5). The "pokeemerald Slice 3 harness" turned out not to exist as a file,
  so we matched the spec→port→verify *shape* rather than porting code. Runtime was a third environment
  (WSL + native Windows `Game.exe`), and the macOS doc's "preloadScript unsupported" claim was wrong —
  the binary exports `preloadScript`; preload works on Windows.
- **Honest limits.** A human still plays one debug battle per mechanic (no headless auto-run). The
  verdict is automated and uniform; the staging is manual, as ledger Q2 accepted.
- **Carries to #16.** The harness Surface (`stage`/`verify <id>`) + the `references/essentials-harness/`
  loader assets are the reuse seam #16 drives in a loop. Adding KINDLE to the devcopy was a hand-edited
  PBS fixture (one line); #16's applier should write that ability row properly and flip the
  `DATA ONLY: implement mechanic` boundary once an accepted Essentials port exists.
- **Env note (not #15 scope):** the machine's default `python` is 3.8; the web test suite needs ≥3.11
  (15 collection errors under 3.8). The harness code is 3.8-safe via `from __future__ import annotations`.

## Code Review Findings

### High Risk

### Medium Risk

### Low Risk
