---
name: learnset-suggest
description: Suggest a complete level-up learnset (or surgically edit one move) for a species from chat, using the running chrooked-pokedex backend. Calls the same proposal endpoint the editor UI will use (one Seam), shows the proposed {level, move, reasoning} rows + rationale + alternatives, and on your confirmation writes the learnset Override through the existing CRUD API. Never writes without confirmation. Use when the user wants to draft or revise a learnset for a species in this Ruleset.
argument-hint: "<species-chrooked-id> [full|surgical|line] [instruction...] [-- direction...]"
disable-model-invocation: true
---

# Learnset Suggest (chat)

Drive LLM-assisted learnset proposals from chat, against the **running backend** —
the `POST /api/species/{id}/suggest/learnset` endpoint. There is **one prompt path,
one validation path**: the server assembles the species context (stats, types, current
abilities with effect text, evo context, current learnset, merged move pool), builds
the rubric, calls the LLM Port, and validates the draft against the merged move pool +
level/repeat-move rules. This skill is a thin chat client over that Seam; it adds no
second prompt and no second validation. On your confirmation it writes via the existing
`PUT /api/species/{id}` CRUD route — the loader is the gate, exactly as the UI's Save
will be.

## Quick start

```
/learnset-suggest goodra
/learnset-suggest goodra full make it special-attack leaning
/learnset-suggest goodra surgical swap the L1 move for Pound
/learnset-suggest grotle line model the whole family on torterra
```

- `<species-chrooked-id>` (required) — the species' `chrooked_id` (e.g. `goodra`).
- `full|surgical|line` (optional, default `full`) — which mode to use. `line` proposes a
  coherent learnset for **every member of the evolution line** (see "Line mode" below).
- In `full` mode, an optional direction follows: freeform steer for the whole learnset.
- In `surgical` mode, the instruction follows (required): describes exactly which
  move(s) to change.

## Invariants

- **Never write without explicit confirmation.** The propose step writes nothing; the
  write step runs only after the user approves with an explicit yes.
- **Merged move pool only.** The server validates every proposed move against the real,
  merged move pool (base ⊕ Ruleset). An invented move name → 422. An edited move shows
  its current type/power; a created move is present.
- **Level rules.** Each level must be in [0, 100]. Level 0 = learned on evolution.
  A move may appear at most once at a non-zero level, plus optionally once at L0.
  Two non-zero levels for one move → 422.
- **Surgical untouched-rows guard.** In surgical mode the server asserts every row not
  targeted by the instruction is byte-identical to the current learnset. Any unexpected
  perturbation → 422.
- **Reasoning is proposal-only.** The `reasoning` field on each row is for your review;
  it is stripped before the PUT (the loader stores only `level` + `move`).
- **One Seam.** Always call the backend endpoint. Do NOT re-implement the rubric or
  call an LLM directly from this skill.
- **Evolution-line default.** If the species is part of an evo line, follow the
  "Evolution-line default" convention in `CLAUDE.md`: draft the **final evo's** learnset
  first, then copy it down to the pre-evos **verbatim** (`line` mode is the natural fit).
  A pre-evo learnset that differs from its final evo is an exception — state it explicitly.

## Prerequisites

- The backend is running (default `http://127.0.0.1:8000`; launch with
  `chrooked-pokedex ui`). Use `$CHROOKED_API` if the user set a different base URL.
- The provider key is set for the configured backend (e.g. `ANTHROPIC_API_KEY`). A
  missing key comes back as a clean **503** with an actionable message — relay it,
  do not retry blindly.

## Algorithm: propose → preview → confirm → accept

### 1. Propose (writes nothing)

**Full mode** (whole learnset from scratch):

```bash
curl -sS -X POST "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/goodra/suggest/learnset" \
  -H 'content-type: application/json' \
  -d '{"mode": "full", "direction": "special-attack leaning"}'
```

**Surgical mode** (change one targeted move):

```bash
curl -sS -X POST "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/goodra/suggest/learnset" \
  -H 'content-type: application/json' \
  -d '{"mode": "surgical", "instruction": "swap the L1 move for Pound"}'
```

Omit `direction` (or use `{}`) for a free-choice full learnset. Handle the response
by status:

- **200** → the reusable contract (see shape below).
- **404** → no such species; show the message, stop.
- **422** → a validation problem (hallucinated move, bad level, repeat-move violation,
  untouched-rows guard, missing surgical instruction). Show the message, stop — nothing
  was written.
