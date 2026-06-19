---
name: learnset-suggest
description: Suggest a complete level-up learnset (or surgically edit one move) for a species from chat, using the running chrooked-pokedex backend. Calls the same proposal endpoint the editor UI will use (one Seam), shows the proposed {level, move, reasoning} rows + rationale + alternatives, and on your confirmation writes the learnset Override through the existing CRUD API. Never writes without confirmation. Use when the user wants to draft or revise a learnset for a species in this Ruleset.
argument-hint: "<species-chrooked-id> [full|surgical] [instruction...] [-- direction...]"
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
```

- `<species-chrooked-id>` (required) — the species' `chrooked_id` (e.g. `goodra`).
- `full|surgical` (optional, default `full`) — which mode to use.
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

## Why this shares the Seam (reuse note)

The propose endpoint, the `{draft, rationale, alternatives}` contract, and the
accept-through-CRUD path are the reusable foundation built in issues #6 (ability) and
#32 (typing + stats). This skill and the later editor UI (#37) are two clients of the
**same** backend Seam — no prompt drift between chat and UI. The accept path is always
`PUT /api/species/{id}` → the loader Boundary.
