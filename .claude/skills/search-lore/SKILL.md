---
name: search-lore
description: Gather every canon source on a species or a whole evolution line — dex entries, design origin, name etymology — and return one profile per stage covering its ecological role and its fantastical elements, plus the throughline shared across the line. Reads real sources via scripts/lore_probe.py; never invents flavor. Use when the user asks for the lore of a species or line, wants to know what a creature "is" before a makeover, or asks about a Pokemon's ecology, mythology, real-world basis, or name origin.
argument-hint: "<species-chrooked-id> [more-ids...] [--stage-only]"
---

# search-lore — what this creature actually is, from real sources

The research step that runs before any design decision. It answers two questions per
stage: **what does this thing do in a world** (ecological role) and **what about it
cannot be explained by biology** (fantastical elements).

Lore here is *sourced*, never remembered. With no source in front of it the model
invents plausible etymology — it once claimed Glalie comes from French *glace* when it
is glacier + goalie. Run the probe.

## 1. Resolve the line

Default to the **whole evolution line**, not the one species named. Walk it from the
snapshot:

```bash
.venv/bin/python -c "
import json
d = json.load(open('ruleset/.base/1.11.2.json'))['species']
cur = 'SPECIES_ID'
while d[cur].get('evolution'): cur = d[cur]['evolution']['from']
line = [cur]
while d[line[-1]]['evolves_into']:
    line += [e['to'] for e in d[line[-1]]['evolves_into']]
print(' '.join(line))
"
```

Branching lines (Eevee, Wurmple) come back with every branch — profile them all unless
the user named one. `--stage-only` skips the walk and profiles exactly the ids given.

## 2. Fetch the sources

One call per stage. The cap matters — the default truncates the design-origin section,
which is the most useful part of the whole block:

```bash
for s in <ids>; do .venv/bin/python scripts/lore_probe.py "$s" --cap 20000; done
```

It returns dex entries across every generation, Bulbapedia's **Design origin** and
**Name origin**, and the source URLs. Results cache in `.cache/lore/`; a second run is
offline. Delete a species' file there to refetch.

- **Forms map to their base species** (`marowakalola` → `marowak`), so a form profile
  inherits base flavor. Say so rather than passing it off as form-specific lore.
- A `LORE FETCH FAILED` or `found: False` is a real gap. Report it and fall back to web
  search — never fill the hole from memory without flagging it.

## 3. Profile each stage

One section per stage, always these two headings, in this order:

**Ecological role** — how it lives. Habitat, diet, what hunts it or what it hunts,
social structure, size and growth, and its relationship with people. Every line traces
to a dex entry. Prefer the concrete claim ("eats what sinks to the lake floor") over the
category ("aquatic predator").

**Fantastical elements** — what breaks physics or biology. Powers, omens, cults, the
myth it is built from. Name the real-world source when Bulbapedia gives one — the
Imoogi, the flaming pearl, the Yinglong — because that is the part a makeover can pull
on. Include the name etymology here when it carries meaning (*kairyū*, sea dragon).

Facts only in these two sections. Mechanics, stats, and design opinions stay out.

## 4. Close with the line throughline

3–5 bullets on what changes across the stages and what never does — the axis the line
is built on (Dratini's line: river bottom → lake surface → open sky, and benevolence at
every stage). This is the part a makeover direction is derived from, so it earns its own
section rather than being left implicit.

## Boundaries

- **Read-only.** This skill writes no YAML and calls no suggest endpoint. Handing the
  profile to `/species-suggest` or `/makeover` is the user's next move, not this one's.
- Megas and regional forms get a **short addendum** under the base stage, not a section
  of their own — their lore is a variation, not a separate creature.
- Keep it to what the sources say. An inference is allowed if it is labelled as one.
