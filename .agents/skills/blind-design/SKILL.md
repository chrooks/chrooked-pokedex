---
name: blind-design
description: Design a species line's abilities, learnset (and on request stats, typing, or one custom move/ability) from its lore alone, then carry the approved kit all the way to a pushed commit — anonymize the line's lore profile, hand it to a context-free agent with the merged move and ability pools (customs tagged), relay a fresh kit free of prior-art bias in the house lore-table format, take the user's picks, write the whole line through the CRUD API, apply to Rejuv, read back, log, commit, push. Use when the user wants a "blind design", a fresh kit from lore, or asks what a mon's kit SHOULD be based on what the creature is.
argument-hint: "<species or line> [steer...]"
disable-model-invocation: true
---

# blind-design — lore profile in, unbiased kit out, pushed commit at the end

The prior-art trap: any designer who recognizes the species reaches for its canon
kit. This skill removes the name so the design comes from what the creature *is*.
Proven on Staraptor (2026-08-26) and on seven lines in one session (2026-09-04..06:
Lilligant, Gogoat, Houndstone, Noctowl, Gengar, Garchomp, Tyranitar): the blind
agent re-derived canon abilities word for word (Rough Skin, Shadow Tag, Sap Sipper)
and then improved on them with customs.

Pipeline: **lore → anonymize → pool dump → context-free agent → lore-table relay →
picks → write the line → apply → read back → log → commit → push.**

## 1. Lore

Run `search-lore` for the whole line. Reuse a profile already produced this
conversation.

## 2. Anonymize → `.cache/lore/profiles/<final-id>.md`

Persist it there (gitignored with the cache); a rerun reuses it. Rules:

- Strip every species/stage name, Japanese name, and the whole **Name origin**.
- Strip franchise markers: "Pokémon" as a label, dex numbers, "Mega" → "an
  empowered variant", other mons → a generic description (Steelix → "a giant serpent").
- Stages as "Stage 1 / 2 / 3" with a plain role label; regional variants as
  "Variant A / B" under the final stage, each designed separately.
- **Keep** real-world biology, design-origin animals, myth references. That is the
  material the design pulls on.
- **No** typing, stats, abilities, or game data. The agent infers typing.

## 3. Pools

Dump once per session with `pool_dump.py` (bundled here); it writes
`moves-pool.txt` and `abilities-pool.txt` with `[CUSTOM]` tags to the scratchpad:

```bash
.venv/bin/python .claude/skills/blind-design/pool_dump.py <SCRATCHPAD>
```

Re-dump after creating an ability or move mid-session.

## 4. The context-free agent

One `general-purpose` agent, nothing but the three file paths and this shape
(keep the constraints verbatim; adapt the brackets):

> You are doing a blind creature-design exercise for a Pokémon-style fan game.
> You have NO context beyond the three files named below. Do not try to identify
> which existing creature this profile might describe — design purely from the
> profile.
>
> Read fully: [profile], [abilities-pool], [moves-pool]. [CUSTOM]-tagged entries
> are net-new bespoke content.
>
> For the FINAL STAGE, propose from the pools only — never invent a name [— EXCEPT
> in section C]:
> A. ABILITIES — 5–8 candidates, one line of reasoning each tied to a specific
> profile fact. Mark primary / secondary / hidden. [CUSTOM] on equal footing.
> B. MOVES — 25–35 level-up-worthy moves grouped by role: STAB-flavored attacks
> (pick the types YOU think fit and say why), predation/flavor coverage, lean
> utility. Half-line reason each; flag moves that pay off a proposed ability.
> Never include Glaive Rush or Precipice Blades.
> [C. ONE NEW CUSTOM — exactly one brand-new move OR ability that best completes
> the kit: which kind and why, working name, terse pool-style description, exact
> mechanic, the profile facts it is built from, the closest pool entry and why it
> is not a duplicate.]  ← only when the user said the mon deserves something custom
> [D. STATS — a six-stat spread in the BST band the user gave, one line per stat.]
> [E. BATTLER ROLE + a "defense of connection": one sentence per pick tracing it
> to a quoted profile fact.]  ← only when asked
> Plus one short paragraph naming the one or two profile facts you treated as the
> design axis.
>
> Your final text IS the deliverable — structured markdown, no files.

