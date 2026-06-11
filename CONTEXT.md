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
