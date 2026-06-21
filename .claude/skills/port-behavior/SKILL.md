---
name: port-behavior
description: Port a Ruleset behavior spec (a custom Pokémon ability/move mechanic) into a target pokeemerald-expansion or Pokémon Essentials fork. Use when implementing a custom mechanic into an engine, porting a behavior, or filling the reference library. Checks references/ for a cached patch first (deterministic git apply); on a cache miss it emits the implementation packet, spawns a behavior-port agent, compiles, verifies against the spec's acceptance tests, and captures the new patch.
argument-hint: "<mechanic-id> [--engine pokeemerald] [--target PATH]"
disable-model-invocation: true
---

# Port Behavior

Implement one Ruleset **behavior spec** into a real engine fork. This is the LLM-as-compiler
[Surface](~/.claude/CONTEXT.md) — kept deliberately apart from the deterministic data applier
(`chrooked-pokedex apply`), which must stay pure and reproducible. The LLM's output is a
*proposal* that only becomes trusted after it compiles, passes review against the spec's
acceptance tests, and you approve it. Determinism is recovered at the **reference library**:
once a patch is captured, future ports of that exact (mechanic, engine, version) are a plain
`git apply`, no LLM.

## Quick start

```
/port-behavior innerfocus --engine pokeemerald --target ../ROMs/pokeemerald-expansion
```

- `<mechanic-id>` (required) — the behavior spec's `chrooked_id` (a file in `ruleset/behaviors/`).
- `--engine` (default `pokeemerald`) — which engine hint to surface; `pokeemerald` or `essentials`.
- `--target` (required for a cache miss) — path to the fork to edit. Must be git-clean.

## Algorithm: cache-first

1. **Resolve the spec.** Confirm `ruleset/behaviors/<mechanic-id>.yaml` loads:
   `chrooked-pokedex behaviors --mechanic <id>` (errors if unknown).
2. **Read the target version.** From `<target>/include/constants/expansion.h`
   (`EXPANSION_VERSION_MAJOR/MINOR/PATCH`) build `<engine>-<major.minor.patch>`, e.g.
   `pokeemerald-expansion-1.15.3`. For Essentials, use the game's version string.
3. **Cache check.** If `references/<mechanic-id>.<engine>-<version>.patch` exists → **cache hit**.
   Else → **cache miss**.

### Cache hit (no LLM)

```
git -C <target> apply --check references/<id>.<engine>-<version>.patch   # verify it still applies
git -C <target> apply        references/<id>.<engine>-<version>.patch
```

If `--check` fails (the engine drifted), treat it as a cache miss and re-derive; flag that the
stored patch is stale.

### Cache miss (invoke the LLM)

1. **Confirm the target is git-clean.** `git -C <target> status --porcelain` — abort if there are
   tracked changes (you need a clean diff to capture). Untracked files are fine.
2. **Emit the packet.**
   `chrooked-pokedex behaviors --mechanic <id> --engine <engine>` — this is the self-contained brief.
3. **Spawn a behavior-port subagent** (Task/Agent tool) with the packet. Use the prompt template
   below. The subagent gets ONLY the packet — that is the test of spec sufficiency. It returns BOTH
   the mechanic edit AND, for pokeemerald, a battle test compiled from the spec's `test_cases`.
4. **Static-verify** the returned diff yourself:
   - the gate matches the spec (right condition, right ownership — attacker vs target ability);
   - it does not leak (other moves / other abilities unaffected);
   - it did not duplicate vanilla logic;
   - it touched only the intended file(s) and carries the `// chrooked:<id>` tag.
   - Walk EACH acceptance test in the spec and argue why the edit satisfies it.
