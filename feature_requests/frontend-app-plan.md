# Build the chrooked-pokedex frontend: browse, edit, and apply the Ruleset from a local web app

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with the ExecPlan rules in `/Users/cdbrooks/.claude/PLAN.md`. If that file is not in context, read it in full before revising this plan. It builds on `plans/chrooked-pokedex-plan.md` (the backend, all seven milestones complete) and the project Lexicon in `CONTEXT.md`; key terms are restated below so this plan stands alone.


## Purpose / Big Picture

Today everything Chris does with his Ruleset happens at a command line: `seed` to derive it, `apply` to write it into a game, `harvest` to pull tuning back, `behaviors` to print a mechanic packet. There is no way to *see* his Pokémon changes as a Pokédex, and editing a change means hand-editing YAML.

After this change Chris runs one command — `chrooked-pokedex ui` — and a browser opens to a local app where he can:

1. **Browse a Canon dex**: the full national Pokédex with his Ruleset merged on top, so Goodra shows as Water/Dragon with Poison Heal and a learnset that cites Excalibur, while Pikachu shows unchanged base values. Overridden fields are visibly flagged.
2. **CRUD his Ruleset**: create, edit, and delete species overrides, owned moves, owned abilities, type-chart overrides, and behavior specs — through typed forms that validate before they save. Saving writes YAML to `ruleset/`; he reviews `git diff` and commits himself.
3. **Apply to a Target he picks**: register his games (a pokeemerald Fork or a Pokémon Essentials fangame) once, then select one, see a no-write **preview** of exactly what apply will do (applied / partial / blocked / created), and run the real apply — surfacing the Apply Report and any DATA-ONLY behavior warnings.

You can see it working when, from the repo root, `chrooked-pokedex ui` serves a FastAPI backend and a React app at a localhost URL; the dex grid renders ~900 species with sprites; editing Goodra's Speed and saving changes `ruleset/species/goodra.yaml` (visible in `git diff`); and selecting a registered Target shows a preview whose counts match a subsequent real apply's Apply Report.


## Terms (plain language — this plan stands alone)

- **Ruleset**: the engine-neutral source of truth, a folder of YAML under `ruleset/` describing Chris's preferred Pokémon changes in plain names (`Water`, `Poison Heal`). It stores *only overrides* (fields that differ from base), except learnsets, which are stored whole.
- **Override**: one changed field relative to base. The Ruleset has a species file only for species that changed at least one field.
- **chrooked_id**: a short stable slug (`goodra`, `excalibur`) that identifies a thing across engines; the join key.
- **Applier**: a program that writes the Ruleset into one engine's files. Two exist: pokeemerald (writes C) and essentials (writes PBS text). They live in `src/chrooked_pokedex/appliers/{pokeemerald,essentials}/`.
- **Apply Report**: the classified output of an apply run — every entry is `applied`, `partial` (landed but a referenced field could not), or `blocked` (whole entry could not land). Produced by `src/chrooked_pokedex/report/`. Written as `apply-report.md` plus a JSON sidecar into the Target.
- **Fork**: a copy of pokeemerald-expansion with changes layered on (e.g. `dreamstone-mysteries`).
- **Target**: a specific game on disk an Applier writes into — a Fork (pokeemerald engine) or an Essentials fangame (essentials engine). Every Target carries an engine. The CLI calls this `--target`.
- **Target registry**: the managed list of known Targets the frontend picks from — label + path + engine, registered once and reused. The frontend's "explorer" is this registry, not a raw filesystem browser. Stored as a gitignored local JSON file because the paths are machine-specific, not canon.
- **Canon dex**: the full national Pokédex as the Ruleset sees it — the committed base 1.11.2 snapshot with the Ruleset's overrides merged on top. Game-independent; always renders.
- **Per-Target preview**: a Target's own current data with the Ruleset previewed on top — a no-write dry run of an apply, showing resulting values and each entry's apply status. Computed by apply-then-revert (see Architecture Decisions and `docs/adr/0001-apply-then-revert-dry-run.md`).
- **Behavior spec**: the human-owned mechanic layer (under `ruleset/behaviors/`) describing what a custom ability/move *does*, as neutral triggers plus given/expect test cases. Kept apart from the machine-owned data the seed regenerates.


## Context and Orientation

The backend is a complete, tested Python package, `chrooked_pokedex`, installed editable into `.venv` (`pip install -e ".[dev]"`, `pytest` green). Its shape:

