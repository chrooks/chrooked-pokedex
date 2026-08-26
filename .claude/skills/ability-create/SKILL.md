---
name: ability-create
description: Create a brand-new custom ability from chat — describe the ability in plain words and get a complete proposal (a new owned ability + an engine-neutral behavior stub + a species-distribution plan), then on your confirmation write it through the existing chrooked-pokedex CRUD API. Calls the same propose endpoint the editor UI will use (one Seam), shows the ability + behavior stub (engine_hints left empty for your grounding pass) + the distribution table, and never writes without confirmation. Use when the user wants to invent a new ability for this Ruleset.
argument-hint: "<direction describing the ability...>"
disable-model-invocation: true
---

# Ability Create (chat)

Drive LLM-assisted **ability creation** from chat, against the **running backend** —
the `POST /api/abilities/suggest` endpoint. This is the first capability that *creates*
owned content (rather than picking or rewriting existing data) and the first that writes
to **three** places on accept. There is **one prompt path, one validation path**: the
server builds the rubric, calls the LLM Port, and validates the draft (a slugified id
that refuses to clobber, an engine-neutral behavior stub with **empty** `engine_hints`,
and a distribution plan validated against the dex). This skill is a thin chat client over
that Seam; it adds no second prompt and no second validation.

On your confirmation it writes via the existing CRUD routes **in order** —
`PUT /api/abilities/{id}` → `PUT /api/behaviors/{id}` → `PUT /api/species/{id}` ×N —
the loader is the gate, exactly as the UI's Save will be.

## Quick start

```
/ability-create a Water sponge that boosts Speed when hit by Water
/ability-create a contact-punisher that lowers the attacker's Attack
```

- `<direction>` (required) — a freeform description of the ability you want.

## Invariants

- **Never write without explicit confirmation.** The propose step writes nothing; the
  three writes run only after the user approves with an explicit yes.
- **Never author `engine_hints`.** The behavior stub leaves `engine_hints` **empty** —
  the C citation (pokeemerald) and the Essentials translation are a human grounding pass.
  The stub carries a "STUB — engine_hints ungrounded, needs human grounding pass" note.
  If the server returns a draft with a filled `engine_hints` it is a 422; never fill it
  yourself before the PUT.
- **Create never clobbers.** The new ability's `chrooked_id` is slugified from the name
  (lowercase, no separators). If it collides with an existing owned ability OR behavior
  id, the server returns a 422 with a `warnings` entry — relay it and ask the user to
  rename; do not overwrite.
- **Distribution is validated at propose time.** Every target species must exist in the
  dex and the slot must be one of `primary`/`secondary`/`hidden`. Each row's `replaces`
  shows the species' real current slot occupant. Zero species is valid (author now,
  distribute later).
- **Proposal-only fields.** `reasoning`, `replaces`, the `ai_rating`, and `warnings` are
  for your review; strip them before each PUT (the loader stores only the real fields).
  The AI rating is advisory — fold it into the behavior `notes` if the user wants it
  preserved on disk, but it is NOT an ability schema field.
- **One Seam.** Always call the backend endpoint. Do NOT re-implement the rubric or call
  an LLM directly from this skill.

## Prerequisites

- The backend is running (default `http://127.0.0.1:8000`; launch with
  `chrooked-pokedex ui`). Use `$CHROOKED_API` if the user set a different base URL.
- The provider key is set for the configured backend (e.g. `ANTHROPIC_API_KEY`). A
  missing key comes back as a clean **503** with an actionable message — relay it,
  do not retry blindly.

## Algorithm: propose → preview → confirm → accept

### 1. Propose (writes nothing)

```bash
curl -sS -X POST "${CHROOKED_API:-http://127.0.0.1:8000}/api/abilities/suggest" \
  -H 'content-type: application/json' \
  -d '{"direction": "a Water sponge that boosts Speed when hit by Water"}'
```

Handle the response by status:

- **200** → the reusable contract (see shape below).
- **422** → a validation problem (empty name, id collision, non-empty `engine_hints`,
  hallucinated species, invalid slot). Show the message (and any `warnings`), stop —
  nothing was written.
- **503** → a recoverable backend/LLM problem (missing key, provider/timeout). Show the
  honest message (it never contains the key), stop.

### 2. Preview in chat

**Ability-creation contract:**

