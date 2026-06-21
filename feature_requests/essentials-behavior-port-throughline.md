---
issue: 12
sub_issues: [14, 15, 16]
active_sub_issue: 15
stage: prove
status: in_progress
grillable: false
tier: heavy
effort: high
next_action: "/commit #15 (all 5 ACs pass), then close #15 + scope #16 (drive loop, flip DATA-ONLY)"
exec_plan: feature_requests/essentials-harness-plan.md
acceptance_criteria:
  - id: AC1
    statement: A D:-drive dev-copy is created/registered on this WSL+native-Windows machine with the preload path confirmed, and the oracle route is settled — a headless PokeBattle_Battle either boots (Route A) or is documented-infeasible with the log-oracle (Route B) chosen.
    proof_method: "boot the new dev-copy (Game.exe via WSL interop); Scripts/chrooked_load.log shows [LOAD_ORDER_SHIM] active AND either 'battle-boot OK' or a captured failure; Decision Log records the route with that evidence"
    status: pass  # devcopy created+registered; log shows [LOAD_ORDER_SHIM] active + glob-loader + PokeBattle_Battle arity=5 -> Route B (log oracle) chosen
  - id: AC2
    statement: A generic runner executes any mechanic's neutral test_cases and prints PASS/FAIL per case, with no mechanic-specific code in the runner.
    proof_method: "harness run innerfocus -> 3/3 PASS (tracer mechanic re-proved through the NEW runner) + grep shows the runner file has no innerfocus/focusblast literals"
    status: pass  # verify innerfocus -> 3/3 PASS through generic harness.py; grep clean (literals only in docstrings); 4/4 hermetic unit tests
  - id: AC3
    statement: A second mechanic (hitting a different Seam than innerfocus) runs through the unchanged runner and passes.
    proof_method: "harness run <mechanic2> -> its test_cases PASS; git diff shows the runner unchanged between M1 and M2 (only a new plugin + scenario added)"
    status: pass  # kindle (pbModifyDamage Seam, != innerfocus accuracy Seam) -> verify kindle 3/3 PASS; harness.py untouched (only chrooked_kindle.rb + scenarios.py entry + KINDLE PBS row added)
  - id: AC4
    statement: Failures report which spec and which test_case failed, readably.
    proof_method: "M3 break-and-restore: flip the mechanic2 gate, harness run -> a FAIL line naming the spec + failing case; restore -> green"
    status: pass  # readable FAIL shown organically (live 'FAIL kindle :: ...Surf... (not observed)') + hermetic test_fail_when_delta_leaks_to_other_move (expected/observed); both failure modes covered
  - id: AC5
    statement: The harness is documented for reuse so #16 can drive it cold.
    proof_method: "static: .claude/skills/port-behavior/SKILL.md Essentials arm names the harness command + the add-a-mechanic steps (plugin -> scenario -> harness run)"
    status: pass  # SKILL Essentials arm now documents harness stage|verify, the OBS-format -> scenario add-a-mechanic steps, glob-loader, references/essentials-harness/ home, and the WSL/Windows launch line

# --- Closed: #14 tracer (innerfocus, AC1-AC5 all proved). Proof record lives in
# feature_requests/essentials-behavior-tracer-plan.md (Progress M0-M3 + Outcomes) and git d2785b9. ---
---

# Essentials behavior-mechanic porting — Throughline

Mirror the completed pokeemerald behavior track (Slices 1–3) for Essentials
(Africanvs / 16.2 first). Spec layer, packet rendering, and Wine debug loop
already exist and are reused. Missing: the `port-behavior` path for `--engine
essentials`, a reference library, and a verification gate.

## Decision Ledger

- **[RESOLVED] Q1 — Where does ported Essentials code live + how applied?**
  Choice: **A — external plugin `.rb` files**, one per mechanic, tagged
  `# chrooked:<id>`, captured as text `.patch` (mirrors pokeemerald cache).
  Rationale: only option that preserves the proven text-patch/cache
  architecture; forward-compatible with v21 `Plugins/` autoload. Tracer's first
  job is to settle the Wine mkxp-z autoload caveat (AC3); fall back to the
  PBS+Ruby-handler hybrid (option C) only if autoload genuinely fails — never
  hand-edit the binary `Scripts.rxdata`.

