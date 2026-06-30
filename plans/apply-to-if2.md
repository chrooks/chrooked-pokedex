# Handoff: apply chrooked-pokedex Ruleset → Infinite Fusion 2

**Run this in a session rooted at `~/projects/chrooked-pokedex`.**

## Context (already verified)
- IF2's PBS is **`essentials16` dialect** (numeric `[N]` headers, `InternalName=`,
  `Type1/Type2`, flat-CSV moves/abilities). `apply --dialect auto` detects this and
  routes to the **`essentials162`** applier automatically (confirmed in `dispatch.py`).
- IF2 path from WSL: `/mnt/d/Games/Pokemon FanGames/InfiniteFusion2Hoenn/InfiniteFusion2`
  (the `PBS/` folder is freshly exported and present).
- Resolution is the default path: ruleset `chrooked_id` → IF2 `InternalName`
  (standard uppercase English, same as Africanvs). No `aka.essentials` hints needed
  for the national-dex base.

## ⚠️ Gotcha: `apply` has NO dry-run flag
`chrooked-pokedex apply` always writes to the target (and drops `apply-report.md`
there). Only `harvest` has `--dry-run`. So to "preview" safely, run against a
throwaway COPY of IF2's PBS, not the live game:

```bash
cd ~/projects/chrooked-pokedex
source .venv/bin/activate            # or however the env is activated

IF2="/mnt/d/Games/Pokemon FanGames/InfiniteFusion2Hoenn/InfiniteFusion2"

# 1. Make an isolated preview target with just the PBS folder
mkdir -p /tmp/if2-preview/PBS
cp "$IF2/PBS/"*.txt /tmp/if2-preview/PBS/

# 2. Apply to the COPY (--force: copy isn't a clean git tree)
chrooked-pokedex apply --target /tmp/if2-preview --engine essentials --dialect auto --force

# 3. Read the report + see exactly what would change
cat /tmp/if2-preview/apply-report.md
diff -u "$IF2/PBS/pokemon.txt" /tmp/if2-preview/PBS/pokemon.txt | less
diff -u "$IF2/PBS/types.txt"   /tmp/if2-preview/PBS/types.txt
```

## What to check in the report
- **`applied=`** vs **`blocked=`** — blocked = species/moves IF2 lacks (expected for
  any the Ruleset names but IF2 doesn't have). If *everything* blocks, dialect/
  resolution is wrong.
- **`partial=`** — likely owned moves/abilities whose behavior is Ruby (FunctionCode),
  reported honestly, plus the known hex-FunctionCode gap (issue #22) for 16.2 move effects.
- The **`⚠ DATA ONLY`** abilities list, if any.

## Known deltas to watch
1. **moves.txt Target column**: IF2 uses NAMED targets (`NearOther`); Africanvs used
   numeric (`00`). Only the `moves`/`create` tiers touch this — if the report shows
   owned-move writes, eyeball the moves.txt diff for a malformed Target field.
   Species/learnset/type-chart are unaffected.
2. **Move effects (hex FunctionCodes)** are a known incomplete area in essentials162
   (`#22`) — created moves will be plain damaging unless behavior is installed.
3. **Fusion ripple**: IF2 is a fusion game — base-species stat/type changes propagate
   into fusions. Expected, not a bug.

## Go-live (after the preview looks right)
The live apply needs a clean-or-forced git tree (IF2's repo is dirty from modding edits):

```bash
chrooked-pokedex apply --target "$IF2" --engine essentials --dialect auto --force
```

Then **in IF2: hold `Ctrl` while the game boots** to recompile the PBS into `.dat`.
Recovery net if a recompile errors: run `git checkout -- $(git ls-files --deleted)`
in the game folder.

**Tip:** run `--category species` first (smallest, safest tier) to validate the
pipeline end-to-end before running `--category all`.
