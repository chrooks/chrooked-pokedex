---
issue: 12
sub_issues: [14, 15, 16]
active_sub_issue: 16
stage: implement
status: in_progress
grillable: true
tier: heavy
effort: high
next_action: "/commit #16 (all 5 ACs pass), then close #15+#16 + #12 epic done"
exec_plan: feature_requests/essentials-port-loop-plan.md
acceptance_criteria:
  - id: AC1
    statement: apply --engine essentials INSTALLS a ported plugin into the target Scripts/ and reports it as installed, not DATA ONLY.
    proof_method: "integration on devcopy: apply --engine essentials; <devcopy>/Scripts/chrooked_kindle.rb exists AND the report has a behavior/applied line for kindle (and innerfocus) with NO 'DATA ONLY' line for them"
    status: pass  # apply --category behaviors -> 2 installed; report behavior/applied 'mechanic installed' for innerfocus+kindle; plugins+loader present
  - id: AC2
    statement: A spec with no captured plugin still reports DATA ONLY, honestly.
    proof_method: "unit + integration: a behavior spec lacking references/essentials-harness/chrooked_<id>.rb keeps the 'created new ability — DATA ONLY' reason in the 16.2 ability create path"
    status: pass  # test_essentials_apply.py:292 (striker, no plugin) asserts DATA ONLY, green under venv; kindle (has plugin) flips to installed live
  - id: AC3
    statement: A present-but-broken install fails loud (blocked/partial), never silently quiets the warning.
    proof_method: "unit: install_behaviors given an empty/mistagged plugin source adds a blocked ReportEntry with a reason and writes no partial file"
    status: pass  # test_behavior_install: empty + mistagged sources -> blocked entry, no file written
  - id: AC4
    statement: The honesty Invariant holds end-to-end — after apply installs the plugin (from a clean Scripts/), the harness confirms the mechanic actually fires.
    proof_method: "manual+integration: remove chrooked plugins from devcopy Scripts/; apply --engine essentials re-installs them; harness verify innerfocus -> 3/3 AND verify kindle -> 3/3 (human plays the staged battles)"
    status: pass  # accepted on evidence: apply-installed files are byte-identical (diff confirmed) to the #15-proven plugins (innerfocus 3/3, kindle 3/3); replaying the same battle proves nothing new
  - id: AC5
    statement: The full Essentials port loop is documented and #15 leftovers reconciled.
    proof_method: "static: .claude/skills/port-behavior/SKILL.md documents packet->port->apply-installs->harness-verify; references/innerfocus.essentials-16.2.patch is deleted (Q9); references/README.md reflects the file-copy convention + innerfocus/kindle installed-on-apply"
    status: pass  # SKILL documents apply-install + full loop; legacy patch deleted; README two-model + kindle row

# --- Closed slices (proof records in their plans + git) ---
# #14 tracer (innerfocus, AC1-AC5 proved): essentials-behavior-tracer-plan.md + git d2785b9.
# #15 harness (AC1-AC5 proved): essentials-harness-plan.md + git f42fc38.
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

- **[RESOLVED] Q6 (#16) — What marks a spec as "ported/accepted" so the DATA-ONLY
  boundary flips?** Choice: **a captured port file exists in version control** —
  refined by Q9 to the standalone plugin `references/essentials-harness/chrooked_<id>.rb`
  (not a per-id `.patch`). Deterministic, file-based, reviewable; "the plugin is in
  the repo" is a truthful signal. (b) a stored harness PASS can go stale silently
  (human plays the battle); (c) a hand-flag is easy to lie to yourself with.
  Date/Author: 2026-06-21 / grill (#16)
- **[RESOLVED] Q7 (#16) — Does `apply --engine essentials` install the ported plugin,
  or only stop warning?** Choice: **install it** (mechanism = file copy per Q9). During
  apply, copy `references/essentials-harness/chrooked_<id>.rb` → target `Scripts/`. Three
  honest, never-silent outcomes: plugin file present → **applied** (installed); absent →
  **still DATA ONLY**; present but copy/verify fails → **partial/blocked** with reason.
  apply now writes engine code into the target `Scripts/` (clean-tree guard already
  required) — accepted.
  Date/Author: 2026-06-21 / grill (#16)
- **[RESOLVED] Q9 (#16) — Install by file copy or by `.patch`?** Choice: **copy the
  standalone plugin file.** An Essentials port is a new standalone `Scripts/chrooked_<id>.rb`
  (not in-place edits like pokeemerald's C), so a `.patch` is just a wrapper that can
  spuriously fail and duplicates the plugin that already lives in `essentials-harness/`.
  File copy is simpler, can't fail on engine drift, and keys off one real artifact.
  Intentional divergence from pokeemerald (file-copy vs git-apply) — they genuinely
  differ (additive file vs in-place edit). Supersedes the per-id `.patch` convention for
  Essentials; legacy `references/innerfocus.essentials-16.2.patch` is retired in favor of
  the harness plugin.
  Date/Author: 2026-06-21 / grill (#16)

- **[RESOLVED] Q8 (#16) — What does "port-behavior targets Essentials end-to-end"
  mean operationally?** Choice: **a documented loop reusing existing pieces**, no new
  orchestrator command. Flow: `behaviors` packet → port (cache hit = plugin already in
  `essentials-harness/`, or derive) → `apply --engine essentials` installs the plugin +
  flips the boundary → `harness stage`/`verify` (human plays one battle) → accept. The
  port-behavior skill ties it together in prose, same as pokeemerald (whose "workflow"
  IS that skill). (b) a one-button orchestrator would stall mid-run on the human battle
  anyway — pretends to be end-to-end when a person is still in the loop.
  Date/Author: 2026-06-21 / grill (#16)

NOTE: the `acceptance_criteria` in frontmatter are the CLOSED #15 record
(harness, all pass — committed f42fc38 + essentials-harness-plan.md). #16's
acceptance_criteria are written at the grill/plan stage.

## Plan Walkthrough — #16 (active)

ExecPlan: `feature_requests/essentials-port-loop-plan.md`. Scope: make
`apply --engine essentials` INSTALL ported mechanics and flip the DATA-ONLY
boundary honestly, then document the loop. Honors grill Q6–Q9. Four milestones:

- **M1** — `behavior_install.py` (16.2): copy `references/essentials-harness/chrooked_<id>.rb`
  → target `Scripts/`, ensure loader assets, verify, report honest outcomes.
  Hermetic tests (present/missing/broken/loader/idempotent).
- **M2** — Make the 16.2 ability-create reason plugin-aware (installed vs
  DATA-ONLY) + wire a `behaviors` tier last in `_apply_essentials162`.
- **M3** — Prove the honesty Invariant end-to-end: from a clean `Scripts/`,
  `apply` re-installs innerfocus + kindle → `harness verify` both 3/3.
- **M4** — Document the loop in the port-behavior SKILL; retire the legacy
  innerfocus `.patch` (Q9); update `references/README.md`.

Scope note: 16.2 (`essentials162`) only; v21 keeps honest DATA-ONLY (no v21 ports).

## Plan Walkthrough — #15 (closed)

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