```json
{
  "draft": {
    "ability":   { "chrooked_id": "tidalforce", "name": "Tidal Force",
                   "description": "Absorbs Water moves; gains Speed instead of damage." },
    "behavior":  { "name": "Tidal Force", "chrooked_id": "tidalforce", "applies_to": "ability",
                   "aka": {},
                   "effects": [ {"summary":"...","trigger":"on-hit","when":"...","effect":"..."} ],
                   "test_cases": [ {"given":"...","expect":"..."} ],
                   "notes": [ "STUB — engine_hints ungrounded, needs human grounding pass" ],
                   "engine_hints": {} },
    "distribution": [ { "species":"poliwag", "slot":"hidden", "replaces":"Water Absorb",
                        "reasoning":"thematic fit; underused line" } ]
  },
  "rationale": { "ability": "...", "ai_rating": "B+ — strong but fair", "distribution": "..." },
  "alternatives": [ {"value":"...","rationale":"..."} ]
}
```

Present:

- The **ability**: name + description.
- The **behavior stub**: its effects + test cases, and call out that `engine_hints` is
  empty — that is the human's grounding TODO, not a bug.
- The **distribution** as a table: species · slot · replaces · reasoning.
- The **AI rating** from `rationale.ai_rating` (advisory).

### 3. Confirm

**Preview first, question second.** The step-2 preview must be a plain chat message the
user has already read before any decision prompt appears. End the preview turn and take
the decision from the user's chat reply — never bundle the preview and an
AskUserQuestion dialog into the same turn; the dialog covers the options before they
can be read.

Ask the user to **approve, edit, or reject**:

- Approve as-is → go to step 4.
- Edit (rename the ability, drop/add a distribution row, change a slot) → adjust, then
  re-propose if the name changed (so the id + collision check re-runs), then step 4.
- Reject → stop. Nothing is written.

**Do not proceed to step 4 without an explicit yes.**

### 4. Accept — write through the existing CRUD API (in order, stop-and-report)

The partial state is always valid on disk (an uncited ability/behavior orphans nothing;
the citation guard is delete-side only), so **git is the undo**. On the FIRST failure,
stop and report exactly what landed vs. what didn't — no fake rollback.

**4a. Create the owned ability** (strip everything but the ability fields):

```bash
curl -sS -X PUT "${CHROOKED_API:-http://127.0.0.1:8000}/api/abilities/tidalforce" \
  -H 'content-type: application/json' \
  -d '{ "chrooked_id": "tidalforce", "name": "Tidal Force",
        "description": "Absorbs Water moves; gains Speed instead of damage." }'
```

**4b. Create the behavior stub** (PUT the `draft.behavior` as-is — `engine_hints` stays
`{}`; never fill it):

```bash
curl -sS -X PUT "${CHROOKED_API:-http://127.0.0.1:8000}/api/behaviors/tidalforce" \
  -H 'content-type: application/json' \
  -d '{ "name": "Tidal Force", "chrooked_id": "tidalforce", "applies_to": "ability",
        "effects": [ {"summary":"...","trigger":"on-hit","when":"...","effect":"..."} ],
        "test_cases": [ {"given":"...","expect":"..."} ],
        "notes": [ "STUB — engine_hints ungrounded, needs human grounding pass" ],
        "engine_hints": {} }'
```

**4c. Distribute — for EACH distribution row**, read the current Override, merge the new
ability into the chosen slot, and PUT the whole species (strip `replaces`/`reasoning`):

```bash
# 404 here means no Override yet → start from {name, chrooked_id}
curl -sS "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/poliwag"

curl -sS -X PUT "${CHROOKED_API:-http://127.0.0.1:8000}/api/species/poliwag" \
  -H 'content-type: application/json' \
  -d '{ "name": "Poliwag", "chrooked_id": "poliwag",
        "abilities": { "hidden": "Tidal Force" } }'
```

Handle each write response:

- **200** → relay what landed; continue to the next write.
- **422** → the loader rejected it; show its message verbatim, STOP. Report which writes
  already landed (e.g. ability + behavior wrote, species N did not) — the partial state
  is valid on disk and the same Boundary the UI's Save will hit.

Chris reviews `git diff` and commits himself; the skill never touches git.

## Why this shares the Seam (reuse note)

The propose endpoint, the `{draft, rationale, alternatives}` contract, and the
accept-through-CRUD path are the reusable foundation built in issues #6 (ability),
#32 (typing + stats), and #7 (learnset). This skill and the later editor UI (#37) are two
clients of the **same** backend Seam — no prompt drift between chat and UI. What is new
in #8 is that accept orchestrates THREE existing routes in order rather than one.
