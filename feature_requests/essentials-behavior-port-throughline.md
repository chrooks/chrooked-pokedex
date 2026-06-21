---
issue: 12
sub_issues: [14, 15, 16]
stage: prove
status: in_progress
grillable: false
tier: heavy
effort: high
next_action: /commit (mechanic proven in-game)
exec_plan: feature_requests/essentials-behavior-tracer-plan.md
acceptance_criteria:
  - id: AC1
    statement: A loose external Ruby plugin loads and executes in the Africanvs Wine debug build (autoload caveat settled, or documented fallback in force).
    proof_method: "manual: boot debug via scripts/africanvs_devloop.sh --no-apply; observe [LOAD_ORDER_SHIM] active (or a # chrooked debug print on the fallback route) in the mkxp-z console"
    status: pass  # log shows [LOAD_ORDER_SHIM] active + installed on PokeBattle_Move
  - id: AC2
    statement: The custom innerfocus delta works — an Inner Focus user's Focus Blast always hits a +6-evasion foe.
    proof_method: "manual debug battle: Focus Blast hits 5/5 vs a +6-evasion foe (misses without the plugin) + static review that the override gates on the user's ability AND move==Focus Blast"
    status: pass  # log oracle: Lucario(InnerFocus) Focus Blast x3 -> ALWAYS-HIT
  - id: AC3
    statement: The effect does not leak and vanilla survives — user's other moves use normal accuracy, a non-Inner-Focus user's Focus Blast uses normal accuracy, vanilla no-flinch untouched.
    proof_method: "manual debug battle: (a) Inner Focus user's Hydro Pump can miss at +6 evasion; (b) non-Inner-Focus Focus Blast ~70% accuracy + static review that chrooked_innerfocus.rb adds no no-flinch code"
    status: pass  # log oracle: Pidgeotto(no InnerFocus) Focus Blast x3 -> normal accuracy; move-id gate structurally excludes other moves; plugin touches only pbAccuracyCheck
  - id: AC4
    statement: The port is captured as a reusable, deterministically re-appliable reference.
    proof_method: "references/innerfocus.essentials-16.2.patch exists and git apply --check succeeds on a clean copy; references/README.md has the inventory row"
    status: pass  # patch authored, git apply --check OK on clean dir, README row added
  - id: AC5
    statement: The next Essentials port is mechanical — the skill documents the code home and version string.
    proof_method: "static: .claude/skills/port-behavior/SKILL.md contains the external-Scripts/ code-home convention and the essentials-16.2 version-string source"
    status: pass  # SKILL Essentials arm extended with code-home + version-string + 16.2 gotchas
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

## Plan Walkthrough

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