- **503** → a recoverable backend/LLM problem (missing key, provider/timeout). Show
  the honest message (it never contains the key), stop.

### 2. Preview in chat

**Learnset contract:**

```json
{
  "draft": {
    "learnset": [
      {"level": 0,  "move": "Dragon Pulse",  "reasoning": "signature on-evo reward"},
      {"level": 1,  "move": "Tackle",         "reasoning": "basic early move"},
      {"level": 20, "move": "Dragon Breath",  "reasoning": "STAB progression"}
    ]
  },
  "rationale": {"learnset": "Designed around SPA-leaning special STAB..."},
  "alternatives": [
    {"value": "Aqua Jet @ L24 — priority STAB option", "rationale": "Speed insurance"}
  ]
}
```

Present the learnset as a table sorted by level, with the reasoning column:

```
Proposed learnset for Goodra:

  Lv  Move            Reasoning
   0  Dragon Pulse    signature on-evo reward
   1  Tackle          basic early move
  20  Dragon Breath   STAB progression

Rationale: Designed around SPA-leaning special STAB...

Alternatives:
  Aqua Jet @ L24 — priority STAB option — Speed insurance
```

### 3. Confirm

Ask the user to **approve, edit, or reject**:

- Approve as-is → go to step 4 with the draft learnset rows.
- Edit (swap in an alternative, adjust a level, drop a row) → adjust the rows, then
  step 4. Ensure every move name is in the real pool and levels are in [0, 100].
- Reject → stop. Nothing is written.

**Do not proceed to step 4 without an explicit yes.**

### 4. Accept — write through the existing CRUD API

Strip the `reasoning` field from each row before PUT — the loader stores only
`level` + `move`. Build a `[{level, move}]` list from the approved rows.

First read the current raw Override so you can merge only the learnset field without
clobbering other Override fields:

```bash
# 404 here means no Override yet → start from {name, chrooked_id}
curl -sS "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/goodra"
```

Then PUT the merged body with the approved learnset:

```bash
curl -sS -X PUT "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/goodra" \
  -H 'content-type: application/json' \
  -d '{
    "name": "Goodra",
    "chrooked_id": "goodra",
    "learnset": [
      {"level": 0,  "move": "Dragon Pulse"},
      {"level": 1,  "move": "Tackle"},
      {"level": 20, "move": "Dragon Breath"}
    ]
  }'
```

Handle the write response:

- **200** → the saved Override (overrides-only JSON). Confirm to the user what landed.
- **422** → the loader rejected the draft; show its message verbatim. Nothing was
  written — the same Boundary the UI's Save will hit.

Chris reviews `git diff` and commits himself; the skill never touches git.

## Line mode — suggest the whole evolution line

`line` mode proposes a coherent, stage-appropriate learnset for **every member of the
species' evolution line** in one flow. There is **no new endpoint**: it loops the same
`POST …/suggest/learnset` once per member, feeding each call the anchor's learnset and the
members already proposed (this run) through the existing `direction` field. Coherence
rides in `direction`; the chain is the loop.

A learnset is stage-specific, so each member gets its **own** stage-appropriate list — not
one list copied. Shared signature moves carry across members at scaled levels.

### Algorithm

1. **Resolve the line.** Fetch the dex once:

   ```bash
   curl -sS "${CHROOKED_API:-http://127.0.0.1:8000}/api/dex"
   ```

   Each merged entry carries `evolution` (backward `{from, method}`) and `evolves_into`
   (forward `[{to, …}]`). From the invoked species, walk `evolution.from` back to the base
   (no `evolution`), then walk `evolves_into[].to` forward. Keep the **linear chain through
   the invoked species**; for a branching tip (e.g. Eevee) take only the branch the invoked
   species sits on and note the others are skipped in v1. Order the chain base → tip.

2. **Anchor = the invoked species.** Its **current** learnset (from its dex entry) is the
   fixed reference every other member is modeled on.

3. **Propose each member in chain order.** For each member, call the existing endpoint,
   building `direction` from: the user's freeform steer (the text after `line`) + the
   anchor's learnset + the learnsets already proposed earlier in this run. Build the JSON
   with a file (apostrophes/quotes break inline `-d`):

   ```bash
   # write payload.json = {"mode":"full","direction":"<built text>"}
   curl -sS -X POST "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/<member>/suggest/learnset" \
     -H 'content-type: application/json' --data-binary @payload.json
   ```

   - **200** → keep the member's draft; add it to the running coherence context for the
     next member.
   - **422** → mark the member **blocked**, show the message, **continue** the chain (don't
     abort the others).
   - **503** → the LLM/key problem is global; stop and relay it.

