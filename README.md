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

## Develop

    pip install -e ".[dev]"
    pytest