5. **Verify by running the acceptance tests — RED then GREEN.** This is the real gate.

   **pokeemerald-expansion** ships an executable battle harness (`test/battle/`, run by the
   prebuilt `tools/mgba/mgba-rom-test`). Each spec `given/expect` case becomes a
   `SINGLE_BATTLE_TEST` in `test/battle/ability/<id>.c` (or `move/<id>.c`). Use
   `PASSES_RANDOMLY(passes, trials, RNG_ACCURACY)` to make probabilistic outcomes deterministic —
   e.g. a 70%-accuracy move asserted at `100, 100` proves an always-hit bypass.

   - **RED:** with the test in place but the mechanic NOT applied, run the test. It MUST fail. A
     test that passes on the clean engine proves nothing — it is not exercising your change.
   - **GREEN:** apply the mechanic, re-run. It MUST pass.
   ```bash
   docker run --rm -v "$(cd <target> && pwd)":/project -w /project \
     devkitpro/devkitarm:20240202 \
     bash -c "apt-get update -qq >/dev/null && apt-get install -y -qq build-essential libpng-dev libelf-dev cmake >/dev/null; make check TESTS=\"<test name filter>\" -j$(sysctl -n hw.ncpu) 2>&1 | tail -40; echo CHECK_EXIT=\${PIPESTATUS[0]}"
   ```
   The first test-ROM build is long (~12-15 min); the GREEN re-run is incremental. `make modern`
   (ROM-only, faster) is a weaker fallback that proves it *builds* but not that the behavior is real.

   **Essentials** cannot run battles headlessly (the 16.2 `PokeBattle_Battle` constructor needs a
   full on-screen scene + parties — `#initialize` arity is 5; confirmed in M0 of issue #15), so
   verification is a **log-oracle harness with a one-battle human step**, not a fully automated run.
   Do not claim runtime verification you did not perform — a human still plays the battle.

   The harness (`src/chrooked_pokedex/behavior/harness.py`, issue #15):

       PYTHONPATH=src python -m chrooked_pokedex.behavior.harness stage  <id>   # clears the log, prints the in-game actions
       # boot the game (debug), run the printed actions in one battle, quit
       PYTHONPATH=src python -m chrooked_pokedex.behavior.harness verify <id>   # reads the log -> PASS/FAIL per spec test_case

   **To add a mechanic to the harness** (the runner never changes): (1) write the plugin
   `Scripts/chrooked_<id>.rb` so it logs ONE uniform line per gated battle event —
   `[chrooked:<id>] OBS key=value ...` (e.g. `move=FLAMETHROWER kindle=true result=BOOSTED`); (2) add
   an entry under `<id>` in `src/chrooked_pokedex/behavior/harness_scenarios.py` — one check per spec
   `test_case`, in order, each with a `stage` instruction, a `select` (key/values picking the relevant
   OBS line) and an `expect` (key/values that must hold). The driver matches them and reports PASS/FAIL
   using the spec's own `test_case` wording. A `select` that matches no OBS line reports a readable
   `not observed` FAIL (the staged action was skipped) — it never false-passes.

   **Essentials code home & version string (16.2 dialect, e.g. Africanvs).** A ported mechanic is a
   loose external Ruby plugin `Scripts/chrooked_<chrooked_id>.rb` in the game copy, tagged
   `# chrooked:<id>`, auto-loaded by the copy's `load_order_shim.rb` (preloaded via `mkxp.json` →
   `preloadScript`; the shim globs `Scripts/chrooked_*.rb`, so NO `load_order.txt` editing is needed).
   The canonical port AND the loader assets live in `references/essentials-harness/`
   (`mkxp.json`, `load_order_shim.rb`, and one `chrooked_<id>.rb` per mechanic). Never repack the
   binary `Scripts.rxdata`. **There is no per-id `.patch` for Essentials** (issue #16, Q9): an
   Essentials port is an additive standalone file, so the captured artifact IS the plugin in
   `references/essentials-harness/`, and `chrooked-pokedex apply --engine essentials` **installs** it —
   copies it into the target's `Scripts/` (and ensures the loader assets), then the 16.2 ability-create
   report line flips from `DATA ONLY` to "mechanic installed". An unported spec (no plugin file) still
   reports `DATA ONLY`, honestly. The honesty Invariant: the warning disappears only when the plugin is
   genuinely installed.

   **The full Essentials loop** (what "end-to-end" means here — a documented sequence, no new command):
   (1) `behaviors --mechanic <id> --engine essentials` emits the packet; (2) port it — cache hit if
   `references/essentials-harness/chrooked_<id>.rb` already exists, else derive a new plugin from the
   packet; (3) `apply --engine essentials --target <copy>` installs the plugin + flips the boundary;
   (4) `harness stage <id>` → play one debug battle → `harness verify <id>` → PASS per test_case;
   (5) surface for review. A human plays the battle (the engine can't run battles headlessly).
   Gotchas proven on the innerfocus tracer: (1) the 16.2 battle class is `PokeBattle_Move`
   (modern Essentials is `Battle::Move`), so verify the Seam against the **extracted** scripts
   (`ruby -e` Marshal-load + Zlib-inflate `Data/Scripts.rxdata`), not the spec hint; (2) this engine
   runs **Ruby 1.8** — `Module#prepend` AND `TracePoint` are both 2.0+ and do NOT exist, so override
   via `alias_method` chaining (not `prepend`) and defer the install via a one-shot hung on the
   native `Graphics.update` (defined at preload, called every frame; Essentials' own `Graphics.update`
   aliases chain so the hook survives) — not `TracePoint`; (3) under the console-suppressed Wine build
   `STDERR` is a bad file descriptor (writing raises `Errno::EBADF`), so route all logging to a
   guarded logfile (`Scripts/chrooked_load.log`). That logfile is also the verification oracle: make
   the plugin log the gate decision per cast, since in-game evasion setup is impractical and a 70%
   move's raw hit-counts are an unreliable oracle.
6. **Capture** BEFORE cleanup, and update the `references/README.md` row.
   - pokeemerald: `git -C <target> diff > references/<id>.<engine>-<version>.patch` — the patch must
     carry BOTH the mechanic edit AND the battle test (RED→GREEN).
   - essentials: copy the working plugin to `references/essentials-harness/chrooked_<id>.rb` (this is
     the install source `apply` reads). No `.patch`.
7. **Restore the target** (it is usually a keeper): `git -C <target> checkout -- <edited files>`,
   remove build/test artifacts (`pokeemerald.gba`, `*.elf`, `*.map`, `build/`).
8. **Surface for review.** Show the diff, the chosen [Seam](~/.claude/CONTEXT.md), the RED→GREEN
   result, and the per-acceptance-test argument. **Do not commit until the human approves** — this
   is the highest-stakes step (a subtly-wrong mechanic poisons playtesting silently).

## Subagent prompt template

> You are a behavior-port implementer. Implement ONE custom Pokémon battle mechanic into the fork
> at `<target>` (engine `<engine>`, version `<version>`), working ONLY from the spec packet below.
> Read the engine to find the idiomatic Seam — do not blindly copy any reference; a newer engine
> may centralize this differently.
>
> [paste the full packet here]
>
> Tasks: explore the relevant source; verify any vanilla part of the mechanic already exists and do
> not duplicate it; implement the custom part with a minimal, well-commented edit tagged
> `// chrooked:<id>`; gate it exactly as the spec says (mind attacker-vs-target ownership). For
> pokeemerald, ALSO author a battle test in `test/battle/.../<id>.c` — one `SINGLE_BATTLE_TEST` per
> acceptance case, using `PASSES_RANDOMLY(..., RNG_ACCURACY)` to make probabilistic cases
> deterministic; at least one test must FAIL without your mechanic (the RED discriminator). DO NOT
> compile and DO NOT edit unrelated files. Return: the function/Seam + file:line, the unified diff
> (`git -C <target> diff`), and a short argument for EACH acceptance test (especially that the
> effect does not leak to other moves or users).

## Honest limits

- **Runtime verification is engine-dependent.** pokeemerald runs the acceptance tests for real
  (`make check`, RNG-controlled). Essentials cannot run battles headlessly, so its ceiling is the
  log-oracle harness (`harness stage|verify <id>`): the verdict is automated and uniform, but a human
  still plays one debug battle to produce the log. The neutral prose `test_cases` are the portable
  Contract that feeds both; keep them concrete enough for a human tester.
- **On this machine** (WSL host, native Windows `Game.exe`): launch with
  `powershell.exe Start-Process -FilePath Game.exe -WorkingDirectory '<D: devcopy>' -ArgumentList debug`
  (or double-click `Play (Debug).bat` in the copy). NOT macOS `open`/`.command`, NOT `cmd /c start`
  (UNC-cwd error). The devcopy lives on the D: drive; see the `africanvs-target-env` memory.
- **A passing test on the clean engine is a red flag**, not a green light — it means the test does
  not exercise the mechanic. Always confirm RED before GREEN.
