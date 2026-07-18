# Rejuvenation modding playbook

How we bend Pokémon Rejuvenation to Chris's preferences. Read this before the next
"make Rejuv do X" request — it's the decision tree plus the install/verify flow.

## The one rule Rejuv gives us

From the game's own `Modding.txt`:

- `patch/Mods/*.rb` override the base game **per method/constant/function**, not per file.
  Redefine only what you need; the rest of the base script stays.
- **Never edit base `Scripts/*.rb`.** Rejuv says so explicitly, and edits get clobbered on update.
- `patch/Definitions/*.rb` override the compiled data (mons/moves/abilities/types).
- `patch/Init/*.rb` run before the main menu (used for our compile trigger).

Everything below lives under `patch/` — uninstall is `rm -rf patch/`.

## Decision tree: which kind of change is this?

```
Is it a data value? (base stat, type, learnset, move power, ability text)
  └─ YES → Ruleset Override (ruleset/species|moves|abilities/*.yaml). The applier
           writes patch/Definitions. No Ruby.

Is it battle logic tied to an ability or move? (ability buffs a move, on-hit effect)
  └─ YES → Ruleset BEHAVIOR. Two files:
           1. ruleset/behaviors/<id>.yaml   — engine-neutral spec (human-owned)
           2. references/rejuv-harness/chrooked_<id>.rb — Rejuv impl, tagged
              `# chrooked:<id>`, registers into a CHROOKED_* table from the core.
           Installed only when BOTH exist (behavior_install.py).

Is it a UI / QoL / menu / input tweak? (not an ability or move)
  └─ YES → STATIC MOD. One file:
           references/rejuv-harness/chrooked_zz_<name>.rb, tagged `# chrooked:zz_<name>`.
           apply.py::_install_static_mods copies every chrooked_zz_*.rb into
           patch/Mods on every apply — no Ruleset entry needed.
```

Rule of thumb: **behavior** = something an ability or move does in battle;
**static mod** = everything else about the game (menus, input, screens).

## How the Ruby patches take effect (no base edits)

The core, `chrooked_00_core.rb`, uses `Module#prepend` to wrap vanilla battle methods,
and declares `CHROOKED_*` lookup tables keyed by ability/move symbol. Each behavior file
just adds a row to a table. When you need a NEW hook point:

1. Add a `CHROOKED_<THING> = {}` table near the top of the core.
2. Add a `prepend`ed wrapper method that consults it (mirror an existing one).
3. Behavior files register `CHROOKED_<THING>[:SYMBOL] = lambda { ... }`.

A static mod that reopens a class works the same way — but if the change is buried
mid-method (an input loop, say) with no seam, override the whole method per Modding.txt
and mark it `ponytail:` with a re-sync note, because it goes stale on Rejuv updates.

## Install + verify flow

1. Write the file(s) under `references/rejuv-harness/` (+ `ruleset/behaviors/` for a behavior).
2. Copy into the live target's `patch/Mods/` to test now:
   `cp references/rejuv-harness/chrooked_<x>.rb "<TARGET>/patch/Mods/"`
   (a behavior also needs the possibly-updated `chrooked_00_core.rb` copied.)
   A full `apply` does this for you — the hand-copy is just faster for one file.
3. `ruby -c <file>` if ruby is on hand; `pytest tests/test_rejuv_applier.py` for the applier.
4. Boot Rejuv and drive the actual flow — the harness can't prove in-game behavior.

Target lives at the path in the gitignored `targets.json` (engine `rejuv`). v14 today:
`/mnt/d/Games/Pokemon FanGames/Rejuvination v14`.

## Finding the seam (how to locate the code to hook)

- `grep -rn` the target's `Scripts/*.rb` for the symbol, method, or on-screen label.
- Confirm the class that owns the method before reopening it.
- Confirm the exact Rejuv symbol (`:BADDREAMS`, `:HYPNOSIS`) — don't guess casing.
- Prefer a real seam (a prepend wrapper or a per-game hook) over a whole-method override.

## Worked examples in this repo

| Change | Kind | Files |
|--------|------|-------|
| Learn menu shows past level-up moves (free relearn everywhere) | static mod | `chrooked_zz_relearn.rb` (override `canRelearnAll?` → true) |
| Bad Dreams makes Hypnosis 1.2× accurate | behavior | `ruleset/behaviors/baddreams.yaml`, `chrooked_baddreams.rb`, new `CHROOKED_ACCURACY_MODS` table + `pbCalcAccuracy` wrapper in the core |
| Pressing B runs from a wild battle | static mod | `chrooked_zz_run.rb` (per-method override of `pbCommandMenuEx`) |