- `src/chrooked_pokedex/model/` — frozen dataclasses (`schema.py`), the YAML loader with fail-fast validation (`loader.py`), and `Ruleset.load(dir)` (`ruleset.py`). **This is the validation Boundary. Every write the frontend makes must round-trip through `loader` so a bad edit is rejected, not silently saved.**
- `src/chrooked_pokedex/readers/pokeemerald/` — parsers that read a fork's C into dataclasses.
- `src/chrooked_pokedex/seed/` — derives the Ruleset by diffing a fork against base; `seed/writer.py` emits the canonical YAML formatting.
- `src/chrooked_pokedex/appliers/{pokeemerald,essentials}/` — the two Appliers and their resolution maps; `git_guard.py` enforces a clean Target tree.
- `src/chrooked_pokedex/report/` — the Apply Report (md + json).
- `src/chrooked_pokedex/harvest/` — gated reverse sync.
- `src/chrooked_pokedex/cli.py` — argparse CLI with `seed`, `apply`, `harvest`, `behaviors`.
- `ruleset/` — the YAML source of truth: `species/`, `moves/`, `abilities/`, `type-chart/overrides.yaml`, `behaviors/`, `meta.yaml`. Seeded from `dreamstone-mysteries` against base 1.11.2 (758 species, 216 learnsets, 45 owned moves, 57 owned abilities, 7 type-chart overrides).

The frontend adds two new top-level areas: a Python web layer (`src/chrooked_pokedex/web/`, a FastAPI app that imports the existing modules) and a React single-page app (`frontend/`, built with Vite). A new `ui` CLI subcommand starts the server. No existing module is rewritten; the web layer is a thin Interface over the core.

Critical existing facts this plan relies on:

- The Ruleset never invents a *species* — `schema.py` has `SpeciesOverride` but no "new species" type. So every Canon dex entry is an existing national-dex slot with a dex number (kept in `aka.dex` even when renamed). Sprites keyed by dex number therefore never gap.
- `ruleset.py` documents the ownership Boundary: `behaviors/` is human-owned; species/moves/abilities/type-chart are "machine-owned data the seed regenerates." A re-seed overwrites UI edits to the machine-owned kinds. The UI must show this as honest friction; it does not try to prevent re-seed.
- `apply` already requires a clean git tree on the Target (`appliers/pokeemerald/git_guard.py`), bypassable with `--force`. The preview engine leans on this.


## Architecture Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| App shape | Local FastAPI + React (Vite); FastAPI imports `chrooked_pokedex.*` | Reuses all validation/applier logic; richest path for a visual dex; seed/apply/harvest need local filesystem + git + Python, so nothing is deployable |
| Dex meaning | Both — Canon dex first, per-Target preview as a second backdrop on one grid | "Applied" means base ⊕ Ruleset; the two bases (1.11.2 vs a chosen game) are different features sharing one grid |
| Base source | Committed base snapshot JSON, generated from pinned 1.11.2 | Deterministic, fast, no dependency on the deletable `../ROMs/_scratch-expansion-1.11.2` worktree; regenerate only when the pin moves |
| Write model | Write → reload-validate → user commits | Loader is the gate; `git diff` is the review; UI never touches git; matches the solo-main workflow |
| CRUD scope | All five kinds writable | Behaviors especially have no other editor; the others are small |
| Target picker | Target registry (gitignored local JSON) | A browser SPA cannot use a native file picker; registration gives each Target a stable identity that also powers the preview backdrop |
| Dry-run engine | Apply-then-revert via git | The preview *is* apply, so it cannot drift; safe because a clean tree is already required. See `docs/adr/0001-apply-then-revert-dry-run.md` |
| Sprites | PokéAPI sprite CDN, by national dex number, browser-cached | Reliable since the Ruleset never invents a species; zero bundled artwork; no asset pipeline |
| Sequencing | S1 Canon dex (read) → S2 CRUD all five → S3 Targets + preview + apply | Dependency-forced: the base ⊕ Ruleset merge is the spine both CRUD and preview hang off |


## File Changes

### New Files

