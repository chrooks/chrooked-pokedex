---
name: move-design
description: Design a brand-new custom move or propose edits to an existing move from chat — describe the move in plain words (specifics, comparative, or vibe) and get a complete proposal (full field set + optional engine-neutral behavior stub), then on your confirmation write it through the existing chrooked-pokedex CRUD API. Calls the same propose endpoint the editor UI will use (one Seam), shows the full draft with a before/after for edits, and never writes without confirmation. Use when the user wants to create a new move or edit an existing move's design.
argument-hint: "<direction describing the move...>"
disable-model-invocation: true
---

# Move Design (chat)

Drive LLM-assisted **move creation or editing** from chat, against the **running backend** —
the `POST /api/moves/suggest` endpoint. Accepts three input shapes:

- **Specifics**: "80 BP, 15 PP, Fairy special, 30% confuse"
- **Comparative**: "Thunderbolt but Dark type"
- **Vibe**: "Ground-type punching move with recoil"

Create mode (new owned move) when the name is new; edit mode (move Override) when
it targets an existing move. The draft covers all move fields; for edits, only the
changed fields are proposed and a before/after is shown before any write.

## Quick start

```
/move-design a Fairy-type special move, 90 BP, 15 PP, 30% chance to infatuate
/move-design Thunderbolt but Dark type with a flinch chance
/move-design --edit excalibur bump power from 90 to 100 and add the slicing flag
```

## Modes

- **create** (default): design a brand-new move. The name must not collide with an
  existing owned move id. The full field set (type, category, power, accuracy, PP,
  priority, target, flags, effect, additional_effects, description) is drafted.
- **edit**: propose changes to an existing move. Requires the move's `chrooked_id`
  as `move_id`. Only the changed fields are returned; the existing record is the
  baseline. A before/after table is shown.

## Invariants

- **Never write without explicit confirmation.** The propose step writes nothing; the
  write runs only after the user approves with an explicit yes.
- **Never author `engine_hints`.** If the move has a custom mechanic the draft may
  include a behavior stub — but `engine_hints` MUST stay empty. The C citation
  (pokeemerald) and the Essentials translation are a human grounding pass. If the
  server returns a draft with a filled `engine_hints` it is a 422; never fill it
  yourself before the PUT.
- **Create never clobbers.** The new move's `chrooked_id` is slugified from the name
  (lowercase, no separators). If it collides with an existing owned move id, the
  server returns a 422 — relay it and ask the user to rename; do not overwrite.
- **One Seam.** Always call the backend endpoint. Do NOT re-implement the rubric or
  call an LLM directly from this skill.
