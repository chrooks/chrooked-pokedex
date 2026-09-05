---
name: ability-distribute
description: Distribute one EXISTING ability across the dex by ecological / lore fit — scan real dex text for a theme (nocturnal, burrowing, venomous…), screen by explicit dex claims, fit against what the ability mechanically rewards, propose per-line slots in a table, then write whole lines, apply to Rejuv, read back. Use when the user wants an ability "given to everything that is X", asks who else should have an ability, or invokes /ability-distribute. NOT for creating the ability (/ability-create) or for moves (/move-distribute).
argument-hint: "<ability name> [theme keywords...]"
disable-model-invocation: true
---

# Ability Distribute

Captured from the Night Stalker run (2026-09-04): 95 candidates → 11 lines.
Lore is **sourced, never remembered** — every claim in the table traces to a dex
sentence the scan printed.

## Quick start

```
/ability-distribute "Night Stalker" nocturnal night darkness dusk
```

## Workflow

1. **Name the mechanic's beneficiary.** Read the ability. Offensive (crits, power) →
   only predators and strikers qualify. Defensive → only walls. Write this down
   before scanning; it is the screen in step 4.
2. **Candidates.** Two sources, merged:
   - the dex: `POST /api/abilities/{id}/distribute` with `{"prompt": "<theme>",
     "limit": 30}` — the LLM proposes families from the in-dex roster (read-only);
   - your own list of lines whose ecology fits.
   Whole lines only. Forms use their form id (`lycanrocmidnight`); a miss is a
   real gap — report it.
3. **Scan.** `.venv/bin/python .claude/skills/ability-distribute/scan_lore.py
   --keywords "k1,k2,…" <ids>` (or `--all` once to prime the cache for the whole
   dex). It prints, per species: types, current three slots, and the dex sentences
   that hit. Nothing that is not in that output goes in the table.
4. **Screen.** Keep a line only when a dex sentence makes the explicit claim
   ("active at night", "hunts in darkness"), not colour or habitat. Then apply the
   step-1 beneficiary test. Skip lines whose current trio already carries the same
   mechanic (Virulence already crits) or a signature the theme belongs to (moon
   lines keep Full Moon).
5. **Table.** `/table md`: Line · Slot 1 · Slot 2 · HA · Recommendation · Why.
   Recommendation names the slot and what it displaces; Why quotes the dex. Mark
   optional rows. House rules: starters keep Overgrow / Blaze / Torrent in slot 1;
   an empty HA is the free slot; displace the most generic ability, never a niche
   (Long Reach, Aerodynamic on a bug).
6. **Show your work.** A funnel: candidates → fetched → mention theme → explicit
   claim → pass the mechanic screen → final. Name the ids that failed to resolve.
7. **Confirm.** Preview first, decision from the user's reply. Fold edits.
8. **Write + apply + read back.** One call:
   `.venv/bin/python .claude/skills/ability-distribute/write_lines.py "<Ability>"
   id=slot id=slot …` — PUTs every stage, runs the **host CLI** apply against the
   Rejuv target, and diffs each written slot in `montext.rb`. Exit 1 = stop.
9. **Design log + commit + push.** Append to `ruleset/DESIGN-LOG.md`: rename
   decisions, method funnel, distributed lines with slots, rejected lines with
   the reason, user corrections near-verbatim. Then `/commit`.

## Invariants

- Read-only until step 8. The write path is the CRUD Seam, never YAML by hand.
- Whole evolution lines. A branch-shared pre-evo is opt-in.
- Apply from the host CLI. The dex container's image lags `references/rejuv-harness/`.
- A green Apply Report is not proof; the slot read-back is.
- If the theme's name stops matching who benefits (a crit ability called
  "Nocturnal" that only serves predators), raise the rename before distributing.
