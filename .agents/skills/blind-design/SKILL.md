---
name: blind-design
description: Batch blind design over the split-shift pipeline — queue lines in ruleset/QUEUE.md, `preprocess` researches and stages one packet per line unattended, `review` walks the packets one decision each, realizes previews in the background, ships every confirmed line with one apply, and commits one commit per line. A thin chat client over the /api/design router (the dex UI will drive the same routes later). Use when the user says "blind design", "preprocess the queue", "review my packets", or "queue <mon>".
argument-hint: "queue <row> | preprocess | review | status"
disable-model-invocation: true
---

# blind-design — queue → preprocess → review

The prior-art trap: any designer who recognizes the species reaches for its canon
kit. The server strips the name so the design comes from what the creature *is*.
This skill is a **thin client**: it renders, it parses Chris's replies, it calls
routes. It never writes YAML, never runs its own design prompt, never applies by
hand. One Seam: the `/api/design` router on the host server (`localhost:8000`,
started with `.venv/bin/chrooked-pokedex ui`; the hestia container lags the
harness, so apply and ship always go through the host).

    API=http://localhost:8000/api/design

## `queue <row>` — capture

Append the row verbatim to `ruleset/QUEUE.md`. One row per line; a steer after a
comma or ` - `; `&` joins lines designed together (`Mandibuzz line & Braviary line
together, mirrored`); regional prefixes work (`Alolan Ninetales`). Say nothing else.

## `preprocess` — the machine's shift, unattended

1. `POST $API/ingest` → report `created`, `existing`, and every `unresolved` row
   verbatim with its reason (a typo gets a "did you mean" hint; fix the row, never
   guess).
2. `POST $API/propose` → `{started: [...]}`. Poll `GET $API` every 30 s until no
   record is `proposing`. Records in a group travel together.
3. Report: counts by state, every packet `warnings` entry, every `error` record
   with its message. A queue with a `custom` in the steer gets a custom proposal.

## `review` — Chris's sitting, one decision per packet

Walk every `proposed` record in queue order. For each, render the packet in the
house lore-table format, four parts:

1. **Lore profile table** — `Stage | Ecological role | Fantastical element` from
   `packet.profile`. Ecological role means habitat + ecosystem niche.
2. **How the profile becomes mechanics** — 3–4 ASD-STE100 sentences from
   `packet.axis`; state `inferred_types` and park typing as Chris's call; say when
   the kit converged with `packet.current`.
3. **Abilities** — `**Name — slot.** Reason. Pro: … Con: …` for `packet.abilities`,
   then the bench, then `packet.current.abilities` for contrast.
4. **Moves** — one table `Move | Role | Reason | Pays off`, then the pre-drafted
   learnset as `Lv | Move | Type | BP` (**STAB bold**, *own types italic*) with its
   `warnings` and `lint` lines under it. `reference_stats` (a "mirror X BST" steer)
   and `current.stats` render as one stat table when present.

Custom (only when `packet.custom` exists): kind, mechanic, the five names. Close
with the decisions: typing (only if opened), trio, custom yes/no + name, anchors
and drops against the draft.

Take Chris's reply and translate it into the decisions schema — he answers by
exception, so start from the packet's trio and draft and apply his changes:

    {"typing": null | [...], "abilities": [p, s, h], "anchors": [...], "drop": [...],
     "custom": null | {"kind", "name", "mechanic", "written": false},
     "stats": null | {six} | {"delta": {...}}, "skip_pre": [...], "notes": "his words"}

`PUT $API/{id}/decisions` (auto-realizes in the background unless a custom is
pending). A 422 names the offending ability or move — fix and re-PUT. Move to the
next packet **immediately**; do not wait for the preview.

**Custom lane.** When the decisions carry a custom, before the PUT dispatch ONE
background `general-purpose` agent with: the mechanic and chosen name; the
`/ability-create` Seam (`POST /api/abilities/suggest` → `PUT /api/abilities/{id}`
→ `PUT /api/behaviors/{id}`; a move goes `PUT /api/moves/{id}`); the Rejuv plugin
conventions (`references/rejuv-harness/`, never prepend `pbInitPokemon`, hook
`CHROOKED_SWITCH_IN` / `CHROOKED_MAGIC_GUARD`); and the instruction to finish with
`PUT $API/{id}/decisions` re-sending the same decisions with `custom.written: true`
(that triggers realize). Names: when Chris dislikes one, Datamuse `?ml=` and offer
the filtered hits.

After the last packet, walk every `previewed` record: render `preview.learnset.rows`
as the `Lv | Move | Type | BP` table with `warnings`/`lint` under it and
`preview.stats` per stage. Take "go" → `POST $API/{id}/confirm`; a correction →
`POST $API/{id}/realize {"correction": "his words"}` and re-show when `previewed`.
Hand-check before showing: the anchors are all present, nothing from `drop`, no
`scrub:` note left unexplained.

## Ship — automatic once every preview has a "go"

1. Target id: `curl -s localhost:8000/api/targets | jq '.[] | {id,label}'` (Rejuv).
2. `POST $API/ship {"target_id": "<id>"}` (all `confirmed`). Synchronous; one apply.
   Per id the response is `{state, apply, readback, log_section, bad_rows}`; an
   `error` record names its bad rows or diff — report it, fix, ship again for that
   id (`"ids": [...]`). Shipped rows are removed from `ruleset/QUEUE.md` and the
   design log is already appended.
3. One commit per shipped line: its `ruleset/species/*.yaml` stages plus any custom
   ability / move / behavior / plugin files, message
   `feat(ruleset): <Line> line blind design — <one-line axis>`; the `DESIGN-LOG.md`
   and `QUEUE.md` changes ride with the last commit. Push.
4. Report: read-back proof first (MATCH per stage from `readback`), then what
   shipped per line, then the in-game check owed (the harness cannot run a battle).
   `POST $API/{id}/proof {"result": "proven"|"problem", "note"}` when Chris reports
   back from the game.

## `status`

`GET $API` → one table `id | state | activity | steer`.

## Boundaries

- One Seam: the router proposes, realizes, and ships; the CRUD routes write; the
  applier applies. No hand-written YAML, no second prompt path, no chat-side agent
  design call.
- Typing that differs from canon or the Ruleset is a parked one-liner, never a
  silent write. Nothing reaches `ruleset/` before a confirm except an approved
  custom.
- Deep dive on the pipeline: `.tasks/103-batch-blind-design/plan.md`.
