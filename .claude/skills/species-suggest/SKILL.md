---
name: species-suggest
description: Suggest a best-fit typing (1-2 types) OR a six-stat spread for a species from chat, using the running chrooked-pokedex backend. Calls the same proposal endpoints the editor UI uses (one Seam), shows the proposed values + rationale + alternatives, and on your confirmation writes the species Override through the existing CRUD API. Never writes without confirmation. Use when the user wants to brainstorm or pick a fitting typing or stat spread for a species in this Ruleset.
argument-hint: "<typing|stats> <species-chrooked-id> [direction...]"
disable-model-invocation: true
---

# Species Suggest — Typing and Stats (chat)

Drive LLM-assisted typing and stats proposals from chat, against the **running
backend** — the exact same `POST /api/species/{id}/suggest/typing` and
`POST /api/species/{id}/suggest/stats` endpoints the editor UI calls. There is
**one prompt path, one validation path**: the server assembles the species context,
builds the rubric, calls the LLM Port, and validates the draft against the real type
pool / stat range. This skill is a thin chat client over that Seam; it adds no
second prompt and no second validation. On your confirmation it writes via the
existing `PUT /api/species/{id}` CRUD route — the loader is the gate, exactly as
the UI's Save is.

## Quick start

```
/species-suggest typing goodra make it Water/Dragon for STAB on Liquidation
/species-suggest stats goodra faster special attacker
/species-suggest stats goodra
```

- `typing|stats` (required) — which capability to invoke.
- `<species-chrooked-id>` (required) — the species' `chrooked_id` (the dex join
  key, e.g. `goodra`).
- `[direction...]` (optional) — freeform steer, sent verbatim as the proposal
  `direction`. Omitting it triggers AUDIT mode for stats (the server evaluates the
  current spread for coherence). For typing, omitting direction lets the rubric
  choose the best fit freely.

## Invariants

- **Never write without explicit confirmation.** The propose step writes nothing;
  the write step runs only after the user approves. You — the loader — are still
  the gate.
- **Existing types only (typing).** The server validates the draft against the real
  type pool and rejects a hallucinated type with a 422.
- **Range-valid stats only (stats).** The server validates each stat value is an
  integer in [1, 255] and rejects anything out of range with a 422.
- **One Seam.** Always call the backend endpoint. Do NOT re-implement the rubric or
  call an LLM directly from this skill — that would fork the prompt away from the UI.
- **Evolution-line default.** If the species is part of an evo line, follow the
  "Evolution-line default" convention in `CLAUDE.md`: design the **final evo first**,
  then copy its typing/abilities/learnset down to the pre-evos and scale only stats by
  the same BST delta. Divergences are exceptions — state them explicitly.

## Makeover opening move — lore first, endpoint second

