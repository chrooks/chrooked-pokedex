---
name: makeover
description: Run a full species-line makeover end to end — lore research, typing, stats, abilities, learnset, pre-evo copy-down, auto-apply to the active Rejuv target, read-back verification, commit and push. Orchestrates the existing suggest skills (one Seam each); design steps keep their confirm gates, the tail (apply, verify, commit) runs automatically. Use when the user asks for a "makeover" of a species or line, or names a line and a rework intent.
argument-hint: "<species-chrooked-id> [direction...]"
disable-model-invocation: true
---

# Makeover — the full line-rework pipeline

One command for the flow that used to be driven by hand: `/species-suggest` →
`/ability-suggest` / `/ability-create` → `/learnset-suggest` → apply → verify → commit.
This skill **orchestrates**; every design stage delegates to the existing skill and its
backend Seam — no second prompt paths, no new endpoints.

The stages in order. Design stages (1–5) each end at their skill's normal confirm gate.
The tail (6–8) is **automatic** — do not ask.

## 1. Lore first

Follow the "Makeover opening move" in `species-suggest/SKILL.md`: research the line's
flavor, present **2–3 typing + role options**, let the user pick. Skip only if the user
already gave a clear direction.

## 2. Typing

`/species-suggest typing <final-evo> <picked direction>` — final evo first, per the
Evolution-line default in `CLAUDE.md`. On approval, write typing for the final evo and
copy it to every pre-evo (and per-form where the line has forms).

## 3. Stats

`/species-suggest stats <final-evo> <role direction>`. On approval, scale pre-evos by
the **same BST delta** against their canon BST, preserving the role emphasis (dump stat
stays low). Preview the whole line's spreads in one table before writing.

## 4. Abilities

Show the line's current abilities. If the role calls for a change, route through
`/ability-suggest` (existing abilities) or `/ability-create` (new ability — which may
add a behavior needing a Rejuv implementation; note it for stage 6). Same abilities on
every stage of the line.

## 5. Learnset

`/learnset-suggest <final-evo> line <direction>` — one LLM proposal for the final evo,
mechanical copy-down minus L0 rows to pre-evos, megas/forms mirror the base list.
Respect the hard pacing caps in that skill.

## 6. Apply to Rejuv — automatic

Once the last design stage is locked in, apply without being asked:

- If stage 4 created a **new behavior**, implement it in the Rejuv scripts first
  (`/port-behavior` or the behavior packet via `chrooked-pokedex behaviors`).
- Run the apply against the active Rejuv target (the registered Target; same path the
  user always uses). Surface the Apply Report — `partial`/`blocked` entries verbatim.

## 7. Read back — automatic

A green Apply Report is not In-Game Proof. For **each changed species**, read the
applied PBS entry from the target and diff it against the Ruleset expectation: types,
stats, abilities, learnset rows, evolutions. Form species (e.g. `cherrimsunshine`)
get checked individually — form-join bugs have shipped past the report before.
Any mismatch: stop, report it, fix before continuing.

## 8. Commit and push — automatic

`/commit` the Ruleset changes (one logical scope; behaviors/engine work may be a second
commit), then push. Lead the completion report with the read-back proof, then what
changed, then the commit hashes.

## Invariants

- **Design gates stay.** Never write a design stage without the user's explicit yes at
  that stage's preview. The automation is the tail, not the gates.
- **One Seam per stage.** Each stage calls its existing skill/endpoint; this skill adds
  no prompts or validation of its own.
- **Order is load-bearing.** Typing/stats/abilities before learnset (the learnset rubric
  reads them); behaviors implemented before apply (the Resolution map needs them).
- **Partial runs resume, not restart.** If invoked mid-line (e.g. typing already done),
  skip completed stages — check the current Override before proposing.
