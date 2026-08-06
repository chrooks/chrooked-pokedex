# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An engine-neutral Pokémon **Ruleset** (the single source of truth for Chris's preferred changes) plus per-engine **Appliers** that write that Ruleset into a target game's files. Read `CONTEXT.md` first — it is the project Lexicon and defines every domain term used here (Ruleset, Override, Applier, Resolution map, Apply Report, Harvest, Fork, Target, Canon dex, In-Game Proof, `chrooked_id`). `PRODUCT.md`/`DESIGN.md` govern the web UI; `plans/` and `feature_requests/` hold ExecPlans.

## Commands

```bash
pip install -e ".[dev,web]"     # dev = pytest/httpx; web = fastapi/uvicorn/litellm
pytest                          # all tests
pytest -m unit                  # fast hermetic only; -m integration needs on-disk base/fork
pytest tests/test_dispatch.py::test_name   # single test
pytest --cov=src --cov-report=term-missing # coverage
```

CLI (`chrooked-pokedex`, defined in `cli.py`):

```bash
chrooked-pokedex seed --fork PATH --base PATH      # diff a fork vs base → write ruleset/ YAML
chrooked-pokedex apply --target PATH [--engine pokeemerald|essentials] [--category all|...] [--dialect auto|essentials16|essentials21] [--force]
chrooked-pokedex harvest --fork PATH [--dry-run]   # gated reverse sync: propose Ruleset edits from a fork
chrooked-pokedex behaviors [--mechanic ID --engine ENG]  # list/print custom-mechanic implementation packets
chrooked-pokedex snapshot --base PATH              # freeze base 1.11.2 → ruleset/.base/1.11.2.json (deterministic)
chrooked-pokedex ui [--reload]                     # serve FastAPI + built SPA on :8000 (API under /api)
```

Frontend (in `frontend/`): `npm run dev` (Vite :5173, proxies `/api`), `npm run build` (`tsc -b && vite build`), `npm run lint`, `npm run test` (vitest). For UI hot-reload run `chrooked-pokedex ui` and `npm run dev` side by side.

## Architecture

Data flows one direction by default: **Ruleset YAML → model → Applier → target game files**. `seed` and `harvest` are the only paths that read a fork.

- `ruleset/` — source of truth. Hand-editable YAML by kind: `species/`, `moves/`, `abilities/`, `behaviors/`, `type-chart/`, plus `meta.yaml`. Stores only **Overrides** (fields differing from base), except learnsets which are stored whole.
- `model/` — frozen dataclasses for the neutral schema (`schema.py`), the `Ruleset` aggregate with a fail-fast `Ruleset.load(dir)` loader (`ruleset.py`, `loader.py`), and the custom-mechanic schema (`behavior_spec.py`).
- `readers/pokeemerald/` — vendored C parsers that read pokeemerald-expansion source (the baseline `seed`/`harvest` diff against).
- `seed/` — extract a Ruleset by diffing a fork against its base, then write YAML.
- `appliers/` — one subpackage per engine: `pokeemerald/` (writes C), `essentials/` (v21 section-based PBS), `essentials162/` (16.x flat-CSV PBS). `dispatch.py::route_apply` is the shared engine+dialect router both the CLI and web layer call so they cannot drift; it does **not** print or write the report (each entry point owns those side effects).
- `report/` — the **Apply Report** (`applied`/`partial`/`blocked`). Apply never silently drops anything; an unresolvable entry becomes a report entry, not a stack trace.
- `harvest/` — deliberate, per-field-confirmed reverse sync; never part of a normal apply.
- `behavior/` — renders custom mechanics as engine-specific implementation packets (data-only abilities still need engine code).
- `web/` — FastAPI app factory (`app.py`). Loads the Ruleset **per request** so edits to `ruleset/` appear without a restart. The LLM lives behind a provider-agnostic Port (`llm.py`, LiteLLM) hung off `app.state` so tests inject a mock. Routers: `dex`, `crud`, `collections`, `targets`, `suggest`, `snapshot`, `evolution`.
- `frontend/` — Vite + React + TypeScript SPA, served from `frontend/dist` in production.

