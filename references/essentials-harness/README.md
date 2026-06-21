# Essentials 16.2 harness assets

Reusable target-side files for porting + verifying custom mechanics in an
Essentials 16.2 game (e.g. Africanvs). Built in issue #15. The Python side of
the harness lives in `src/chrooked_pokedex/behavior/harness.py`; these are the
Ruby/config files that get copied into the game copy.

## Install into a game copy

Copy into the target's root + `Scripts/`:

- `mkxp.json` → `<copy>/mkxp.json` — points mkxp-z `preloadScript` at the shim.
- `load_order_shim.rb` → `<copy>/Scripts/load_order_shim.rb` — preload shim: sets
  up the guarded `$chrooked_log` (writes `Scripts/chrooked_load.log`), prints
  `[LOAD_ORDER_SHIM] active`, and auto-loads every `Scripts/chrooked_*.rb`.
- `chrooked_<id>.rb` → `<copy>/Scripts/` — one plugin per mechanic.

No `load_order.txt` editing — the shim globs `chrooked_*.rb`.

## Files

| file | role |
| --- | --- |
| `mkxp.json` | preload entry point |
| `load_order_shim.rb` | general plugin loader + logger (mechanic-agnostic) |
| `chrooked_harness_probe.rb` | M0 spike: logs `PokeBattle_Battle` ctor arity (no instantiate) |
| `chrooked_innerfocus.rb` | innerfocus port (Seam: `pbAccuracyCheck`) + OBS logging |
| `chrooked_kindle.rb` | kindle port (Seam: `pbModifyDamage`) + OBS logging |

## Verify a mechanic

    PYTHONPATH=src python -m chrooked_pokedex.behavior.harness stage  <id>
    # boot the copy in debug, run the printed actions in one battle, quit
    PYTHONPATH=src python -m chrooked_pokedex.behavior.harness verify <id>

Each plugin logs one uniform line per gated event —
`[chrooked:<id>] OBS key=value ...` — and the driver scores those against the
mechanic's scenario in `src/chrooked_pokedex/behavior/harness_scenarios.py`.

Ruby 1.8 engine: no `prepend`/`TracePoint`; overrides use `alias_method`
chaining and defer install via a one-shot on `Graphics.update`.
