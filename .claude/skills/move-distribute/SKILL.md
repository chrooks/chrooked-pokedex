---
name: move-distribute
description: Distribute one already-existing move across many species' level-up learnsets by mechanical rule — pick recipients by type(s) and attack split (physical/special), then drop the move into the widest gap of a level window (early/mid/late, or explicit numbers) so it never collides with an existing move and keeps spacing. Deterministic and append-only (never drops a move), writes directly to the base Ruleset YAML via the project's own writer, and previews with a dry-run first. Use when you have a move and an idea of which Pokémon should learn it and roughly when (by level). NOT for designing the move itself (/move-design) or LLM-drafting one species' whole learnset (/learnset-suggest).
argument-hint: "<move> --types T[,T] --split physical|special [--preset early|mid|late | --levels MIN-MAX]"
disable-model-invocation: true
---

# Move Distribute

Roster-wide, **deterministic** distribution of one move across the base Ruleset.
You bring a move (already created) plus a rule for *who* learns it (type + attack
split) and *when* (a level window). The skill drops the move into the widest gap
of that window per species, so it never lands on an occupied level and keeps
breathing room from neighbors.

This is the captured, repeatable version of the Clod Toss distribution. It is the
right tool whenever you think "I want a Ground physical early-game move on the
right Pokémon," or the same for a mid- or late-game move of any type and split.

## Quick start

```
# Reproduce the Clod Toss run:
/move-distribute "Clod Toss" --types Ground --split physical --levels 4-14

# A mid-game special Water move:
/move-distribute surf --types Water --split special --preset mid

# Early move a caught-evolved mon should also have (parks it at L1 on evolutions):
/move-distribute "Mach Punch" --types Fighting --split physical --preset early --evolved-at-1
```

Always run with `--dry-run` first (the skill does this by default before any
write) — it prints the full recipient table and writes nothing.

## How it works

The skill shells out to its engine script:

```
.venv/bin/python .claude/skills/move-distribute/distribute_move.py <move> <flags>
```

1. **Resolve the move** — accepts a display name (`"Clod Toss"`) or `chrooked_id`
   (`clodtoss`). Errors if the move doesn't exist yet (create it via `/move-design`).
2. **Select recipients** — every species whose type list includes any `--types`
   value AND matches the `--split` predicate over base atk/spa.
3. **Place the move** — into the widest gap of the level window (earliest level on
   a tie). With `--evolved-at-1`, evolved forms instead get it at level 1.
4. **Write** — through the project's `species_yaml` writer, preserving every other
   Override field (abilities, stats, typing, evolution). New recipients get a new
   learnset-only Override file.

## Parameters

- `move` (required) — display name or `chrooked_id`. Must already exist.
- `--types T[,T]` (required) — a species matches if it has **any** listed type.
- `--split` — `physical` (atk≥spa, default), `special` (spa≥atk),
  `strong-physical` (atk>spa), `strong-special` (spa>atk), or `any`.
- `--preset early|mid|late` — window shorthand: early `4-15`, mid `16-35`,
  late `36-55`. Default `early`.
- `--levels MIN-MAX` — explicit window (overrides `--preset`). Level numbers are
  the real metric; presets are just shorthand.
- `--evolved-at-1` — park the move at L1 on evolved forms for Move Reminder access
  (use for early-game moves a fully-evolved catch should still know).
- `--include-legendaries` — keep legendaries/paradox/mythicals (excluded by default).
- `--include-megas` — keep Mega/Primal forms (skipped by default; they share the
  base species learnset).
- `--exclude id1,id2` — drop specific `chrooked_id`s from the recipient set.
- `--dry-run` — print the table, write nothing.

## Invariants

- **Append-only — never drops a move.** The engine asserts the new learnset is the
  old one plus the distributed move. This is the guardrail the original two-pass
  Clod Toss attempt lacked (it clobbered Mud-Slap / Payback). If the assert ever
  fires, nothing for that species is written and the run stops.
- **Idempotent.** A species that already has the move is reported and skipped, so
  re-running is safe.
- **Gap placement, never a collision.** The chosen level is the one in the window
  farthest from any existing move; it only sits adjacent to a neighbor when the
  learnset is too dense for a real gap (acceptable at low levels).
- **Base Ruleset only.** Writes to `ruleset/species/*.yaml`. Never touches a Target
  (africanvs etc.) — that only happens through `apply`, one-directional.
- **Preview then write.** Default to `--dry-run`, show the table, get a yes, then
  write. The user reviews `git diff` and commits; this skill does not commit.

## Verify after writing

```
# No move lost vs HEAD, ruleset still loads, adjacency report:
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0,'src')
from chrooked_pokedex.model.ruleset import Ruleset
print('Ruleset loads:', len(Ruleset.load('ruleset').species), 'species')
PY
```

Then refresh the web UI (Cmd+Shift+R) — the species dex only re-fetches after
UI-driven edits, so on-disk script writes need a hard refresh to show up.

## Edge cases & gotchas

- **Cross-type evolution lines.** A line whose pre-evos are a *different* type
  (Nidoran♀/♂ are Poison, only Nidoqueen/Nidoking are Ground) won't have its
  pre-evos caught by a type filter. Distributing for the final type leaves a gap
  in the early line — top it up with a second run (`--types Poison ...` scoped via
  `--exclude`) or a manual edit. The Clod Toss Nidoran add-on was exactly this.
- **`fully_evolved` vs `evolved`.** "Evolved form" here means *appears as another
  species' evolution target* — that's what `--evolved-at-1` keys on.
- **Legendary list is curated.** It's a best-effort dex-number set in the script;
  the recipient table shows everything included, so eyeball it and top up the set
  or use `--exclude` if a straggler slips through.

## Out of scope

- **Designing the move** → `/move-design`.
- **One species' whole learnset (LLM-drafted)** → `/learnset-suggest`.
- **Applying to a Target game** → the `apply` CLI.
