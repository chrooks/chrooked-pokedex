# chrooked-pokedex

An engine-neutral Pokémon **Ruleset** — the single source of truth for Chris's
preferred Pokémon changes — plus per-engine **Appliers** that write that Ruleset
into a target game's files.

Today the Ruleset targets **pokeemerald-expansion** forks (C source). A future
Applier will target **Pokémon Essentials** (PBS text + Ruby).

See `CONTEXT.md` for the project Lexicon and `plans/chrooked-pokedex-plan.md` for
the full design and milestones.

## Layout

- `ruleset/` — the source of truth: hand-editable YAML (species, moves, abilities, type-chart).
- `src/chrooked_pokedex/readers/pokeemerald/` — vendored C parsers (from v1).
- `src/chrooked_pokedex/model/` — frozen dataclasses for the neutral schema.
- `src/chrooked_pokedex/seed/` — extract a Ruleset by diffing a fork against its base.
- `src/chrooked_pokedex/appliers/pokeemerald/` — Ruleset → C, plus the resolution map.
- `src/chrooked_pokedex/report/` — the Apply Report writer.
- `src/chrooked_pokedex/harvest/` — gated reverse sync (fork → proposed Ruleset edits).
- `src/chrooked_pokedex/web/` — the local FastAPI app (Canon dex, CRUD, apply); a thin Interface over the core.
- `frontend/` — the Vite + React single-page app served by `chrooked-pokedex ui`.

## Develop

    pip install -e ".[dev]"
    pytest

## Web app

The local app browses a **Canon dex** (the full national Pokédex with the Ruleset
merged on top), edits the Ruleset, and applies it to a registered game.

    pip install -e ".[dev,web]"

    # 1. Freeze base 1.11.2 into the committed snapshot the Canon dex merges onto.
    #    Deterministic — re-running on an unchanged base rewrites byte-identical JSON.
    chrooked-pokedex snapshot --base ../ROMs/_scratch-expansion-1.11.2

    # 2. Build the SPA (optional in dev — see below), then serve everything.
    cd frontend && npm install && npm run build && cd ..
    chrooked-pokedex ui            # http://127.0.0.1:8000  (API under /api)

For frontend dev with hot reload, run the API and the Vite dev server side by side
(Vite proxies `/api` to the FastAPI server):

    chrooked-pokedex ui &          # serves the API on :8000
    cd frontend && npm run dev     # serves the SPA on :5173

The committed base snapshot lives at `ruleset/.base/1.11.2.json`; regenerate it
with the `snapshot` subcommand only when the 1.11.2 base pin moves.
