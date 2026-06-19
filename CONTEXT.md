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