- `src/chrooked_pokedex/web/__init__.py` — marks the web package.
- `src/chrooked_pokedex/web/app.py` — the FastAPI application factory; mounts routers and (in production mode) the built React assets.
- `src/chrooked_pokedex/web/dex.py` — builds the Canon dex (base snapshot ⊕ Ruleset) and the merge/flag logic shared with preview.
- `src/chrooked_pokedex/web/snapshot.py` — generates and loads the committed base snapshot JSON via the existing readers.
- `src/chrooked_pokedex/web/crud.py` — write endpoints for all five kinds; each writes YAML via `seed/writer.py` helpers, then reloads through `loader` to validate.
- `src/chrooked_pokedex/web/targets.py` — Target registry CRUD (the gitignored JSON) and per-Target preview (apply-then-revert) and real apply, wrapping the existing appliers + report.
- `ruleset/.base/1.11.2.json` — the committed base snapshot (species/moves/abilities/type-chart at base 1.11.2, keyed for merge). Committed; regenerated only on pin change.
- `frontend/` — the Vite + React app: `package.json`, `index.html`, `src/main.tsx`, `src/App.tsx`, components for the dex grid, species/move/ability/type-chart/behavior editors, the Target registry, and the preview/apply panel.
- `docs/adr/0001-apply-then-revert-dry-run.md` — already written; the dry-run-engine ADR.

### Modified Files

- `src/chrooked_pokedex/cli.py` — add a `ui` subcommand that builds (or assumes a build of) the frontend and runs the FastAPI server.
- `pyproject.toml` — add web dependencies (`fastapi`, `uvicorn`) under an extra, e.g. `[project.optional-dependencies] web`.
- `.gitignore` — ignore the Target registry JSON (e.g. `.chrooked/targets.json`) and `frontend/node_modules`, `frontend/dist`.
- `README.md` — document `chrooked-pokedex ui` and the snapshot regeneration step.

### Deleted Files

- None.


## Data & API Changes

The FastAPI layer exposes a small REST surface (all local, single-user; no auth). Shapes mirror the existing dataclasses, serialized to JSON.

- `GET /api/dex` — the Canon dex: a list of entries `{ dex, chrooked_id, name, types, abilities, stats, learnset?, evolution?, overridden_fields: [...] }`, base values with overrides merged and `overridden_fields` naming what the Ruleset changed.
- `GET /api/dex/{chrooked_id}` — one merged entry with full detail.
- `GET /api/moves`, `/api/abilities`, `/api/type-chart`, `/api/behaviors` — the Ruleset-owned collections.
- `POST/PUT/DELETE /api/{species|moves|abilities|type-chart|behaviors}/{id}` — write endpoints; each validates by reloading and returns the loader's error verbatim on failure (HTTP 422 with the message).
- `GET /api/targets`, `POST /api/targets`, `DELETE /api/targets/{id}` — the Target registry.
- `POST /api/targets/{id}/preview` — apply-then-revert dry run; returns the Apply Report classification plus resulting values. Refuses (HTTP 409) with a clear message if the Target tree is dirty.
- `POST /api/targets/{id}/apply` — the real apply; returns the Apply Report and DATA-ONLY warnings; honors a `force` flag.


## Milestones

### Milestone 0 — Web scaffold and the base snapshot

Stand up the FastAPI app, the Vite React app, the `ui` CLI subcommand, and the committed base snapshot, with nothing yet rendered but a health check and an empty dex endpoint backed by real data. At the end, `chrooked-pokedex ui` serves a page and `GET /api/dex` returns merged JSON.

Work: add `fastapi` + `uvicorn` to `pyproject.toml` under a `web` extra. Create `src/chrooked_pokedex/web/app.py` with a FastAPI factory and a `GET /api/health` returning `{"status":"ok"}`. Write `src/chrooked_pokedex/web/snapshot.py`: a `build_snapshot(base_dir)` that runs the existing readers over base 1.11.2 and writes `ruleset/.base/1.11.2.json`, and a `load_snapshot()` that reads it. Add a CLI `snapshot --base PATH` subcommand to regenerate it (guarded by the same 1.11.2 version check `cli._verify_base_version` already does). Scaffold `frontend/` with Vite + React + TypeScript; a placeholder `App.tsx`. Add the `ui` subcommand: it serves the API and, if `frontend/dist` exists, the built assets; in dev it prints the Vite dev-server URL.

Acceptance: `pip install -e ".[dev,web]"` succeeds. `python -m chrooked_pokedex.cli snapshot --base ../ROMs/_scratch-expansion-1.11.2` writes `ruleset/.base/1.11.2.json`; re-running produces an identical file (idempotent, `git status` clean on the second run). Starting the server, `curl localhost:PORT/api/health` returns `{"status":"ok"}`, and `curl localhost:PORT/api/dex` returns a JSON array including Goodra with `types: ["Water","Dragon"]` and `overridden_fields` listing `types` and `abilities`.