- **Distribution is OUT OF SCOPE here.** Adding a move to species learnsets is handled
  by `/learnset-suggest` (#7 territory) — propose and write only the move record.

## Prerequisites

- The backend is running (default `http://127.0.0.1:8000`; launch with
  `chrooked-pokedex ui`). Use `$CHROOKED_API` if the user set a different base URL.
- The provider key is set for the configured backend (e.g. `ANTHROPIC_API_KEY`). A
  missing key comes back as a clean **503** with an actionable message — relay it,
  do not retry blindly.

## Algorithm: propose → preview → confirm → accept

### 1. Propose (writes nothing)

**Create mode:**
```bash
curl -sS -X POST "${CHROOKED_API:-http://127.0.0.1:8000}/api/moves/suggest" \
  -H 'content-type: application/json' \
  -d '{"direction": "a Fairy-type special move, 90 BP, 30% confuse"}'
```

**Edit mode:**
```bash
curl -sS -X POST "${CHROOKED_API:-http://127.0.0.1:8000}/api/moves/suggest" \
  -H 'content-type: application/json' \
  -d '{"mode": "edit", "move_id": "excalibur", "direction": "bump power to 100"}'
```

Handle the response by status:

- **200** → the reusable contract (see shape below).
- **422** → a validation problem (empty name, id collision, non-empty `engine_hints`,
  unrecognized type, invalid range). Show the message and any `warnings`, stop —
  nothing was written.
- **503** → a recoverable backend/LLM problem (missing key, provider/timeout). Show
  the message, do NOT retry automatically.

### 2. Preview

Show the proposed move in a compact table. For **edit mode**, show a before/after
table of the changed fields only, followed by the full resulting payload.

For **create mode**, a full field summary:

| Field | Value |
|-------|-------|
| name | {{draft.move.name}} |
| type | {{draft.move.type}} |
| category | {{draft.move.category}} |
| power | {{draft.move.power}} |
| accuracy | {{draft.move.accuracy}} |
| pp | {{draft.move.pp}} |
| priority | {{draft.move.priority}} |
| target | {{draft.move.target}} |
| flags | {{draft.move.flags}} |
| effect | {{draft.move.effect}} |
| additional_effects | {{draft.move.additional_effects}} |
| description | {{draft.move.description}} |

If `draft.behavior` is present, show the behavior stub clearly marked as
**STUB — ungrounded** with its effects and test_cases. Never fill `engine_hints`
yourself — relay it empty so the human's grounding pass stays the authoritative
step.

If `warnings` is non-empty, surface each warning before asking for confirmation.
Surface `rationale.move` (and `rationale.edit` for edits) to help the user
evaluate the design intent.

Show `alternatives` as a brief "Other ideas considered" list.

### 3. Confirm

**Preview first, question second.** The step-2 preview must be a plain chat message the
user has already read before any decision prompt appears. End the preview turn and take
the decision from the user's chat reply — never bundle the preview and an
AskUserQuestion dialog into the same turn; the dialog covers the options before they
can be read.

Ask: **"Accept this move? (yes to write / no to cancel)"**

Wait for an explicit yes. Do not proceed on ambiguous input.

### 4. Accept (writes on confirmation only)

The `chrooked_id` is in the response root. Use it for the PUT path.

**Step 1 — Write the move:**
```bash
curl -sS -X PUT "${CHROOKED_API:-http://127.0.0.1:8000}/api/moves/{{chrooked_id}}" \
  -H 'content-type: application/json' \
  -d '<move payload>'
```

Strip proposal-only fields before PUT: `warnings`, `reasoning`, `chrooked_id` at
the root (it is inside the move payload already). The loader is the gate; a rejected
write writes nothing.

**Step 2 — Write the behavior stub (if present):**
```bash
curl -sS -X PUT "${CHROOKED_API:-http://127.0.0.1:8000}/api/behaviors/{{chrooked_id}}" \
  -H 'content-type: application/json' \
  -d '<behavior payload>'
```

Only call this step if `draft.behavior` was present in the response.
The stub has empty `engine_hints` — do NOT fill it before the PUT.

**Stop and report** after each write. If a write fails (4xx/5xx), show the error
and stop — do not proceed to the next step. Report what landed vs. what did not.

## Response shape

```json
{
  "draft": {
    "move": {
      "chrooked_id": "shadowstrike",
      "name": "Shadow Strike",
      "type": "Ghost",
      "category": "physical",
      "power": 80,
      "accuracy": 100,
      "pp": 10,
      "priority": 0,
      "target": "selected",
      "flags": ["contact"],
      "effect": "hit",
      "additional_effects": [{"effect": "flinch", "chance": 30}],
      "description": "A shadowy strike that may cause flinching."
    },
    "behavior": null
  },
  "rationale": {
    "move": "A reliable contact Ghost-type move with a flinch angle...",
    "edit": "(edit mode only) Changed power from 90 to 100 to..."
  },
  "alternatives": [
    {"value": "Shadow Claw variant", "rationale": "higher BP, no flinch"}
  ],
  "warnings": [],
  "chrooked_id": "shadowstrike",
  "before": null
}
```

In **edit mode** `before` contains the original values for the changed fields
(for your review); it is stripped before the PUT.