### Things that bite

- **Apply tier order is load-bearing.** Each engine applies categories in a fixed sequence (see the `_*_CATEGORIES` tuples and comments in `cli.py`): moves/abilities are written before species so newly-created entries register into the in-memory **Resolution map** before a species references them. Don't reorder.
- **Resolution map is per-Applier** (`chrooked_id` → engine symbol, e.g. `goodra → SPECIES_GOODRA`). Partly auto-derived from `aka:` hints, partly hand-confirmed.
- **`dispatch.py` imports the `_apply_*` helpers inline** to avoid a `cli → dispatch → cli` circular import. Keep it that way.
- **Essentials dialect is auto-detected** from PBS file shape; an unrecognized format produces one `blocked` report entry and writes nothing — override with `--dialect`.
- **`apply` requires a clean target git tree** (`git_guard.py`) unless `--force`.
- **`snapshot` and `seed` are pinned to base 1.11.2.** Seeding/snapshotting against the wrong base fabricates phantom overrides — `_verify_base_version` warns. The committed snapshot (`ruleset/.base/1.11.2.json`) is regenerated only when the base pin moves; the writer is deterministic so an unchanged base leaves `git status` clean.
- `targets.json` (the Target registry) is gitignored and machine-specific — never canon.

## Conventions

- Frozen dataclasses, immutable updates (return new copies; never mutate). Python ≥3.11, type-annotated, PEP 8.
- Tests: `pytest` markers `unit` (hermetic) and `integration` (needs a real on-disk checkout, auto-skipped when absent). Fixtures live under `tests/fixtures/`.
- Conventional commits, scoped to one logical change; many small files over few large ones (<800 lines).

### Evolution-line default (Ruleset design)

When reworking a species that is part of an evolution line, default to this shape:

1. **Design the final evo first** — typing, stats, abilities, learnset. That's where the line's identity is decided; get it approved before deriving anything.
2. **Copy the kit down to every pre-evo**: same typing, same abilities, **same learnset (exact copy, minus L0 on-evo moves)** — L0 rows are the evolution's reward and stay on the evolved stage only. No per-stage rescaling of levels.
3. **Only stats scale down.** Apply the *same BST delta* the final evo received to each pre-evo's canon BST, then redistribute within that total preserving the final evo's role emphasis (keep the dump stat low). Example: Sawsbuck 475 → 520 (**+45**), so Deerling 335 → **380**.
4. **Multi-form lines**: do all of the above per form, so each form keeps its own typing and stat-role identity across both stages.
5. **Megas and battle forms mirror the base form's learnset** — never bespoke. Keep the base form's L0 row.
6. **Branch-shared pre-evos are opt-in.** A pre-evo that also feeds another line (Goomy feeds both Sliggoo forms) is NOT mirrored by default — copying one line's kit onto it desyncs the other, and the next makeover there clobbers it back. The mirror UI starts such rows on skip; pull one in only when you've decided which line owns it.

Divergent typing, abilities, or stat shape between stages is an **exception** — allowed, but state it explicitly rather than doing it silently.

### Makeover definition of done

A species makeover is **not done** at Ruleset write. Done means:

1. **Applied** — run `apply` against the active Rejuv target automatically once the makeover is locked in; don't wait to be asked.
2. **Read back** — after apply, read the applied PBS entry for each changed species from the target and diff it against the Ruleset expectation (types, stats, abilities, learnset rows, evolutions). A green Apply Report alone is not In-Game Proof — form-join and clobber bugs have shipped past it.
3. **Committed and pushed** once the read-back checks out.

Dex UI changes get the same discipline: drive the running UI with a real query (screenshot or assertion) before calling it done — passing vitest alone has shipped broken filters.
</content>
</invoke>