### Milestone 1 (Slice 1) — The read-only Canon dex

Render the full national Pokédex with the Ruleset merged on top: a sprite grid, a detail view, and visible flags on overridden fields. This is the first thing Chris can actually *use*.

Work: in `web/dex.py`, implement the merge — for each base species in the snapshot, overlay the matching Ruleset `SpeciesOverride` (join on dex number / chrooked_id), producing merged values and an `overridden_fields` list; do the same surfacing for moves/abilities/type-chart. Build the React dex: a virtualized grid of cards (sprite by national dex number from the PokéAPI sprite CDN, e.g. `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{dex}.png`, cached in the browser), each card showing name, type chips, and an "edited" marker when `overridden_fields` is non-empty; a detail panel showing stats, abilities, learnset, evolution, with each overridden field badged. Add tab navigation for the other four kinds as read-only lists.

Acceptance: open the app; the grid shows ~900 species with sprites. Goodra's card is marked edited; its detail shows Water/Dragon and Poison Heal badged as overrides and a learnset containing Excalibur. Pikachu's card is unmarked and shows unchanged base values. The Moves tab lists Excalibur (Steel, physical, power from the Ruleset). Filtering by "edited only" shows exactly the species the Ruleset overrides.

### Milestone 2 (Slice 2) — CRUD for all five kinds

Make every Ruleset kind writable through typed, validated forms. Saving writes YAML; Chris reviews `git diff` and commits.

Work: in `web/crud.py`, implement create/edit/delete for species, moves, abilities, type-chart, and behaviors. Writes reuse `seed/writer.py` formatting helpers and then call `Ruleset.load`/`loader` to validate; on a validation error, return HTTP 422 with the loader's message and write nothing. Species delete = remove the override file (reverts to base in the dex). Deleting an owned move/ability that a learnset cites returns a warning listing the citing species (the reference would report partial on apply) and requires a confirm flag. Build the React editors: forms per kind with field-level validation feedback wired to the 422 messages; for species, "override a field" is reachable directly from the dex detail panel; behaviors get a structured form (closed-set trigger dropdown from the neutral vocabulary, repeatable effect rows, repeatable given/expect test-case rows, optional engine hints). Show a standing banner on the machine-owned kinds noting a re-seed will overwrite unsaved-to-canon edits.

Acceptance: from the dex, edit Goodra's Speed and save; `ruleset/species/goodra.yaml` changes (confirm with `git diff`) and the dex reflects the new value on reload. Entering an invalid stat key (`spee`) shows the loader's error inline and writes nothing (`git status` clean). Create a new owned move via the Moves form; a `ruleset/moves/<id>.yaml` appears and validates. Authoring a behavior spec writes `ruleset/behaviors/<id>.yaml` that `Ruleset.load` accepts. Attempting to delete a move cited by a learnset is blocked until confirmed and names the citing species.

### Milestone 3 (Slice 3) — Targets, preview, and apply

Register games, preview exactly what apply will do, and run the real apply — all from the app.

