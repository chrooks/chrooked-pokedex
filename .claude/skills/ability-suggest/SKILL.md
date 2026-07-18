---
name: ability-suggest
description: Suggest a best-fit EXISTING ability for a species from chat, using the running chrooked-pokedex backend. Calls the SAME proposal endpoint the editor UI uses (one Seam), shows the proposed ability + rationale + alternatives, and on your confirmation writes the species Override through the existing CRUD API. Never writes without confirmation. Use when the user wants to brainstorm or pick a fitting ability for a species in this Ruleset.
argument-hint: "<species-chrooked-id> [direction...]"
disable-model-invocation: true
---

# Ability Suggest (chat)

Drive the LLM-assisted ability proposal from chat, against the **running backend** —
the exact same `POST /api/species/{id}/suggest/ability` endpoint the editor UI calls.
There is **one prompt path, one validation path**: the server assembles the species
context, builds the ability-suggest rubric, calls the LLM Port, and validates the draft
against the real ability pool. This skill is a thin chat client over that Seam; it adds
no second prompt and no second validation. On your confirmation it writes via the
existing `PUT /api/species/{id}` CRUD route — the loader is the gate, exactly as the UI's
Save is.

## Quick start

```
/ability-suggest goodra make it a contact-punisher
```

- `<species-chrooked-id>` (required) — the species' `chrooked_id` (the dex join key,
  e.g. `goodra`).
- `[direction...]` (optional) — freeform steer, sent verbatim as the proposal `direction`.

## Invariants

- **Never write without explicit confirmation.** The propose step writes nothing; the
  write step runs only after the user approves. You — the loader — are still the gate.
- **Existing abilities only.** The server rejects a hallucinated ability with a 422; new
  ability creation is a separate capability (issue #8), out of scope here.
- **One Seam.** Always call the backend endpoint. Do NOT re-implement the rubric or call
  an LLM directly from this skill — that would fork the prompt away from the UI.
- **Evolution-line default.** If the species is part of an evo line, follow the
  "Evolution-line default" convention in `CLAUDE.md`: pick the **final evo's** abilities
  first, then copy the same ability kit down to every pre-evo. A pre-evo with different
  abilities is an exception — state it explicitly.

## Prerequisites

- The backend is running (default `http://127.0.0.1:8000`; launch with
  `chrooked-pokedex ui`). Use `$CHROOKED_API` if the user set a different base URL.
- The provider key is set for the configured backend (e.g. `ANTHROPIC_API_KEY`). A
  missing key comes back as a clean **503** with an actionable message — relay it, don't
  retry blindly.

## Algorithm: propose → preview → confirm → accept

### 1. Propose (writes nothing)

Call the proposal endpoint. The optional direction goes in the JSON body:

```bash
curl -sS -X POST "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/goodra/suggest/ability" \
  -H 'content-type: application/json' \
  -d '{"direction": "make it a contact-punisher"}'
```

Handle the response by status:

- **200** → the reusable contract:
  ```json
  {
    "draft": {"abilities": {"hidden": "Rough Skin"}},
    "rationale": {"hidden": "Punishes contact attackers; fits its bulk."},
    "alternatives": [{"value": "Hydration", "rationale": "Status immunity in rain."}]
  }
  ```
- **404** → no such species; show the message, stop.
- **422** → a validation problem (e.g. the model picked a non-existent ability, or the
  species has no valid suggestion). Show the message, stop — nothing was written.
- **503** → a recoverable backend/LLM problem (missing key, provider/timeout error). Show
  the honest message (it never contains the key), stop.

### 2. Preview in chat

Present the draft as a small table the user can read at a glance — the proposed slot(s)
with the rationale, then the alternatives:

```
Proposed for Goodra:
  hidden ← Rough Skin   — Punishes contact attackers; fits its bulk.

Alternatives:
  Hydration — Status immunity in rain.
```

### 3. Confirm

Ask the user to **approve, edit, or reject**:

- Approve as-is → go to step 4 with the draft slots.
- Edit (swap in an alternative, change the slot) → adjust the slots, then step 4.
- Reject → stop. Nothing is written.

**Do not proceed to step 4 without an explicit yes.**

### 4. Accept — write through the existing CRUD API

The write is a `PUT /api/species/{id}` with a **partial** Override carrying only the
approved field set. `PUT` upserts, so to avoid clobbering the species' other Override
fields, first read the current raw Override, merge the approved ability slots onto its
`abilities`, and PUT the merged body back:

```bash
# Read the current raw Override (404 means no Override yet → start from {name, chrooked_id}).
curl -sS "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/goodra"

# PUT the merged Override (abilities is a partial slot map: only changed slots).
curl -sS -X PUT "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/goodra" \
  -H 'content-type: application/json' \
  -d '{"name": "Goodra", "chrooked_id": "goodra", "abilities": {"hidden": "Rough Skin"}}'
```

Handle the write response:

- **200** → the saved Override (overrides-only JSON). Confirm to the user what landed.
- **422** → the loader rejected the draft; show its message verbatim. Nothing was written
  — the same Boundary the UI's Save hits.

Chris reviews `git diff` and commits himself; the skill never touches git.

## Why this shares the Seam (reuse note)

The propose endpoint, the `{draft, rationale, alternatives}` contract, and the
accept-through-CRUD path are the reusable foundation (issue #6). This skill and the
later editor UI are two clients of the **same** backend Seam — no prompt drift between
chat and UI. A future capability (#7 learnset, #8 new-ability, #9 move, #10 stats, #32
distribution) adds its own `suggest/<capability>` route with its own rubric + field set
and reuses this exact propose → preview → confirm → accept shape.
