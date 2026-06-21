# Install ported Essentials mechanics on apply + flip the DATA-ONLY boundary (#16)

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository keeps its ExecPlan format guide at `~/.claude/PLAN.md`; maintain this document in accordance with it. It builds on the completed harness (`feature_requests/essentials-harness-plan.md`, #15) and tracer (`feature_requests/essentials-behavior-tracer-plan.md`, #14); the facts needed from those are repeated here so this plan stands alone.

## Purpose / Big Picture

Right now, when you run `chrooked-pokedex apply --engine essentials` against the Africanvs game, any custom ability that has a behavior spec gets its **data** written (name, description) and then the report prints a loud `DATA ONLY: implement mechanic` line. That line is honest — the mechanic's battle code is NOT in the game — but it is a dead end: the tool has no way to resolve it, even after someone has actually written the mechanic.

After this change, that dead end closes for mechanics that have been ported. Issue #15 built two real Essentials ports as standalone plugin files — `references/essentials-harness/chrooked_innerfocus.rb` and `chrooked_kindle.rb` — each a `# chrooked:<id>`-tagged Ruby file that drops into the game's `Scripts/` folder and makes the mechanic fire in battle. This plan teaches `apply` to **install** those plugins into the target and to **stop** printing `DATA ONLY` for them — while still printing it, honestly, for every mechanic that has not been ported yet.

What you can do after this change that you could not before: run `apply --engine essentials` and watch a ported ability (say Kindle) land BOTH its data row AND its working battle plugin, with the report saying "mechanic installed" instead of "DATA ONLY"; meanwhile an unported custom ability still says "DATA ONLY". Then `harness verify <id>` confirms the just-installed mechanic actually works in a battle. The whole thing — packet → port → apply installs → harness verifies — becomes one documented, repeatable loop.

The hard rule this plan protects (the **honesty Invariant**): the `DATA ONLY` warning may only disappear when the mechanic is *genuinely installed in the game*. "The warning went quiet" must always mean "the plugin is really there," never "we stopped checking."

## Definitions (plain language)

- **Behavior spec** — an engine-neutral YAML under `ruleset/behaviors/<id>.yaml` describing a custom mechanic and its `test_cases`. `<id>` is the `chrooked_id` (e.g. `kindle`).
- **Plugin** — the ported Essentials implementation of one mechanic: a standalone Ruby file `Scripts/chrooked_<id>.rb` that the game auto-loads. The canonical copy lives in the repo at `references/essentials-harness/chrooked_<id>.rb`.
- **Target** — the on-disk Essentials game copy `apply` writes into. On this machine: the D:-drive devcopy registered in `targets.json` (`/mnt/d/Games/Pokemon FanGames/Pok-mon-Africanvs-Definitive-Edition - devcopy`). The game is Essentials **16.2** (dialect `essentials162`).
- **Apply Report** — the `applied` / `partial` / `blocked` record `apply` prints; it never silently drops anything.
- **DATA-ONLY boundary** — the spot in the applier that today prints `DATA ONLY: implement mechanic` for a created ability that has a behavior spec.

## Settled decisions (from the #16 grill — do not reopen)

- **Q6 — what marks a mechanic "ported"?** The plugin file `references/essentials-harness/chrooked_<id>.rb` exists in the repo. Deterministic, file-based, reviewable.
- **Q7 — what does apply do with it?** It INSTALLS it (copies the plugin into the target's `Scripts/`). Three honest outcomes, never silent: plugin present → **applied** (installed); absent → **still DATA ONLY**; present but the copy/verify fails → **partial/blocked** with a reason.
- **Q9 — copy or patch?** Copy the standalone file (an Essentials port is a new file, not in-place edits like pokeemerald's C). Intentional divergence from pokeemerald. Retire the legacy `references/innerfocus.essentials-16.2.patch`.
- **Q8 — what is "end-to-end"?** A documented loop reusing existing pieces (`behaviors` packet → port → `apply` installs → `harness stage`/`verify`, human plays one battle), not a new orchestrator command. The port-behavior skill ties it together, same as it does for pokeemerald.

## Context and Orientation

The deterministic apply path, by full path:

- `src/chrooked_pokedex/appliers/dispatch.py` — `route_apply(...)` picks the engine and (for Essentials) the dialect, then calls `_apply_essentials162(...)` (16.2, our target) or `_apply_essentials(...)` (v21). It imports the `_apply_*` helpers inline to avoid a `cli → dispatch → cli` import cycle — keep that.
- `src/chrooked_pokedex/cli.py` — holds the per-engine **category order** tuples (e.g. `_ESSENTIALS_CATEGORIES = ("moves", "create", "species", "learnset", "evolution", "type-chart")`) and the `_apply_essentials162` / `_apply_essentials` bodies that call each category's applier in order. Tier order is load-bearing: moves/abilities are created before species so new symbols register first. A new step is added at the END (after data exists), so it does not disturb that.
- `src/chrooked_pokedex/appliers/essentials162/ability_apply.py` — the **16.2** ability applier. `_create_row(...)` appends a new abilities.txt row and today reports `reason="created new ability — DATA ONLY; mechanic must be implemented in the target engine"`. This is the boundary to make plugin-aware for 16.2.
- `src/chrooked_pokedex/appliers/essentials/creation.py` — the **v21** equivalent (`_creation_reason`). Out of scope to flip (no v21-shaped plugins exist; Q1 said 16.2 first). It must keep printing DATA-ONLY honestly. Leave it.
- `src/chrooked_pokedex/report/report.py` — `ReportEntry(status, category, chrooked_id, symbol="", reason="", partial_fields=())` with `status` in `applied|partial|blocked`. The installer emits these.
- `ruleset/` is loaded by `Ruleset.load(dir)`; `ruleset.behaviors` is a dict keyed by `chrooked_id`; `ruleset.behavior_for(name)` maps an ability/move name to its spec (this is what the boundary uses today).
- `references/essentials-harness/` — the plugin home from #15: `chrooked_innerfocus.rb`, `chrooked_kindle.rb`, the loader `load_order_shim.rb`, `mkxp.json`, `chrooked_harness_probe.rb`, README. The installer reads `chrooked_<id>.rb` from here.
- The harness (#15): `src/chrooked_pokedex/behavior/harness.py` with `stage`/`verify <id>`. Reused unchanged to prove an installed mechanic works.

A subtlety to honor: the game also needs the **loader** (`mkxp.json` + `Scripts/load_order_shim.rb`) present, or a plugin in `Scripts/` is never executed. On the devcopy these already exist (placed in #15). For a fresh target they would not. The installer therefore must also ensure the loader assets are present (idempotent copy), or no installed plugin would run — installing a plugin into a target with no shim would be silently dead, violating the Invariant.

## Architecture Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Install mechanism | Copy `references/essentials-harness/chrooked_<id>.rb` → `<target>/Scripts/` | Q9 — additive standalone file; no patch wrapper. |
| Marker = "ported" | That source file exists | Q6 — deterministic, in version control. |
| Loader assets | Installer also ensures `mkxp.json` + `load_order_shim.rb` present (idempotent) | A plugin with no loader never runs — installing it would silently violate the Invariant. |
| Where it runs | A new apply step/category `behaviors`, LAST in the 16.2 order, after `create` | Data (the ability row) must exist first; a standalone file copy has no other ordering needs. |
| Scope | 16.2 (`essentials162`) only | Q1 — 16.2 first; v21 keeps honest DATA-ONLY (no v21 plugins). |
| Boundary reason | 16.2 ability create consults "is there a plugin?": yes → "created; mechanic installed (Scripts/chrooked_<id>.rb)"; no → unchanged DATA-ONLY | Q7 honesty outcomes. |
| Failure handling | Missing source → DATA-ONLY; present but copy/verify fails → `blocked`/`partial` entry, never silent | Q7 + the Apply-Report Invariant. |

## Milestones

### M1 — Behavior installer module (pure, hermetic)

Scope: a new module `src/chrooked_pokedex/appliers/essentials162/behavior_install.py` with a function that, given the ruleset, the target path, and the report, installs every ported plugin and records honest outcomes. Logic only — no CLI wiring yet, so it is unit-testable without a game.

What exists at the end: `install_behaviors(target, ruleset, report) -> set[Path]` that, for each behavior spec whose `references/essentials-harness/chrooked_<id>.rb` exists, copies it to `<target>/Scripts/chrooked_<id>.rb`, ensures the loader assets (`mkxp.json`, `Scripts/load_order_shim.rb`) are present, verifies the copied file is non-empty and tagged `# chrooked:<id>`, and adds a `ReportEntry(status="applied", category="behavior", chrooked_id=<id>, reason="mechanic installed (Scripts/chrooked_<id>.rb)")`. A source that is unreadable/empty/mistagged adds a `blocked` entry with the reason and copies nothing. A spec with no source file adds nothing (the create-time DATA-ONLY in M2 covers it).

Acceptance: `tests/test_behavior_install.py` (unit, hermetic, temp dirs) proves: (a) a present plugin is copied + reported `applied`; (b) a missing plugin yields no install and no crash; (c) a broken (empty/mistagged) plugin yields a `blocked` entry and no partial file; (d) the loader assets are ensured; (e) re-running is idempotent (no duplicate/erroring).

### M2 — Flip the boundary + wire the step into 16.2 apply

Scope: make the 16.2 ability-create reason plugin-aware, and run the installer as the last tier of `_apply_essentials162`. Add `behaviors` to `_ESSENTIALS162_CATEGORIES` (and the `--category` choices) and call `install_behaviors(...)` last in `_apply_essentials162`. In `essentials162/ability_apply.py::_create_row`, when a plugin source exists for the created ability's `chrooked_id`, change the reason from the DATA-ONLY string to `"created new ability; mechanic installed via Scripts/chrooked_<id>.rb"`; when it does not, keep the existing DATA-ONLY string verbatim.

What exists at the end: `apply --engine essentials --target <devcopy>` writes Kindle/Inner-Focus data, the report shows their abilities as installed (no DATA-ONLY), the plugin files are in the devcopy `Scripts/`, and a custom ability with no plugin still shows DATA-ONLY.

Acceptance: integration test (auto-skipped without a target) + a manual `apply` run on the devcopy. The report contains a `behavior`/`applied` line for innerfocus and kindle and NO `DATA ONLY` line for them; an unported custom ability (if present) still shows `DATA ONLY`. `<devcopy>/Scripts/chrooked_kindle.rb` exists after apply.

### M3 — Prove the honesty Invariant end-to-end (apply → harness)

Scope: prove that "no DATA-ONLY" really means "works." After M2 installs the plugins via `apply` (not hand-placed), run the #15 harness against the devcopy for both mechanics.

What exists at the end: starting from a devcopy whose `Scripts/` has NO chrooked plugins, a single `apply --engine essentials` installs them, and `harness verify innerfocus` + `harness verify kindle` pass (human plays the staged battles). This closes the loop: the applier put the mechanic in, and the harness independently confirms it fires.

Acceptance: with plugins removed from the devcopy, `apply --engine essentials` re-installs them; `harness stage`/`verify innerfocus` → 3/3 and `verify kindle` → 3/3 (manual battle, log oracle). Recorded with the log evidence.

### M4 — Document the loop + reconcile #15 leftovers

Scope: make the loop runnable cold and clean up. Extend `.claude/skills/port-behavior/SKILL.md` Essentials arm with the full loop (packet → port → `apply` installs → `harness verify`) and the "ported = plugin file in `references/essentials-harness/`" + apply-installs convention. Retire the legacy `references/innerfocus.essentials-16.2.patch` (superseded by the harness plugin per Q9; the pokeemerald patch stays). Update `references/README.md` inventory to the file-copy model and mark innerfocus + kindle as installed-on-apply.

Acceptance: static review — SKILL documents the end-to-end loop + the apply-install step; `references/innerfocus.essentials-16.2.patch` is gone; README reflects the file-copy convention and both mechanics.

## File Changes

### New Files
- `src/chrooked_pokedex/appliers/essentials162/behavior_install.py` — the installer (M1).
- `tests/test_behavior_install.py` — hermetic installer tests (M1).

### Modified Files
- `src/chrooked_pokedex/cli.py` — add `behaviors` to `_ESSENTIALS162_CATEGORIES` + `--category` choices; call `install_behaviors(...)` last in `_apply_essentials162` (M2).
- `src/chrooked_pokedex/appliers/essentials162/ability_apply.py` — plugin-aware create reason (M2).
- `.claude/skills/port-behavior/SKILL.md` — document the loop + apply-install (M4).
- `references/README.md` — file-copy convention + inventory (M4).
- `feature_requests/essentials-behavior-port-throughline.md` — control file (ACs/stage).

### Deleted Files
- `references/innerfocus.essentials-16.2.patch` — retired per Q9 (M4).

## Data & API Changes

No Ruleset schema or web API changes. One new CLI apply category value `behaviors` (16.2). The installer writes engine files (`Scripts/chrooked_*.rb`, and loader assets if absent) into the target — `apply` already requires a clean target git tree (`git_guard`) unless `--force`.

## Validation and Acceptance

Run from the repo root. The integration/manual steps need the devcopy (machine-specific; auto-skipped where absent). Launch on this machine: `powershell.exe Start-Process -FilePath Game.exe -WorkingDirectory '<D: devcopy>' -ArgumentList debug` (or `Play (Debug).bat`).

### Manual Verification Steps

1. Remove the chrooked plugins from the devcopy `Scripts/` (simulate a fresh target): delete `Scripts/chrooked_innerfocus.rb` and `Scripts/chrooked_kindle.rb`.
2. `chrooked-pokedex apply --engine essentials --target "<devcopy>"` (or `--force` if the tree is dirty). Expect the report to show innerfocus + kindle as `behavior`/`applied` ("mechanic installed"), NOT DATA-ONLY, and the two plugin files to reappear in `Scripts/`.
3. `PYTHONPATH=src python -m chrooked_pokedex.behavior.harness stage innerfocus`, play the battle, `verify innerfocus` → 3/3 PASS. Same for `kindle`.
4. Confirm an unported custom ability (a behavior spec with no plugin file) still reports `DATA ONLY` in the same apply run.

### Expected report excerpt (illustrative)

        | status  | category | chrooked_id | symbol      | reason |
        | applied | behavior | kindle      | KINDLE      | mechanic installed (Scripts/chrooked_kindle.rb) |
        | applied | behavior | innerfocus  | INNERFOCUS  | mechanic installed (Scripts/chrooked_innerfocus.rb) |
        | applied | ability  | someunported| SOMEUNPORT  | created new ability — DATA ONLY; mechanic must be implemented in the target engine |

## Testing Plan

### Unit Tests
- `test_behavior_install.py`: present→copied+applied; missing→no-op; broken(empty/mistagged)→blocked; loader assets ensured; idempotent re-run. (hermetic, temp dirs)
- A focused test that `_create_row`'s reason is plugin-aware: given a fake references dir with/without the plugin, the created-ability reason flips between "installed" and DATA-ONLY.

### Integration Tests
- `apply --engine essentials` against a temp copy or the devcopy (marker `integration`, auto-skipped when absent): report shows installed behaviors + plugins on disk.

### E2E
- M3 manual: apply-installs → harness verify innerfocus + kindle pass.

## Idempotence and Recovery

The installer copies files and is safe to re-run (overwrites with the same canonical source; loader assets copied only if absent). It writes only `Scripts/chrooked_*.rb` and (if missing) the loader assets. Recovery from a bad install: delete the plugin and re-apply, or `git checkout`/restore the target. Never repack the binary `Scripts.rxdata`. `apply`'s clean-tree guard still protects the target.

## Progress

- [x] (2026-06-21) M1 — `behavior_install.py` (`install_behaviors`, `has_plugin`) + `tests/test_behavior_install.py` 7/7 (present→applied, missing→noop, empty/mistagged→blocked, loader ensured, idempotent, has_plugin marker).
- [x] (2026-06-21) M2 — `essentials162/ability_apply.py::_create_row` plugin-aware (installed vs DATA-ONLY); `behaviors` tier wired last into `_apply_essentials162` + added to `--category` choices + `_ESSENTIALS162_CATEGORIES`. Full suite 620 passed / 15 skipped under `.venv` (py3.14).
- [~] M3 — DONE except one runtime re-check. Live on devcopy: removed plugins + KINDLE row; `apply --category abilities` recreated KINDLE with reason "created new ability; mechanic installed via Scripts/chrooked_kindle.rb" (flip proven); `apply --category behaviors` installed both plugins (report behavior/applied) + loader assets; installed files byte-identical to the #15-proven sources. REMAINING (AC4): a post-apply `harness verify` runtime re-check (human battle) to confirm the apply-installed plugin fires.
- [x] (2026-06-21) M4 — SKILL Essentials arm documents apply-install + the full loop + capture-as-plugin; legacy `references/innerfocus.essentials-16.2.patch` retired (Q9); `references/README.md` updated to the two-model (patch vs plugin) + kindle row.

## Surprises & Discoveries

- Observation: A plugin needs the loader (`mkxp.json` + `load_order_shim.rb`) to run at all; installing a plugin into a target without it would be silently dead.
  Evidence: #15 M0 — `[LOAD_ORDER_SHIM] active` is the gate that makes `Scripts/chrooked_*.rb` load. Folded into M1 (installer ensures loader assets).

## Decision Log

- Decision: Scope the boundary flip + install to the 16.2 (`essentials162`) path; leave v21 (`essentials/creation.py`) printing DATA-ONLY.
  Rationale: Q1 said 16.2 first; the #15 plugins are 16.2-shaped (`PokeBattle_Move`, external `Scripts/`). v21 has no ports, so DATA-ONLY there is still honest.
  Date/Author: 2026-06-21 / plan (#16)
- Decision: Installer also ensures loader assets, not just the plugin.
  Rationale: a plugin with no shim never executes — installing it alone would quietly violate the honesty Invariant.
  Date/Author: 2026-06-21 / plan (#16)
- Decision: New apply step `behaviors`, run last in the 16.2 tier order.
  Rationale: the ability data row must exist first; a standalone file copy needs no earlier ordering.
  Date/Author: 2026-06-21 / plan (#16)

## Outcomes & Retrospective

- (pending)

## Code Review Findings

### High Risk

### Medium Risk

### Low Risk