- **[RESOLVED] Q2 — Verification gate for an Essentials port.**
  Choice: **B3 — staged.** Tracer (#14) gates on a **manual playtest
  checklist** in the Africanvs debug battle (test_cases as numbered checks),
  honestly labeled — never claim runtime verification we didn't run. #15 then
  attempts a **headless Ruby battle harness** (instantiate `Battle`, assert on
  outcomes) for real RED→GREEN later. The tracer is not held hostage to building
  a test runner. Accepted caveat: the human is the test oracle for the tracer,
  so the first mechanic must be simple enough to eyeball (see Q3).
- **[RESOLVED] Q3 — First tracer mechanic.**
  Choice: **`innerfocus`.** Only mechanic with an Essentials `engine_hint`
  already authored (`Battle::Move#pbAccuracyCheck`) AND a proven pokeemerald
  twin, so any failure isolates to the new Essentials path, not the spec. Oracle
  is binary (Focus Blast hits at +6 evasion, yes/no) — easiest manual check. The
  vanilla overlap is intentional: forces the agent to port only the custom delta
  (Focus-Blast-always-hit) and not duplicate vanilla Inner Focus no-flinch — the
  realistic steady-state for every future port.
- **[RESOLVED] Q4 — How `port-behavior` generalizes to `--engine essentials`.**
  Choice: **D1 — extend the one skill** with an Essentials arm, not a separate
  skill. Shared scaffolding (cache-first flow, `references/<id>.essentials-16.2.patch`
  naming, text-patch capture, restore discipline, packet rendering) is reused.
  New content, all pre-decided: (1) Essentials subagent prompt → idiomatic Ruby
  Seam (`pbAccuracyCheck`), `# chrooked:<id>`-tagged plugin `.rb`, port only the
  custom delta; (2) autoload-resolution step (tracer's first job, Q1); (3)
  manual-checklist verify branch (Q2, already in SKILL). Mirrors how packet
  rendering already serves both engines from one path.

- **[RESOLVED] Q5 (#15) — Which second mechanic proves harness generality?**
  Choice: **`kindle`** (1.5x Fire damage when ability is Kindle). Hits a
  *different* Seam than innerfocus — damage calc, not accuracy — so a pass proves
  the runner is general, not innerfocus-shaped. Binary and log-observable.
  Date/Author: 2026-06-21 / plan approval (#15)

## Plan Walkthrough — #15 (active)

ExecPlan: `feature_requests/essentials-harness-plan.md`. Scope is the
generalized acceptance-test harness (#15). Turn the tracer's one-off
human-read log line into a reusable runner: `harness run <mechanic-id>` prints
PASS/FAIL per neutral `test_case`, proven on innerfocus **and** a second
mechanic. Four milestones, dependency-ordered:

- **M0** — Create + register a D:-drive dev-copy on this WSL/native-Windows
  machine (no dev-copy exists yet; `Game.exe` launches via WSL interop, not
  Wine) and confirm the preload/autoload path holds. Then spike whether a
  headless `PokeBattle_Battle` boots (Route A); fallback is the proven
  generalized log oracle (Route B). The harness Surface is identical either way,
  so nothing downstream branches.
- **M1** — Generic runner + Python driver (`src/chrooked_pokedex/behavior/harness.py`);
  re-prove innerfocus 3/3 *through the new runner*; runner free of innerfocus
  literals.
- **M2** — Second mechanic (proposed `kindle`, a damage-calc Seam) through the
  unchanged runner → PASS. Proves generality.
- **M3** — Break-and-restore proves readable FAIL lines; extend the
  `port-behavior` SKILL Essentials arm with the harness command + add-a-mechanic
  steps.

Open decision carried to approval: the second mechanic (Q5 below).

## Plan Walkthrough — #14 tracer (closed)

ExecPlan: `feature_requests/essentials-behavior-tracer-plan.md`. Scope is the
tracer (#14) only. Four milestones, dependency-ordered:

- **M0** — Boot Africanvs debug; confirm loose external `.rb` plugins load
  (`[LOAD_ORDER_SHIM] active`). The one empirical unknown; fallback is the
  PBS-FunctionCode + Ruby-handler hybrid if the Wine build won't autoload.
- **M1** — `/port-behavior innerfocus --engine essentials --target <copy>`;
  subagent writes `Scripts/chrooked_innerfocus.rb` overriding `pbAccuracyCheck`
  for the Focus-Blast-always-hit delta only (no vanilla no-flinch touch).
- **M2** — Manual debug-battle checklist proves the 3 test_cases (hit 5/5,
  Hydro Pump can miss, non-Inner-Focus ~70%).
- **M3** — Capture `references/innerfocus.essentials-16.2.patch`, add the README
  row, extend the skill's Essentials arm with the code-home + version-string.

## Resolved approach (summary)

Mirror pokeemerald Slices 1–3 for Essentials by **extending** the existing
`port-behavior` skill. Ported mechanics live as external `# chrooked:<id>`
plugin `.rb` files captured as text patches; the tracer ports **innerfocus**
(custom Focus-Blast-always-hit delta) into Africanvs, gated on a **manual**
debug-battle checklist. Sub-issue map: #14 tracer (innerfocus end-to-end +
settle the Wine autoload caveat), #15 headless Ruby harness for real RED→GREEN,
#16 drive the port loop + flip the DATA-ONLY boundary.
