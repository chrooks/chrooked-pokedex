# Lexicon (chrooked-pokedex project)

Engine-neutral terms for this project. These take precedence over the global
Lexicon when the same term appears in both. Plain-language definitions, because
none of these are ordinary English.

## Terms

**Ruleset**:
The engine-neutral data set that is the single source of truth for Chris's
preferred Pokémon changes. A folder of hand-editable YAML files under `ruleset/`
describing changes with plain names (`Water`, `Poison Heal`), not engine symbols.
_Avoid_: patch, diff, mod, config.

**Override**:
One changed field relative to a baseline. The Ruleset stores only overrides —
fields that differ from unmodified pokeemerald — not a full copy of every
Pokémon. The exception is learnsets, which are stored whole.
_Avoid_: patch, delta, change.

**Status**:
A status condition a Pokémon can carry — burn, frostbite, paralysis. A Ruleset
kind of its own under `ruleset/status/`, owned outright rather than stored as an
[[Override]]: the base snapshot has no status data to diff against. A Status
record is data only; its mechanic lives in a behavior spec.
_Avoid_: condition, ailment, effect.

**Reskin**:
Replacing what an engine symbol *does* and *says* while leaving the symbol
itself in place. Frostbite is a reskin of Rejuv's `:FROZEN`: the mechanic and the
player-facing text change, the symbol does not, so every existing move, item, and
battle rule that names it keeps working untouched. The alternative — renaming the
symbol — touches every reference and breaks save compatibility.
_Avoid_: rename, refactor, swap.

**chrooked_id**:
A short stable slug Chris owns that identifies a thing across all engines
(`goodra`, `excalibur`, `striker`). It is the join key. New content he invents
gets one for free.
_Avoid_: key, name, identifier.

**Applier**:
A program that reads the Ruleset and writes it into one target engine's files.
The pokeemerald Applier writes C; a future Essentials Applier would write PBS text.
_Avoid_: patcher, writer, exporter.

**Resolution map**:
A per-Applier lookup from `chrooked_id` to that engine's symbol, for example
`goodra -> SPECIES_GOODRA`. Partly auto-derived from `aka:` hints in the Ruleset,
partly hand-confirmed for odd cases.
_Avoid_: symbol table, mapping, lookup.

**Apply Report**:
The human-readable output of an apply run. Lists every entry as applied, blocked
(whole entry could not land), or partial (entry landed but one referenced field
could not). Apply never silently drops anything.
_Avoid_: log, summary, output.

**Harvest**:
A separate, deliberate command that reads a fork, compares it against the Ruleset,
and proposes edits back into the Ruleset for per-field confirmation. It is how good
in-game tuning gets pulled into canon. It is never part of a normal apply.
_Avoid_: reverse-sync, import, pull.

**Fork**:
A copy of pokeemerald-expansion with changes layered on. `dreamstone-mysteries`
is a Fork.
_Avoid_: clone, branch, copy.

**Target**:
A specific game on disk that an Applier writes the Ruleset into — a Fork
(pokeemerald engine) or a Pokémon Essentials fangame (essentials engine). Every
Target carries an engine. The CLI calls this `--target`.
_Avoid_: game, destination, fork (a Fork is one kind of Target, not a synonym).

**Target registry**:
The managed list of known Targets the frontend picks from — each a label, a path,
and an engine, registered once and reused. The frontend's "explorer" is this
registry, not a raw filesystem browser.
_Avoid_: explorer, game list, picker.

**Target Override**:
An Override that applies to one Target only, layered on top of the base Ruleset's
Override for the same `chrooked_id`. It exists because a Target can re-theme an
existing entry — Africanvs's Kricketune is the one KRICKETUNE slot wearing Gaul
flavor (different types, stats, Pokédex text), not a separate creature. The base
Ruleset stays canonical and applies everywhere; the Target Override only changes
how that entry lands when applying to that one Target. Read order is base
snapshot → base [[Override]] → Target Override, last wins per field.
_Avoid_: per-game patch, target diff, local override, regional form (it is not a
distinct entity — it shares the base entry's `chrooked_id`).

**Change Ledger**:
An append-only record of every mutation, one entry per change, so any edit can be
reviewed later (and, in a follow-up, reversed). It watches every writer: authoring
edits and [[Harvest]] record a field-level `from → to` diff; an apply records an
event with its [[Apply Report]] counts; a bulk seed records one summary line, not
per-entity spam. Each entry carries its `scope` (base or `target:<slug>`) and a
`source` (web-edit, harvest, apply, seed). Distinct from git history, which is
coarse and cannot name the scope of a change.
_Avoid_: log, audit trail, history, changelog.

**Canon dex**:
The full national Pokédex as the Ruleset sees it: the committed base 1.11.2
snapshot with the Ruleset's Overrides merged on top. Game-independent; always
renders. Distinct from a per-Target preview (a Target's own data with the Ruleset
previewed on top, a no-write dry run of an apply).
_Avoid_: pokedex, dex view, preview (a preview is the per-Target variant).

**In-Game Proof**:
Confirming an applied Ruleset change actually manifests or behaves in the running
game: apply → recompile under Wine → boot Africanvs → observe the change on real
hardware (Eelektross showing Water/Electric, Beautifly with Aerodynamic, a move's
secondary effect firing in a debug battle). The real-hardware acceptance step of the
apply pipeline, distinct from unit tests. The sampling technique used inside it is a
[[Spot-check]].
_Avoid_: smoke test, manual test, playtest.