4. **Preview every member** as a level-sorted table (the same shape as single-species
   mode), blocked members flagged. Show one combined rationale summary.

5. **One confirm gate** for the whole line. On an explicit yes, **PUT each approved member**
   exactly as single-species mode does (read raw Override → merge only `learnset` → PUT),
   looping over the approved members. Report what landed per member. Reject → write nothing.

**Draft capture invariant (the preview IS the write).** Each member's response must be
saved to a **unique, immutable** file (e.g. `<run-id>/<member>.json`) the moment it
returns — never a name reused across members or runs. Preview from that file, and PUT the
learnset read back from that **same** file. If you run calls in the background, wait for
each to fully complete (check the captured HTTP status, not a partial-JSON heuristic)
before previewing. A divergence between what was shown and what is written is a write
without consent — never let a late or duplicate call overwrite a draft mid-flow.

**The anchor and the write set.** Pick the anchor explicitly — it can be the invoked
species or any member the user names (e.g. "anchor on Arboliva"); its **current** learnset
is the coherence reference. By default the anchor is the reference only and is **not**
rewritten. If the user asks to **edit the whole line / include the anchor**, also propose
the anchor: run a suggest for it too (direction = the family theme + the members already
proposed), so every member gets a fresh draft while the anchor's *current* list still
seeds the coherence. Always say which members you'll write before the confirm.

## Distribute mode — one move across many species

`/learnset-suggest distribute <steer>` spreads an existing move (usually one just
created by `/move-design`) across many learnsets. This is **mechanical, not LLM-driven**:
no suggest calls, no per-species prompts. Candidates come from a dex scan, placement
from fixed rules, writes from the same read-Override → merge-learnset → PUT loop.

### Algorithm

1. **Curate candidates from the dex.** Scan `GET /api/dex` against the steer's criteria
   (typing, atk vs spa lean, abilities, flavor). Whole evolution lines by default —
   pre-evos included unless the user says otherwise. Skip megas, totems, cosplay/starter
   event forms, and legendaries/paradox unless asked. Present the list + placement rules
   and **wait for approval** (the normal confirm gate).

2. **Placement rules** (the house convention):
   - **Band.** Place the move inside a level band fitting its role — early-game moves
     ~6–16, mid-game utility ~22–40. Confirm the band with the user in the proposal.
   - **Spacing invariant.** A new row must land **≥3 levels from every existing row**.
     Prefer the free level nearest the band's anchor (mid-band, or the user's stated
     target level).
   - **No free slot → replace, prioritizing passive status moves.** Pick the in-band row
     nearest the anchor whose move is `category == "status"` (from `GET /api/moves`).
   - **Never silently eat an attack or a signature move.** If only non-status rows are
     in the band, or the auto-pick would take a STAB attack, a signature (Shed Tail,
     Milk Drink, recovery moves), or a move this session just placed — hand-pick a
     different victim (redundant coverage, junk utility) or relocate the new move
     (an L1 status slot is a legal fallback). Report every replacement in the summary,
     flagging hand-picks.
   - **Status-first beats theme-protection.** When both a status move and an attack sit
     in the band, replace the status move — even a thematic one (e.g. Poison Gas on the
     Drowzee line) — before touching any attack. Only signatures on the protect list
     above outrank the status-first rule.

3. **Write mechanically.** For each approved species: fresh merged learnset from the dex
   (NOT a stale snapshot — earlier writes this session change it), apply the placement,
   read the raw Override (404 → skeleton `{name, chrooked_id}`), PUT with only
   `learnset` merged. Skip a species whose learnset already contains the move.

4. **Report** — counts of inserts vs replacements, every replaced move by name, any
   species missing from the dex (form ids like `deerlingspring` vs `deerling`), and a
   reminder that a Rejuv apply is needed to land it in-game.

## Why this shares the Seam (reuse note)

The propose endpoint, the `{draft, rationale, alternatives}` contract, and the
accept-through-CRUD path are the reusable foundation built in issues #6 (ability) and
#32 (typing + stats). This skill and the later editor UI (#37) are two clients of the
**same** backend Seam — no prompt drift between chat and UI. The accept path is always
`PUT /api/species/{id}` → the loader Boundary.