Work: in `web/targets.py`, implement the Target registry (gitignored JSON: label, path, engine). Implement `preview` via apply-then-revert: refuse if the Target tree is dirty (HTTP 409, "commit or stash this game first"); otherwise run the real Applier for the chosen engine, capture the Apply Report, then restore with `git checkout . && git clean -fd`; return the classification plus resulting values for a per-Target dex backdrop. Serialize previews per Target. Implement `apply` calling the existing applier path, returning the Apply Report and DATA-ONLY warnings; honor a `force` flag that maps to the existing `--force`. Build the React Targets panel: a list with add/remove; selecting a Target offers Preview (shows applied/partial/blocked/created counts and lets the dex switch to that Target's backdrop) and Apply (a deliberate, confirmed action; dirty-tree shows an Error State with an explicit Force toggle); render the returned Apply Report with the DATA-ONLY behavior warnings linking to each mechanic's packet.

Acceptance: register `dreamstone-mysteries` (pokeemerald) on a clean tree. Preview returns counts and leaves the Target unchanged (`git status` clean afterward). Switching the dex to that Target's backdrop shows the game's own values with the Ruleset previewed on top. Running Apply changes files and prints an Apply Report whose `applied/partial/blocked` counts match the preview's; a created behavior-only ability appears in the DATA-ONLY list with a working packet link. On a deliberately dirtied Target, Apply shows the Error State and only proceeds when Force is toggled.


## Progress

- [x] (2026-06-12) Grilling session complete: nine design nodes resolved (app shape, dex meaning, base source, write model, CRUD scope, Target picker, dry-run engine, sprites, sequencing). CONTEXT.md gained Target / Target registry / Canon dex. ADR 0001 written. This plan authored.
- [x] (2026-06-12) Milestone 0 — Web scaffold + base snapshot. `web` extra (fastapi/uvicorn) added; `web/snapshot.py`, `web/dex.py`, `web/app.py` written; `snapshot` and `ui` CLI subcommands added (web imports deferred so seed/apply/harvest still work without the extra); Vite + React + TS shell scaffolded in `frontend/`; committed base snapshot generated at `ruleset/.base/1.11.2.json` (1451 species). Acceptance met: `/api/health` → `{"status":"ok"}`; `/api/dex` over the real ruleset returns 1451 merged entries with Goodra dex 706, types `[Dragon, Water]`, abilities merged (Sap Sipper base ⊕ Hydrate/Poison Heal override), `overridden_fields` = types/abilities/stats/learnset/evolution; snapshot re-run is byte-identical (idempotent). 194 tests green. Reviews: security clean; one HIGH + three MEDIUM Python findings fixed.
- [x] (2026-06-12) Milestone 1 (Slice 1) — Read-only Canon dex. Backend: `web/collections.py` serializes the four Ruleset-owned kinds; `web/dex.build_dex_entry` + a `base` diff payload added; read-only endpoints `/api/dex/{id}`, `/api/moves`, `/api/abilities`, `/api/type-chart`, `/api/behaviors` (Ruleset-load and snapshot-shape both guarded → 503, never 500). Frontend: a device-framed, virtualized sprite grid (~1451), a detail ledger with a base→now diff toggle, the four read-only kind tabs, 18 dark-tuned franchise type colors, edited-LED, URL-persisted view state, keyboard nav, BST row (folded-in #3). Form sprites resolved via a baked PokéAPI form-id map (`scripts/build_sprite_index.py` → `frontend/src/data/sprite-ids.json`, 194 forms). **Stat-macro data fix**: 151 species had stats silently dropped (symbolic values); the snapshot builder now resolves them. 216 Python tests green; ESLint + tsc + vite build clean. Reviews: react + python + a11y fan-out; all HIGH/CRITICAL + cheap MEDIUMs fixed.
- [ ] Milestone 2 (Slice 2) — CRUD for all five kinds.
- [ ] Milestone 3 (Slice 3) — Targets, preview, apply.

Post-M1 feature requests captured as GitHub issues (chrooks/chrooked-pokedex): [#1](https://github.com/chrooks/chrooked-pokedex/issues/1) dex table view, [#2](https://github.com/chrooks/chrooked-pokedex/issues/2) table sort/filter controls, [#3](https://github.com/chrooks/chrooked-pokedex/issues/3) BST row (folded into M1), [#4](https://github.com/chrooks/chrooked-pokedex/issues/4) reverse lookups (move/ability → species), [#5](https://github.com/chrooks/chrooked-pokedex/issues/5) full type-chart matrix.


## Surprises & Discoveries

- Observation: the Ruleset never invents a species (schema has `SpeciesOverride` only), so every dex entry has a national dex number.
  Evidence: `src/chrooked_pokedex/model/schema.py` defines no "new species" dataclass; overrides carry `aka.dex`. This is why sprite-by-dex-number is gap-free and why the Canon dex must merge onto a base snapshot rather than render the Ruleset alone.

- Observation (M0): base 1.11.2 stores `natDexNum` as a *symbolic* `NATIONAL_DEX_GOODRA`, not a digit, so neither the seed nor a naïve snapshot can read a numeric dex straight from the species entry.
  Evidence: `species_info/gen_6_families.h` → `.natDexNum = NATIONAL_DEX_GOODRA`; the numbers live in the positional `enum` in `include/constants/pokedex.h` (NONE=0, BULBASAUR=1, … GOODRA=706). `web/snapshot._national_dex_map` resolves the symbol via that enum (anchored on `\benum\s*\{`, and stopping at the first `};` so the trailing `#define NATIONAL_DEX_COUNT …` lines don't corrupt the counter). The numeric dex is what M1's sprite-by-dex URL needs.

- Observation (M0): the committed snapshot has **1451** species, not the ~900 the plan estimated — it includes every mega/regional/alternate form. Forms share their base species' national dex number.
  Impact for M1: a sprite keyed purely by dex number will repeat across a species' forms. The dex grid needs form-aware handling (group forms, or pick a form-specific sprite path) rather than assuming one card per dex number.

- Observation (M0): the **real** `ruleset/` overrides Pikachu (stats + evolution), so Pikachu is *edited*, not a clean baseline.
  Impact for M1: the Slice-1 acceptance uses Pikachu as the "unmarked, unchanged" example — pick a genuinely un-overridden species for that assertion (or accept Pikachu shows as edited).

- Observation (M1): a form's sprite cannot be keyed by national dex number — forms share their base species' number (Hisuian Goodra is 706, like Goodra), so PokéAPI-by-dex always returns the base sprite. PokéAPI does carry a distinct sprite per form under a separate numeric id (Hisuian Goodra is 10242), but there's no formula from name to that id.
  Resolution: `scripts/build_sprite_index.py` matches each form's display name against PokéAPI's `/pokemon` list and bakes `frontend/src/data/sprite-ids.json` (chrooked_id → form id, 194 entries). The frontend uses the form id when present, else the dex number, else a placeholder. Cosmetic combos PokéAPI doesn't model (Alcremie swirls, some Paldean Tauros) fall back to the base sprite — no broken images. Grounding in the live API also corrected a wrong manual guess (it's 10242, not 10243).

- Observation (M1): **151 species had base stats silently dropped from the snapshot.** A stat value in 1.11.2 source isn't always a digit — it can be a named macro (`.baseAttack = AEGISLASH_MAIN_STAT`), an inline config-gated ternary (`= P_UPDATED_STATS >= GEN_7 ? 95 : 85`), or a macro with an offset (`= ALAKAZAM_SP_DEF + 10`). The M0 `_base_stats` accepted only `value.isdigit()`, so every symbolic stat vanished (Aegislash Blade showed ATK/SpAtk 0). This is exactly the M0 "[DEFERRED] non-digit stat" low-risk note coming due — and it was caught by eye in the dex, not by a test.
  Resolution: the snapshot builder resolves the engine config (`P_UPDATED_STATS = GEN_LATEST = GEN_9`, the `GEN_*` ladder) and evaluates all three shapes via `_eval_expr` over one symbol table, so values match what the game compiles. After the fix: 0 species with partial stats. The only empties left are 63 Alcremie cosmetic decoration combos that carry no stat block in source (they inherit base Alcremie); the ledger renders those as `—`, never `0`. Form→base stat inheritance for those is a noted follow-up.


## Decision Log

- Decision: local FastAPI + React (Vite), FastAPI importing the existing package.
  Rationale: seed/apply/harvest need local filesystem, git, and Python — nothing is deployable; importing reuses all validation/applier logic instead of reimplementing it.
  Date/Author: 2026-06-12, Chris + Claude (grilling session).

- Decision: the Canon dex merges the Ruleset onto a committed base 1.11.2 snapshot JSON; per-Target preview is a second backdrop.
  Rationale: the Ruleset is overrides-only and cannot render a full dex alone; a committed snapshot is deterministic and avoids depending on the deletable scratch base checkout.
  Date/Author: 2026-06-12, Chris + Claude.

- Decision: UI writes go to YAML via the seed writer, are validated by reloading through the loader, and are not committed by the UI.
  Rationale: the loader is the existing validation Boundary; `git diff` is the review gate; matches the solo-main workflow and the project's "drift only enters canon through a gate Chris opens" ethos (here, Chris is the author opening it).
  Date/Author: 2026-06-12, Chris + Claude.

- Decision: all five Ruleset kinds are writable in v0; the Target picker is a registry, not a file browser.
  Rationale: behaviors have no other editor and the rest are small; a browser SPA cannot use a native file picker, and registration gives each Target a reusable identity that also powers the preview backdrop.
  Date/Author: 2026-06-12, Chris + Claude.

- Decision: the dry-run/preview engine is apply-then-revert via git (see ADR 0001).
  Rationale: the preview must equal a real apply; reusing the real appliers and restoring via git is faithful by construction and safe because a clean tree is already required.
  Date/Author: 2026-06-12, Chris + Claude.

- Decision: delivery is sliced Canon dex (read) → CRUD all five → Targets + preview + apply.
  Rationale: the base ⊕ Ruleset merge is the spine both CRUD and preview depend on; risk rises gradually and each slice is independently usable.
  Date/Author: 2026-06-12, Chris + Claude.

- Decision (M0): `cli.py` defers `import fastapi`/`uvicorn`/`web.*` into the `ui`/`snapshot` handlers, not module top-level.
  Rationale: the web layer is an optional `[web]` extra; a top-level import would break `seed`/`apply`/`harvest` for anyone who installed only the base package. The `ui` handler fails with an actionable "install the web extra" message if the import misses.
  Date/Author: 2026-06-12, Claude (implementation).

- Decision (M0): `/api/dex` loads the snapshot and Ruleset *per request*, and maps a missing/corrupt snapshot to HTTP 503 with a "run `snapshot`" message.
  Rationale: per-request load means a YAML edit shows on the next call with no restart, keeping the loader as the single validation Boundary; the 503 turns the realistic "forgot to generate the snapshot" failure into a clear instruction instead of a bare 500 traceback.
  Date/Author: 2026-06-12, Claude (implementation, from review).

- Decision (M1): the merged dex entry carries a `base` payload — the pre-override value of each changed field — so the detail ledger can show base→now.
  Rationale: the diff toggle ("the edit is the hero") needs both sides; computing the base client-side is impossible from the merged values alone. Captured in `_merge_species` before the override is applied, so it's always the true pre-override value.
  Date/Author: 2026-06-12, Chris + Claude.

- Decision (M1): form sprites resolve through a *baked* PokéAPI form-id map, not a live name→id lookup or Pokémon Showdown's pixel sprites.
  Rationale: keeps the smooth PokéAPI look consistent across base and forms; a baked JSON is offline, deterministic at runtime, and small (~5 kB). Showdown's name scheme works but restyles everything to pixel; PokémonDB lacks newer forms. Regenerate only when the 1.11.2 pin moves.
  Date/Author: 2026-06-12, Chris + Claude.

- Decision (M1): the snapshot builder resolves symbolic stat values (named macros, config-gated ternaries, macro+offset) via the engine's own config flags.
  Rationale: faithfulness — the dex must show what the game compiles, not drop any stat it can't read as a digit. Resolving `P_UPDATED_STATS`/`GEN_*` from the checkout (rather than hardcoding 140/95/…) keeps it correct if the pin's config changes.
  Date/Author: 2026-06-12, Claude (implementation, from a Chris-caught bug).

- Decision (M1): read-only M1 keeps a hand-rolled abortable fetch hook (`useResource`) instead of TanStack Query, and a baked focus trap (`inert` on the background) instead of a trap library.
  Rationale: YAGNI for five read-only GETs with no mutations; the seam to swap in TanStack Query is marked for M2 (CRUD), where caching/optimistic updates actually earn it. `inert` is one line with the best browser support and no dependency.
  Date/Author: 2026-06-12, Claude (implementation, from review).


## Outcomes & Retrospective

**Milestone 0 (2026-06-12).** Shipped the web scaffold and committed base snapshot. `chrooked-pokedex ui` serves the FastAPI app (and the built React shell when present); `/api/dex` renders the full Canon dex by merging the Ruleset onto `ruleset/.base/1.11.2.json`. The merge — the spine M1 (CRUD) and M3 (preview) both hang off — was built and tested in full here rather than stubbed, so M1 inherits a proven base ⊕ Ruleset merge and only adds the React grid/detail on top. Reused the existing pokeemerald readers and `seed.neutralize` wholesale, so base values land in the Ruleset's neutral vocabulary with no second parsing path to drift. Two things surfaced that reshape M1: the snapshot is 1451 entries (forms included, sprites need form-awareness) and the real Pikachu is overridden (pick a different "unchanged" example). No deviations from the chosen architecture.

**Milestone 1 (2026-06-12).** Shipped the read-only Canon dex as a `craft`-flow build (impeccable: `shape` → discovery → committed `PRODUCT.md`/`DESIGN.md` → build → review → visual iteration with Chris). Direction: a terminal-dense "device" with restrained Pokédex character, dark warm-tinted screen, brick-red chrome, an amber edited-LED, and the 18 franchise type colors as a dark-tuned, AA-legible token set. The dex is a virtualized sprite grid + a detail ledger whose diff toggle reveals base→now on every overridden field; four read-only kind tabs cover moves/abilities/type-chart/behaviors. Backend added the four collection serializers and a single-entry route, all 503-guarded. Two real defects surfaced *only by eye*, not by tests, and both got root-cause fixes: the grid collapsed to one column (an `inert` focus-trap wrapper swallowed flex sizing), and 151 species showed dropped/zero stats (symbolic stat values the digit-only reader couldn't parse — the M0 deferred note coming due). Form sprites required a baked PokéAPI form-id map. The visual gate earned its keep: a fully test-green build still had two user-visible bugs a screenshot caught immediately. BST (#3) folded in; the other four requests parked as issues to hold the milestone line.


## Code Review Findings

Milestone 0 review fan-out (2026-06-12): `python-reviewer` + `security-reviewer` on the new `web/` modules, `cli.py` changes, and tests. Security review: clean — no CRITICAL/HIGH; host binds `127.0.0.1`, StaticFiles path is not user-controlled, `json.loads` is stdlib (no unsafe deserialization), no secrets. All HIGH/MEDIUM code findings fixed and covered by tests; 194 green.

### High Risk

- **[FIXED] `dex.py` rename guard used truthiness on a non-Optional field.** `if override.name:` would silently skip a rename when `name == ""`. `SpeciesOverride.name` is typed `str` (always present), so the assignment is now unconditional.

### Medium Risk

- **[FIXED] `snapshot._national_dex_map` matched `enum` as a bare substring.** `text.find("enum")` could be redirected by a stray lowercase `enum` fragment. Now anchored on `\benum\s*\{`. Locked by `test_national_dex_map_is_positional_and_ignores_trailing_defines`.
- **[FIXED] `/api/dex` returned an opaque 500 on a missing/corrupt snapshot.** Now caught and re-raised as HTTP 503 with a "run `snapshot`" message. Locked by `test_dex_returns_503_when_snapshot_missing`.
- **[FIXED] `get_dex` return type was the bare `list[dict]`.** Now `list[dict[str, Any]]` for a usable OpenAPI schema.

### Low Risk

- **[ADDRESSED in M1] A renamed species is not listed in `overridden_fields`.** M1 guards the name write so it only fires on an actual change (an override touching only stats can't clobber the name); rename *visibility* in the ledger is still deferred to the CRUD slice (no name-diff row yet).
- **[FIXED in M1] `_base_stats` drops a stat whose value isn't a bare digit.** This came due exactly as predicted: 1.11.2 writes many stats as named macros, config-gated ternaries, and macro+offset expressions, so 151 species lost stats. The snapshot builder now resolves all three shapes via the engine's config (`_eval_expr` / `_config_int_map` / `_stat_macro_map`); 0 species with partial stats afterward. Locked by `test_symbolic_form_stats_are_resolved_not_dropped` and the `_eval_expr`/`_eval_define` unit tests.

---

Milestone 1 review fan-out (2026-06-12): `react-reviewer` + `python-reviewer` + `a11y-architect` on the M1 diff. All CRITICAL/HIGH fixed, cheap MEDIUMs fixed, true nice-to-haves deferred.

### M1 — Fixed

- **[python HIGH] Unguarded 500s.** A corrupt `ruleset/` YAML or a wrong-shape snapshot crashed with a raw 500. Now both load through 503 guards (`_load_ruleset_or_503`, snapshot `"species"`-key check). Locked by new tests.
- **[python HIGH] Silent rename clobber.** `_merge_species` wrote `name` unconditionally; now only on an actual change.
- **[react HIGH] `memo(DexCell)` defeated** by an inline `onOpen` arrow at 1451 cells → `useCallback`. ESLint + `eslint-plugin-react-hooks` added (was absent). `useColumnCount` → callback ref; `DetailLedger` effects merged.
- **[react HIGH] `useSyncExternalStore` snapshot not cached** in `useUrlState` (re-render loop risk) → cached by query string.
- **[a11y CRITICAL] Detail panel not a dialog / no focus trap.** Now `role="dialog" aria-modal`, labelled, with `inert` on the background. Grid got `role="grid"` + counts; `aria-pressed` → `aria-haspopup`/`aria-expanded` + label; the "edited" state is never color-alone (LED + sr-only/text everywhere); type chips AA-tuned via `color-mix`.

### M1 — Deferred (nice-to-have)

- Full `role="tablist"` with arrow-key roving on the kind tabs (minimal `aria-current` shipped).
- `aka`/`engine_hints` symmetry across the collection serializers (not displayed in M1).
- Alcremie form→base **stat inheritance** (63 cosmetic combos show `—`).
- The dev-only esbuild/vite advisory (pre-existing from the M0 Vite 5 scaffold; not in the production bundle; major-bump to fix).
- **[ADDED] Unit coverage** for `_national_dex_map` (synthetic header) and `_resolve_dex` (symbol + bare-integer + None), so the dex-number resolution no longer depends solely on the integration test against the real base checkout.