Add the user's steer as one extra line, never as context about the species. Keep
the agent id; the user may want an iteration.

## 5. Relay — the lore-table format (default)

Never pass the agent output through raw. Four parts:

1. **Lore profile table** — `Stage | Ecological role | Fantastical element`.
   *Ecological role* means **habitat + ecosystem niche** (biome, what it eats, what
   eats it, apex / prey / engineer), sourced, inferences labeled. It is NOT a list of
   dex behaviors — those go in a "most representative dex facts" line if wanted.
2. **How the profile becomes mechanics** — 3–4 ASD-STE100 sentences: the design
   axis, and how it translates to slots and ladder. State the agent's inferred
   typing and park it as the user's call. Say when the kit converged with canon.
3. **Abilities** — `**Name — slot.** Justification.` then the bench, then the
   current trio for contrast.
4. **Moves** — ONE table `Move | Role | Reason | Pays off`. When a learnset preview
   follows, that table is `Lv | Move | Type | BP` with **STAB bold** and *the mon's
   own types italic*.

Custom proposal, stats, battler role, and defense of connection are extra parts
only when they were asked for. Close with the decisions: typing (only if the user
opened it), ability trio, custom yes / no, anchors. Typing and stats stay untouched
unless the user says so.

## 6. Picks → write the line (this skill owns the tail)

1. **New custom first.** Ability → `/ability-create` (propose, preview, PUT ability
   + behavior stub, Rejuv plugin in `references/rejuv-harness/`; compose via
   `behaviors: [part, vanillapart]` in the ability YAML when it is two existing
   effects). Move → PUT `/api/moves/{id}`; a two-typed move needs only
   `second_type` (Rejuv is native); a bespoke effect needs a behavior spec plus a
   `CHROOKED_MOVE_ON_DEAL` plugin. Never prepend `pbInitPokemon` (zz_zcompose
   aliases it). Names: offer three to five; when the user dislikes one, run a
   meaning-similar word search (Datamuse `?ml=`) and offer the filtered hits.
   Re-dump the pools afterwards.
2. **Abilities** → merge-PUT the trio to every stage of the line (branch-shared
   pre-evos are opt-in). Megas keep their own ability.
3. **Learnset** → `POST /api/species/{final}/suggest/learnset` with `anchors`
   (max 8 — the rest the user named get folded by hand) and a `direction` built
   from the axis and the abilities. Preview as the `Lv | Move | Type | BP` table.
   Hand-rework before showing: no move at L0 AND a later level; no Glaive Rush or
   Precipice Blades; spread pileups (five fangs at L61–67); Dragon Dance very late,
   Swords Dance mid-game; a 100 BP STAB rung may give way to coverage; folds keep a
   2-level gap; the user's late capstones stay in order. Relay every `anchor:`
   warning. Confirm gate: preview first, decision from the user's reply.
4. **Write + apply + read back** in one call:

   ```bash
   .venv/bin/python .claude/skills/blind-design/line_write.py <final> \
     --rows "0:Move,1:Move,5:Move,…" [--abilities "P,S,H"] [--stats hp=65,atk=95,…]
   ```

   It writes the final stage, the pre-evos minus L0, and the megas with L0; runs the
   **host CLI** apply (the dex container lags the harness); fails on any `partial`
   or `blocked` row for the line (a newer-gen move absent from Rejuv, e.g. Noxious
   Torque → swap in the Ruleset's custom equivalent); and diffs every stage's
   moveset in `montext.rb`. Exit 1 means stop, nothing is committed.
5. **Design log + commit + push.** `ruleset/DESIGN-LOG.md` gets: direction, typing
   decision, new mechanics with the rejected names, rejected lanes, the user's
   corrections near-verbatim. One commit for the Ruleset plus plugins, pushed.
   Report: proof first (the read-back), then what shipped, then the in-game check
   owed (the harness cannot run a battle).

## Boundaries

- One Seam: the suggest endpoints propose, the CRUD routes write, the applier
  applies. No hand-written YAML, no second prompt path.
- Anonymization is best-effort against inference. The point is removing the reflex.
- A blind typing that differs from canon or the Ruleset is a parked one-liner,
  never a silent write.