When the ask is an **open-ended makeover** (no direction given, e.g. "cufant line
makeover"), do NOT open with a cold endpoint call — a rubric guess with no flavor
grounding is how bad first proposals happen. Instead:

1. **Research the line's lore.** What kind of creature is it — dex flavor, name
   etymology, real-world inspiration, signature traits? Use what you know; search if
   thin.
2. **Present 2–3 makeover options**, each naming a **typing + role** grounded in that
   lore (e.g. "pure Steel physical wall — copper temple guardian"), one line of why
   each fits.
3. **Only after the user picks a direction**, call the endpoint with that pick as the
   `direction`.

When the user already gives a direction, skip straight to the endpoint as usual.

## Prerequisites

- The backend is running (default `http://127.0.0.1:8000`; launch with
  `chrooked-pokedex ui`). Use `$CHROOKED_API` if the user set a different base URL.
- The provider key is set for the configured backend (e.g. `ANTHROPIC_API_KEY`). A
  missing key comes back as a clean **503** with an actionable message — relay it,
  don't retry blindly.

## Algorithm: propose → preview → confirm → accept

### 1. Propose (writes nothing)

Choose the endpoint based on the first argument:

**Typing:**

```bash
curl -sS -X POST "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/goodra/suggest/typing" \
  -H 'content-type: application/json' \
  -d '{"direction": "make it Water/Dragon for STAB on Liquidation"}'
```

**Stats:**

```bash
curl -sS -X POST "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/goodra/suggest/stats" \
  -H 'content-type: application/json' \
  -d '{"direction": "faster special attacker"}'
```

Omit the body (or use `{}`) when no direction is given. Handle the response by status:

- **200** → the reusable contract (see shapes below).
- **404** → no such species; show the message, stop.
- **422** → a validation problem (hallucinated type, out-of-range stat, no valid
  proposal). Show the message, stop — nothing was written.
- **503** → a recoverable backend/LLM problem (missing key, provider/timeout error).
  Show the honest message (it never contains the key), stop.

### 2. Preview in chat

**Typing contract:**

```json
{
  "draft": {"types": ["Water", "Dragon"]},
  "rationale": {"types": "Strong STAB on Dragon Pulse; Water adds coverage."},
  "alternatives": [{"value": "Dragon", "rationale": "Pure Dragon is viable."}]
}
```

Present it as:

```
Proposed typing for Goodra:
  Water / Dragon  — Strong STAB on Dragon Pulse; Water adds coverage.

Alternatives:
  Dragon — Pure Dragon is viable.
```

**Stats contract:**

```json
{
  "draft": {"stats": {"hp": 90, "atk": 80, "def": 70, "spa": 130, "spd": 150, "spe": 80}},
  "rationale": {"stats": "Boosted SPA and SPE for faster special attacker role."},
  "alternatives": [{"value": "bulkier: hp+10 def+10 spe-10", "rationale": "Trades speed for bulk."}]
}
```

Present it as a stat table — include the current BST vs. proposed BST:

```
Proposed stats for Goodra (current BST 580 → proposed BST 600):

  HP  ATK  DEF  SPA  SPD  SPE
  90   80   70  130  150   80

Rationale: Boosted SPA and SPE for faster special attacker role.

Alternatives:
  bulkier: hp+10 def+10 spe-10 — Trades speed for bulk.
```

### 3. Confirm

**Preview first, question second.** The step-2 preview must be a plain chat message the
user has already read before any decision prompt appears. End the preview turn and take
the decision from the user's chat reply — never bundle the preview and an
AskUserQuestion dialog into the same turn; the dialog covers the options before they
can be read.

Ask the user to **approve, edit, or reject**:

- Approve as-is → go to step 4 with the draft values.
- Edit (swap in an alternative, adjust a single value) → adjust the values, then
  step 4. Re-validate edited values mentally against the range [1, 255] before
  sending — the loader will catch range errors anyway.
- Reject → stop. Nothing is written.

**Do not proceed to step 4 without an explicit yes.**

### 4. Accept — write through the existing CRUD API

The write is a `PUT /api/species/{id}` with a **partial** Override carrying only the
approved field set. `PUT` upserts, so to avoid clobbering the species' other Override
fields, first read the current raw Override, merge the approved values onto it, and
PUT the merged body back.

```bash
# Read the current raw Override (404 means no Override yet → start from {name, chrooked_id}).
curl -sS "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/goodra"
```

**Typing — merge types and PUT:**

```bash
curl -sS -X PUT "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/goodra" \
  -H 'content-type: application/json' \
  -d '{"name": "Goodra", "chrooked_id": "goodra", "types": ["Water", "Dragon"]}'
```

**Stats — merge stats and PUT (partial merge: only changed slots):**

```bash
curl -sS -X PUT "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/goodra" \
  -H 'content-type: application/json' \
  -d '{"name": "Goodra", "chrooked_id": "goodra", "stats": {"hp": 90, "atk": 80, "def": 70, "spa": 130, "spd": 150, "spe": 80}}'
```

Handle the write response:

- **200** → the saved Override (overrides-only JSON). Confirm to the user what landed.
- **422** → the loader rejected the draft; show its message verbatim. Nothing was
  written — the same Boundary the UI's Save hits.

Chris reviews `git diff` and commits himself; the skill never touches git.

## Why this shares the Seam (reuse note)

The propose endpoints, the `{draft, rationale, alternatives}` contract, and the
accept-through-CRUD path are the reusable foundation built in issues #6 (ability)
and #32 (typing + stats). This skill and the later editor UI are two clients of the
**same** backend Seam — no prompt drift between chat and UI. The accept path is
always `PUT /api/species/{id}` → the loader Boundary, whether the input came from
chat or the editor.
