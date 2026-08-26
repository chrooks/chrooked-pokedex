---
name: blind-design
description: Design a species' typing, abilities, and move shortlist from its lore alone — anonymize the line's lore profile, hand it to a context-free agent with the merged move and ability pools (customs tagged), and relay a fresh kit proposal free of prior-art bias. Use when the user wants a "blind design", a fresh kit from lore, an anonymized design pass, or asks what a mon's kit SHOULD be based on what the creature is.
argument-hint: "<species-chrooked-id> [design steer]"
---

# blind-design — lore profile in, unbiased kit out

The prior-art trap: any designer who recognizes the species reaches for its canon
kit. This skill removes the name so the design comes from what the creature *is*.
Proven on the Staraptor line (2026-08-26): a blind agent reinvented the canon
competitive kit from lore alone, then improved on it with customs.

Pipeline: **lore profile → anonymize → pool dump → context-free agent → house-format
relay → hand off to the write skills.**

## 1. Get the lore profile

Run the `search-lore` flow for the line (whole line by default). If a profile was
already produced this conversation, reuse it — do not refetch.

## 2. Anonymize the profile

Write `creature-profile-anon.md` to the scratchpad. Rules:

- Strip every species/stage name, Japanese name, and the entire **Name origin**
  sections (they name the mon).
- Strip franchise markers: "Pokémon" as a category label, dex numbers, "Mega"
  (→ "an empowered variant"), other mons' names (→ a generic description:
  Steelix → "a giant serpent").
- Present stages as "Stage 1 / Stage 2 / Stage 3" with a plain role label
  ("small flocking songbird", "solitary raptor").
- **Keep** the real-world biology, the design-origin animals, and the myth
  references (the roc, the Imoogi) — that is the material the design pulls on.
- **Do not include** current typing, stats, abilities, or any game data. The
  agent infers typing from the lore; that inference is part of the output.

## 3. Dump the pools

The agent needs the real merged pools with customs tagged, or it will invent:

```bash
.venv/bin/python - <<'EOF'
from pathlib import Path
from chrooked_pokedex.web import dex as dexmod
from chrooked_pokedex.web import snapshot as snapmod
from chrooked_pokedex.model.ruleset import Ruleset
from chrooked_pokedex.web.learnset_skeleton import is_battle_gimmick

out = Path("<SCRATCHPAD>")  # the session scratchpad directory
snapshot = snapmod.load_snapshot(Path("ruleset/.base/1.11.2.json"))
ruleset = Ruleset.load(Path("ruleset"))

pool = [r for r in dexmod.build_move_pool(snapshot, ruleset) if not is_battle_gimmick(r)]
lines = []
for r in sorted(pool, key=lambda r: r["move"]):
    eff = (r.get("effect") or "").replace("\n", " ")
    desc = (r.get("description") or "").replace("\n", " ")[:90]
    tag = " [CUSTOM]" if r.get("custom") else ""
    lines.append(f"{r['move']} | {r.get('type')} | {r.get('category')} | BP {r.get('power')} | acc {r.get('accuracy')} | {eff} | {desc}{tag}")
(out / "moves-pool.txt").write_text("\n".join(lines) + "\n")

abilities = dexmod.build_abilities(snapshot, ruleset)
alines = []
for a in sorted(abilities, key=lambda a: a["name"]):
    tag = " [CUSTOM]" if a.get("custom") else ""
    alines.append(f"{a['name']} | {(a.get('description') or '').strip()}{tag}")
(out / "abilities-pool.txt").write_text("\n".join(alines) + "\n")
EOF
```

## 4. Spawn the context-free agent

One `general-purpose` agent. It gets **nothing** but the three file paths and this
task shape (adapt the bracketed parts; keep the constraints verbatim):

> You are doing a blind creature-design exercise for a Pokémon-style fan game.
> You have NO context beyond the three files named below. Do not try to identify
> which existing creature this profile might describe — design purely from the
> profile.
>
> Read fully: [profile path], [abilities-pool path], [moves-pool path].
> [CUSTOM]-tagged entries are net-new bespoke content.
>
> For the FINAL STAGE, propose from the pools only — never invent a name:
> A. ABILITIES — 5–8 candidates, one line of reasoning each tied to a specific
> profile fact. Mark primary / secondary / hidden picks. [CUSTOM] on equal
> footing — prefer it when it fits at least as well.
> B. MOVES — 25–35 level-up-worthy moves grouped by role: STAB-flavored attacks
> (pick the types YOU think fit and say why), predation/flavor coverage, lean
> utility. Half-line reason each; flag moves that pay off a proposed ability.
> Plus one short paragraph naming the one or two profile facts you treated as
> the design axis.
>
> Your final text IS the deliverable — structured markdown, no files.

Add the user's steer (if any) as one extra line, never as extra context about the
species.

## 5. Relay in house format

Never pass the agent output through raw. The relay is exactly three parts:

1. **Design decisions** — one ASD-STE100 paragraph (short active sentences) on
   the design axis and the typing inference.
2. **Abilities** — a bulleted list: `**Name — slot.** Justification.` Bench picks
   after the slotted three.
3. **Moves** — ONE table: `Move | Role | Reason | Pays off`.

If the blind kit converges with the mon's canon kit, say so — that is evidence
the profile carries the identity, and worth one line.

## 6. Hand off — this skill never writes

On the user's picks:

- Abilities → merge-PUT `abilities: {primary, secondary, hidden}` through
  `PUT /api/species/{id}` (whole line, per the evolution-line default).
- Learnset → `/learnset-suggest` with the user's chosen anchors from the
  shortlist as the direction mandate.
- Typing changes are the user's explicit call — surface the agent's inferred
  typing as a parked one-liner, never write it silently.

## Boundaries

- Read-only until the user picks; the write paths are the existing suggest
  skills and the CRUD Seam — never a second write path here.
- The agent is single-use; keep its id in case the user wants an iteration.
- Anonymization is best-effort against inference, not cryptography — a
  distinctive design-origin animal can still identify the mon. That is fine;
  the point is removing the *reflex*, not the possibility.
