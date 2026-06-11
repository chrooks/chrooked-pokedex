# Build chrooked-pokedex: an engine-neutral Pokémon ruleset with per-engine appliers

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with the ExecPlan rules in `/Users/cdbrooks/.claude/PLAN.md`. If that file is not in context, read it in full before revising this plan.

## Purpose / Big Picture

Chris has a set of preferred Pokémon changes — Goodra as a Water/Dragon with Poison Heal, Lopunny with Striker, Ice resisting Flying, Aegislash learning a custom Steel move called Excalibur, and roughly three hundred more edits across stats, typings, abilities, moves, evolutions, and the type chart. Today those changes live trapped inside one ROM hack, `dreamstone-mysteries`, a fork of the GBA decompilation project pokeemerald-expansion. He wants those changes to live in one place he owns, that he edits over time, and that he can re-apply to other games: other pokeemerald-expansion ROM hacks, and eventually Pokémon Essentials fangames (a completely different engine built in Ruby on RPG Maker XP).

A prior attempt, the Python tool at `/Users/cdbrooks/Development/Games/ROMs/pokeemerald-chrooked-patcher` (referred to here as "v1"), worked but had structural limits: it modeled changes as a *diff* between two pokeemerald forks, expressed in C symbols like `TYPE_FIRE` and `MOVE_*`. That coupling meant it could only target pokeemerald, could not author brand-new moves or abilities, never modeled the type chart, and merged learnset edits into a target's existing list — which produced Pokémon that learn the same move twice in a row.

After this change, Chris will have a new repository, `chrooked-pokedex`, containing: (1) a human-editable, engine-neutral data set called the **Ruleset** that is the single source of truth for his preferred Pokémon changes; (2) a **pokeemerald applier** that writes the Ruleset into any pokeemerald-expansion fork's C files; and (3) the design groundwork for a future Essentials applier. He will be able to run one command to apply his entire Ruleset onto a fresh ROM hack and get a build where Goodra is Water/Dragon, Aegislash knows Excalibur (a move the target game never had, created automatically), and so on — with a printed report of anything that could not be applied. Nothing is ever silently dropped.

You can see it working when, from the `chrooked-pokedex` directory, running the applier against a copy of a pokeemerald fork rewrites that fork's species, learnset, evolution, move, ability, and type-chart files, prints an Apply Report listing what landed and what was blocked, and the fork still compiles with `make`.

## Definitions (plain language)

Define-as-you-go, because none of these are ordinary English.

- **pokeemerald-expansion**: an open-source C codebase that recreates the Game Boy Advance game Pokémon Emerald and adds modern features. Game data lives in C source files as large structured tables. Chris's game `dreamstone-mysteries` is a copy of this codebase with his edits on top.
- **Fork**: a copy of pokeemerald-expansion with changes layered on. `dreamstone-mysteries` is a fork.
- **Pokémon Essentials**: an unrelated fan game engine. Most of its game data lives in plain text files called **PBS files** (for example `pokemon.txt`, `moves.txt`), which are far easier to edit than C. Some behavior needs Ruby code. This plan does not build the Essentials applier; it only avoids design choices that would block it.
- **Ruleset**: the new engine-neutral data set this plan creates. It is a folder of human-editable YAML files describing Chris's preferred Pokémon changes using plain names (`Water`, `Poison Heal`), not engine-specific symbols. It is the single source of truth.
- **Override**: one changed field relative to a baseline. The Ruleset stores only overrides — fields that differ from unmodified pokeemerald — not a full copy of every Pokémon. The exception is learnsets (see below).
- **chrooked_id**: a short stable slug Chris owns that identifies a thing across all engines, for example `goodra`, `excalibur`, `striker`. It is the join key. New content he invents (a custom move) gets a `chrooked_id` for free because he mints it.
- **Applier**: a program that reads the Ruleset and writes it into one target engine's files. The pokeemerald applier writes C; a future Essentials applier would write PBS text.
- **Resolution map**: a per-applier lookup from `chrooked_id` to that engine's symbol, for example `goodra -> SPECIES_GOODRA` for pokeemerald or `goodra -> GOODRA` for Essentials. Partly auto-derived from hints in the Ruleset, partly hand-confirmed for odd cases.
- **Apply Report**: the human-readable output of an apply run. Lists every entry as applied, blocked (whole entry could not land), or partial (entry landed but one referenced field could not). Apply never silently drops anything.
- **Harvest**: a separate, deliberate command that reads a fork, compares it against the Ruleset, and proposes edits *back into* the Ruleset for per-field confirmation. It is how good in-game tuning gets pulled into the canon. It is never part of a normal apply.

## Design decisions carried in from the grilling session

These were settled with Chris before this plan was written. They are not open questions.

The Ruleset stores **overrides only** at field granularity for scalar fields (a single changed type, ability, or stat), but stores the **whole list** for learnsets: if Chris touched a Pokémon's level-up moves at all, the Ruleset owns the entire list and the applier replaces it wholesale. This is the specific fix for v1's duplicate-move bug, which came from merging partial edits into an existing list.

Identity across engines uses a **`chrooked_id` slug** that Chris owns, with optional `aka:` hints (national dex number, known engine symbols) that help an applier's resolution map auto-resolve. New content he invents gets an id for free.

When a target game lacks something the Ruleset references, the applier **skips loudly**: a whole entry that cannot land is reported as `blocked`, a single missing referenced field inside a landed entry is reported as `partial`. Nothing is silent. The single exception that turns a skip into a create: if the missing thing is **owned by the Ruleset** (a custom move like Excalibur whose full definition lives in the Ruleset), the applier **creates it in the target** and then resolves the reference. This is decided by whether the data exists to create, not by a flag. Because created content must exist before the species that cite it, the applier resolves in tiers: types, then abilities, then moves, then species.

Reverse flow is a separate **harvest** command, with per-field confirmation, and the Ruleset always stays canonical: drift only enters the Ruleset through a gate Chris opens.

The Ruleset is **seeded from `dreamstone-mysteries`** as canon version zero, by diffing it once against unmodified pokeemerald-expansion. The other fork, `PKMN-Chrooked-HnS`, is not a co-seed; it can be brought in later through harvest.

## Critical baseline pin (read before seeding)

The seed diff must compare `dreamstone-mysteries` against unmodified pokeemerald-expansion **at the exact version Dreamstone forked from**, which is **1.11.2**. This was read from `dreamstone-mysteries/include/constants/expansion.h`:

    #define EXPANSION_VERSION_MAJOR 1
    #define EXPANSION_VERSION_MINOR 11
    #define EXPANSION_VERSION_PATCH 2

The sibling checkout at `/Users/cdbrooks/Development/Games/ROMs/pokeemerald-expansion` is currently at **1.15.3**. Diffing against that would invent hundreds of phantom overrides for everything upstream changed across four minor versions. Do not use the sibling checkout as-is. Obtain unmodified pokeemerald-expansion at tag `expansion/1.11.2` (the upstream project tags releases this way) into a scratch directory and point the seed at that. Verify before seeding by reading the candidate base's `include/constants/expansion.h` and confirming it reads 1.11.2.

## Repository layout to create

Everything lives under `/Users/cdbrooks/Development/Games/chrooked-pokedex`. This plan and its successors live in `plans/`. Create the rest as the milestones reach them. The intended shape:

    chrooked-pokedex/
      plans/                         this file and future plans
      CONTEXT.md                     project Lexicon (engine-neutral terms)
      README.md
      pyproject.toml                 Python package, mirrors v1's tooling
      ruleset/                       THE SOURCE OF TRUTH (YAML, hand-editable)
        species/                       one file per changed species, e.g. goodra.yaml
        moves/                         one file per Ruleset-owned (new/changed) move
        abilities/                     one file per Ruleset-owned ability
        type-chart/overrides.yaml      attacker/defender multiplier overrides
        meta.yaml                      base version pin, schema version
      src/chrooked_pokedex/
        readers/pokeemerald/           VENDORED from v1: the five parsers
        model/                         frozen dataclasses for the neutral schema
        seed/                          extract: fork + base -> ruleset
        appliers/pokeemerald/          ruleset -> C, plus resolution map
        report/                        Apply Report writer (md + json)
        harvest/                       reverse: fork -> proposed ruleset edits (later)
        cli.py
      tests/

## What to vendor from v1 (do not rewrite these)

v1's parsers already read pokeemerald C into clean Python dataclasses and are tested. Copy these files from `/Users/cdbrooks/Development/Games/ROMs/pokeemerald-chrooked-patcher/src/pokeemerald_chrooked_patcher/` into `src/chrooked_pokedex/readers/pokeemerald/`, adjusting imports:

- `species_parser.py` (425 lines) — stats, types, abilities, egg groups, held items per species.
- `learnset_parser.py` (148 lines) — level-up move lists, including the split-file layout and species-to-variable mapping.
- `evolution_parser.py` (116 lines) — evolution methods and conditions.
- `ability_parser.py` (247 lines) — ability names and descriptions.
- `move_parser.py` (81 lines) — move definitions.

Do **not** vendor v1's `patch_artifact.py`, `new_species_artifact.py`, or the `*_writer.py` files. The artifact files encode the diff-vs-base model this plan replaces. The writers encode the regex merge-in-place approach that caused the duplicate-move bug. New appliers render whole records instead.

There is no type-chart parser in v1; one must be written new. In pokeemerald-expansion the type effectiveness data lives in `src/data/types_info.h` (a table of type matchups). The seed reader and the pokeemerald applier both need to understand it.

## Milestones

### Milestone 0 — Scaffold and vendored readers compile

Stand up the repository, the Python package, and the vendored readers, with a smoke test proving the readers still parse a real fork. At the end of this milestone `chrooked-pokedex` is an installable Python package and `pytest` runs green.

Work: create the directory layout above; write `pyproject.toml` modeled on v1's (same dependencies — it is a small CLI with YAML and openpyxl); copy the five parser files into `readers/pokeemerald/` and fix their imports; write `CONTEXT.md` with the engine-neutral Lexicon (Ruleset, Override, chrooked_id, Applier, Resolution map, Apply Report, Harvest — the definitions above are the source text); port v1's parser tests for the five readers.

Acceptance: from `chrooked-pokedex/`, `pip install -e ".[dev]"` succeeds, and `pytest` passes. A one-off script `python -c "from chrooked_pokedex.readers.pokeemerald import species_parser"` imports without error. Pointing the species parser at `../ROMs/dreamstone-mysteries` returns a non-empty list of parsed species including Goodra.

### Milestone 1 — Neutral schema and the Ruleset model

Define the engine-neutral data shapes and prove a hand-written Ruleset file round-trips through the model. This milestone produces no game changes; it fails-before/passes-after via tests.

Work: in `src/chrooked_pokedex/model/`, define frozen dataclasses for `SpeciesOverride`, `MoveDef`, `AbilityDef`, `TypeChartOverride`, and a top-level `Ruleset` that loads a `ruleset/` folder of YAML into those dataclasses. Write the schema exactly as agreed: scalar species fields are optional (present only when overridden); `learnset` when present is the complete list. Hand-author two sample files to drive tests — `ruleset/species/goodra.yaml` (Water/Dragon, Poison Heal, a full learnset citing a normal move and the custom move Excalibur) and `ruleset/moves/excalibur.yaml` (Steel, physical, power 90). Add `ruleset/type-chart/overrides.yaml` with the Flying-resisted-by-Ice entry and `ruleset/meta.yaml` pinning base version 1.11.2.

The Goodra sample, as the canonical schema reference:

    name: Goodra
    chrooked_id: goodra
    aka: { dex: 706, pokeemerald: SPECIES_GOODRA }
    types: [Water, Dragon]
    abilities:
      primary: Poison Heal
      hidden: Sap Sipper
    stats: { spe: 80 }              # only overridden stats appear
    learnset:                        # whole list = owned; applier replaces
      - { level: 1,  move: Dragon Breath }
      - { level: 30, move: Liquidation }
      - { level: 45, move: Excalibur }
    evolution: { from: Sliggoo, method: { level: 50, condition: raining } }

Acceptance: `pytest` includes a test that loads the sample `ruleset/`, asserts Goodra has exactly the overridden fields present and no others, asserts the learnset has three entries in order, and asserts Excalibur resolves to a Ruleset-owned `MoveDef`. A test confirms an unknown field in YAML raises a clear validation error (fail fast at the boundary).

### Milestone 2 — Seed the Ruleset from Dreamstone (the extract step)

Generate the real version-zero Ruleset by diffing Dreamstone against unmodified pokeemerald-expansion 1.11.2. This is the one place diffing legitimately lives. At the end, `ruleset/` contains Chris's actual ~300 changes as hand-readable YAML.

Work: acquire unmodified pokeemerald-expansion at 1.11.2 into a scratch path (see the baseline pin section) and verify its version file reads 1.11.2. In `src/chrooked_pokedex/seed/`, write an extractor that runs each vendored reader over both the base and Dreamstone, computes per-field differences, and emits Ruleset YAML: a species file only when at least one field differs; for learnsets, emit the whole Dreamstone list whenever it differs at all; emit move and ability files for entries Dreamstone changed or added; emit type-chart overrides for matchups that differ. New moves/abilities Dreamstone invented become Ruleset-owned definitions. Mint `chrooked_id` slugs by lowercasing and de-spacing the canonical name, recording `aka.pokeemerald` with the original symbol so nothing is lost.

Acceptance: running `python -m chrooked_pokedex.cli seed --fork ../ROMs/dreamstone-mysteries --base /path/to/expansion-1.11.2` writes files under `ruleset/`. Spot-check by opening `ruleset/species/goodra.yaml` (or whichever species Chris actually changed) and confirming the values match Dreamstone, not base. A summary prints counts: species changed, learnsets replaced, moves owned, abilities owned, type-chart overrides. The run is idempotent — running it twice produces identical files (verify with `git status` showing no diff on the second run).

### Milestone 3 — pokeemerald applier: species, the smallest end-to-end loop

Prove the whole pipeline on the simplest data: push species scalar overrides (types, abilities, stats) from the Ruleset into a fork and have it compile. This is the first slice that visibly changes a game.

Work: in `src/chrooked_pokedex/appliers/pokeemerald/`, build the resolution map (`chrooked_id` to `SPECIES_*` / `TYPE_*` / `ABILITY_*`, seeded from `aka:` hints and the target's own symbol tables, with a printed list of any unmapped ids). Write a renderer that, for each species override, rewrites only the overridden fields in the target's `species_info` files — whole-field replacement, never a merge. Write the Apply Report writer in `src/chrooked_pokedex/report/` producing both a Markdown report and a JSON sidecar, classifying every entry as applied, blocked, or partial. Require a clean git working tree on the target before writing (port this guard from v1's `_require_clean_git_status`), bypassable with `--force`.

Acceptance: against a fresh clone/copy of a pokeemerald fork, `python -m chrooked_pokedex.cli apply --target /path/to/fork --category species` rewrites species files, prints an Apply Report, and the fork compiles with `make -j$(nproc)`. Concretely: after applying, the fork's Goodra entry shows `TYPE_WATER, TYPE_DRAGON` and `ABILITY_POISON_HEAL`. Re-running apply on the now-modified fork reports every species as already-applied with no further file changes (idempotent).

### Milestone 4 — pokeemerald applier: learnsets with whole-list replace

Apply learnsets the new way — replace the entire level-up list per species — and prove the duplicate-move bug cannot recur. This milestone directly retires v1's worst symptom.

Work: extend the applier to render a species' whole learnset from the Ruleset, replacing the target's existing list for that species outright. Resolve each move name through the resolution map; if a move is unresolved and Ruleset-owned, defer it to Milestone 5's create step and mark the entry partial for now; if unresolved and not Ruleset-owned, report partial.

Acceptance: `apply --category learnset` against the fork replaces learnsets and compiles. A test seeds a target whose existing Goodra learnset already contains Dragon Breath, applies a Ruleset Goodra learnset that also contains Dragon Breath, and asserts the result contains Dragon Breath exactly once — the old merge would have produced two. The Apply Report lists Excalibur on Goodra as partial (not yet created) until Milestone 5.

### Milestone 5 — Ruleset-owned creation: moves, abilities, type chart, in dependency tiers

Make the applier author content the target lacks but the Ruleset owns, in the correct order, so that Excalibur ends up real and Aegislash actually knows it. Also apply evolutions and type-chart overrides.

Work: implement tiered apply — first create any Ruleset-owned types/abilities/moves missing from the target (append new `MOVE_*`/`ABILITY_*` constants and their data-table entries), then apply species scalars, then learnsets, then evolutions. Add the type-chart applier that edits `src/data/types_info.h` for each override. After creation, previously-partial references must resolve to applied.

Acceptance: against a fork that has no Excalibur, `apply` (all categories) creates the move, and the fork compiles with Aegislash's and Goodra's learnsets citing it. The Apply Report shows Excalibur as created and the citing entries as applied, not partial. The Flying-vs-Ice override is present in `types_info.h` (Ice takes half damage from Flying). A full apply onto a clean fork yields zero blocked entries for anything the Ruleset owns; the only blocked/partial items are references to real content the target genuinely lacks and the Ruleset does not define.

### Milestone 6 — Harvest (reverse sync), gated and confirming

Allow good in-game tuning to flow back into the Ruleset without ever letting it drift silently. This milestone is additive and does not change apply.

Work: in `src/chrooked_pokedex/harvest/`, read a fork, diff it against the current Ruleset (reusing readers and the resolution map in reverse), and present each differing field as a proposed Ruleset edit. Write nothing without per-field confirmation. A `--dry-run` prints the proposed diffs only.

Acceptance: editing a single stat in a fork, then running `harvest --fork /path/to/fork`, lists exactly that one field as a proposed change; declining leaves `ruleset/` untouched (`git status` clean); accepting updates only that field in the right species file.

### Milestone 7 — Essentials design note (no code)

Close the loop on the deferred engine by writing, in `plans/`, a short successor design note confirming the neutral schema maps cleanly onto Essentials PBS files (name to PBS identifier, types to PBS type names, learnsets to PBS move lists) and flagging the only hard part — custom abilities/moves whose behavior needs Ruby. No applier is built here. This exists so the next session can start the Essentials applier from the Ruleset as-is.

Acceptance: a file `plans/essentials-applier-plan.md` exists describing the PBS mapping per category and explicitly listing what cannot be expressed as flat PBS data.

## Progress

- [x] (2026-06-11) Milestone 0 — Scaffold and vendored readers compile. Package installs (`.venv`), `pytest` green at 27 passed, vendored 5 parsers into `readers/pokeemerald/`, ported 4 parser tests + wrote a new move-parser test, real-fork smoke test confirms Dreamstone Goodra parses.
- [x] (2026-06-11) Milestone 1 — Neutral schema and Ruleset model. Frozen dataclasses in `model/schema.py`; YAML loader with fail-fast unknown-field validation in `model/loader.py`; `Ruleset.load()` + `owned_move`/`owned_ability` in `model/ruleset.py`. Sample `ruleset/` (goodra, excalibur, type-chart, meta) round-trips; 6 model tests green, full suite 33 passed.
- [x] (2026-06-11) Milestone 2 — Seed the Ruleset from Dreamstone against base 1.11.2. New `type_chart_parser.py` reader; `seed/neutralize.py` + `seed/extractor.py` + `seed/writer.py`; `cli.py seed` with a base-version guard. Real seed wrote 758 species, 216 learnsets, 45 owned moves, 57 owned abilities, 7 type-chart overrides. Flying→Ice 0.5 and the Ruleset-owned Excalibur both present. Idempotent (identical file hashes on re-run). Base acquired via `git worktree` at tag `expansion/1.11.2` in `../ROMs/_scratch-expansion-1.11.2`.
- [x] (2026-06-11) Milestone 3 — pokeemerald applier: species end-to-end. `appliers/pokeemerald/`: `c_edit.py` (surgical whole-field entry edits), `resolution.py` (Resolution map), `species_apply.py` (types/abilities/stats), `git_guard.py` (clean-tree guard, `--force` bypass); `report/` Apply Report (md + json, applied/partial/blocked); `cli.py apply`. Real apply onto a clean base-1.11.2 copy turned Goodra into Dragon/Water with Poison Heal (413 applied, 345 partial, 0 blocked); re-run changed 0 files (idempotent). The 345 partials are species citing Dreamstone-custom abilities absent from base — correctly deferred to M5's creation step, with types/stats still landing. `make` compile is a documented manual step (devkitARM not on PATH here); structural validity is proven by the readers round-tripping the rewritten C. Full suite 50 passed.
- [x] (2026-06-11) Milestone 4 — pokeemerald applier: learnsets, whole-list replace. `learnset_apply.py` discards each species' target array body and re-renders it from the Ruleset. Regression test proves a move present in both target and Ruleset appears exactly once (the v1 merge bug retired). Discovery: the same learnset array is defined once per generation behind `#if P_GEN_X`; every definition is replaced so the Ruleset wins regardless of build config. Unresolved moves are omitted and reported partial (owned ones deferred to M5). Real apply onto a clean base copy: 9 files changed, Goodra 17 entries with zero duplicates, 53 applied / 163 partial / 0 blocked; idempotent. 53 passed.
- [x] (2026-06-11) Milestone 5 — Ruleset-owned creation in dependency tiers; evolutions; type chart. `creation.py` appends owned move/ability constants (bumping the `*_COUNT_GEN9` sentinel) and data entries; `type_chart_apply.py` rewrites matrix cells; `evolution_apply.py` rewrites the pre-evolution's `.evolutions` (minimal EVO_LEVEL/EVO_ITEM; real seed has none). CLI now applies in tiers create→species→learnset→evolution→type-chart, with the Resolution map updated in place so prior partials resolve. Full real apply onto a clean base-1.11.2 copy: 1055 applied, 0 partial, 0 blocked; Excalibur created (MOVE_EXCALIBUR, Steel/120) and cited by a real species; Flying→Ice 0.5 in types_info.h; fully idempotent on re-run. (Type tier is empty by design — the schema models no new type definitions, only chart overrides.) 60 passed.
- [x] (2026-06-11) Milestone 6 — Harvest, gated reverse sync. `harvest/harvester.py` compares a fork against the Ruleset's recorded overrides (stats, types, abilities) and proposes per-field edits; `cli.py harvest` lists them, gates each behind y/N confirmation, and `--dry-run` writes nothing. Acceptance: editing one fork stat yields exactly one proposal (`goodra: stat.hp 95 -> 99`); declining leaves `ruleset/` untouched; accepting updates only that field. Building harvest surfaced and fixed a latent apply bug (see Surprises): species fields are preprocessor-gated duplicates, and apply was editing only the first branch. After the fix an apply→harvest round-trip reports zero drift. 65 passed.
- [x] (2026-06-11) Milestone 7 — Essentials design note. `plans/essentials-applier-plan.md` documents the per-category PBS mapping (pokemon.txt species/types/abilities/BaseStats/Moves, moves.txt, abilities.txt, defender-side types.txt) and the one true boundary: custom move/ability *behavior* is Ruby (FunctionCode), which flat PBS cannot express — to be reported `partial`, never faked. No code, by design.

## Surprises & Discoveries

- Observation: Dreamstone is on pokeemerald-expansion 1.11.2 while the sibling `pokeemerald-expansion` checkout is 1.15.3.
  Evidence: `include/constants/expansion.h` reads 1.11.2 in Dreamstone and 1.15.3 in the sibling. Seeding against the sibling would fabricate phantom overrides; the plan pins the base to 1.11.2.

- Observation: the real seed produces 758 changed species, not the ~300 the purpose section estimated.
  Evidence: category breakdown showed 509 species with ability changes, 368 with stat changes, 216 learnsets, 109 type changes. Spot-checking confirmed these are real Dreamstone edits — e.g. base Bulbasaur abilities `{OVERGROW, NONE, CHLOROPHYLL}` vs fork `{OVERGROW, CHLOROPLAST, CHLOROPHYLL}`; base Charizard `Fire/Flying` vs fork `Fire/Dragon`. Dreamstone gave hundreds of species a second ability where base had `ABILITY_NONE`. The "~300" was Chris's headline-change recollection; the mechanical fork diff is legitimately larger. No false positives found.

- Observation: the compile proof (the last open acceptance) caught a real bug — created descriptions emitted a literal backslash the GBA charmap cannot map.
  Evidence: building an applied base-1.11.2 copy failed with `src/pokemon.c: error: no mapping exists for backslash`. The cause: Dreamstone ability descriptions use the `\n` textbox control code; the reader captured the raw backslash, the seed stored it, and `creation._escape` doubled it to `\\n`, leaving a literal backslash in the C string. The GBA charmap has no glyph for backslash, so its preprocessor rejected it. Fix: `neutralize.normalize_description` flattens `\n`/`\l`/`\p` to spaces and drops stray backslashes, applied both at seed time (canonical Ruleset is clean) and at creation time (the emitter can never break the charmap). After the fix the applied fork builds a 33 MB `pokeemerald.gba` with `make`, exit 0.

- Observation: the working toolchain is the devkitPro Docker image, not the system devkitARM.
  Evidence: the system devkitARM (release 66, gcc 15.1) and even `devkitpro/devkitarm:latest` (gcc 16.1) are too new for 1.11.2 — both fail in gcc's own `stddef.h` on the C23 `nullptr` keyword under `-std=c11`, on core engine files the Ruleset never touches. Dreamstone's CI builds in `container: devkitpro/devkitarm`; pinning the dated tag `devkitpro/devkitarm:20240202` (devkitARM r63, gcc 13.2) — the 1.11.2 era — builds cleanly. The compile proof therefore runs inside that pinned image.

- Observation: species_info entries carry the same scalar field more than once, gated by `#if P_UPDATED_ABILITIES/STATS/TYPES >= GEN_x / #else / #endif`; the species applier was editing only the first branch.
  Evidence: post-apply Absol read `{ABILITY_SHARPNESS, ABILITY_SUPER_LUCK, ABILITY_JUSTIFIED}` via the entry editor but `{ABILITY_PRESSURE, ABILITY_NONE, ABILITY_JUSTIFIED}` via the species parser — because the parser keeps the last (`#else`) branch and apply had only rewritten the first. This produced 153 false "drift" proposals when harvesting a freshly-applied fork. Fix: `c_edit` gained `set_field_all` (same value to every branch, for stats/types) and `set_field_per_occurrence` (overlay changed ability slots onto each branch, preserving its other slots). After the fix, apply→harvest round-trip reports zero drift, and a regression test covers a gated entry. This was a real M3 correctness bug that only surfaced because harvest exercised the reverse direction.

- Observation: an owned ability whose description held a real newline produced invalid C and broke creation idempotence.
  Evidence: `ruleset/abilities/blitz.yaml` has `description: "Turn 1: Speed +50%,\nAttack +30%."`. Emitting the newline literally split the C string across two lines (a bare newline inside `"..."` is invalid C), and the single-line description reader then failed to capture the ability, so it was re-created on every run (`create: 2 file(s) changed` on the second pass). Fix: `creation._escape` now escapes newlines/tabs/quotes/backslashes. After the fix a full re-apply changes zero files in every tier.

- Observation: pokeemerald-expansion defines the same learnset array once per generation, each behind a `#if P_GEN_X` block.
  Evidence: `sGoodraLevelUpLearnset[]` appears in gen_1.h through gen_9.h of `src/data/pokemon/level_up_learnsets/`. The learnset applier replaces every definition so the Ruleset's list wins whichever generation the target's build config activates.

- Observation: the seed had to live in a test fixture separate from the canonical `ruleset/`, or M1's hand-authored sample and M2's real seed would collide on `goodra.yaml`.
  Evidence: M2 overwrites `ruleset/species/goodra.yaml` with real Dreamstone data (full learnset, no Excalibur in the level-up list). The M1 sample (3-move learnset citing Excalibur) was moved to `tests/fixtures/sample_ruleset/` so its assertions stay stable.

## Decision Log

- Decision: Ruleset stores overrides-only for scalars but whole-list for learnsets.
  Rationale: portability across games with different rosters, while eliminating the merge step that caused v1's duplicate-move bug.
  Date/Author: 2026-06-11, Chris + Claude (grilling session).

- Decision: identity via Chris-owned `chrooked_id` slug plus `aka:` hints, resolved per applier.
  Rationale: names break on forms/renames and have no value for invented content; dex numbers break on renumbered/fakemon rosters; an owned slug is stable and free for new content.
  Date/Author: 2026-06-11, Chris + Claude.

- Decision: missing references skip loudly (blocked/partial), except Ruleset-owned content which is auto-created; apply resolves in tiers types→abilities→moves→species.
  Rationale: silent drops were v1's trust problem; creation is gated on whether the data exists to create, so it needs no flag.
  Date/Author: 2026-06-11, Chris + Claude.

- Decision: reverse sync is a separate, per-field-confirmed `harvest` command; Ruleset stays canonical.
  Rationale: drift may only enter canon through a deliberate gate.
  Date/Author: 2026-06-11, Chris + Claude.

- Decision: seed from Dreamstone against unmodified pokeemerald-expansion 1.11.2; HnS deferred to harvest.
  Rationale: Dreamstone is the newest, most curated fork; one spine avoids birth-time conflicts.
  Date/Author: 2026-06-11, Chris + Claude.

- Decision: new repo, vendoring v1's five parsers; dropping v1's artifact and writer layers.
  Rationale: the parsers are reusable and tested; the diff-artifact and regex-merge-writer layers encode the model being replaced.
  Date/Author: 2026-06-11, Chris + Claude.

## Outcomes & Retrospective

All seven milestones are complete. Chris now has `chrooked-pokedex`: an
engine-neutral Ruleset he owns (`ruleset/`, ~877 hand-readable YAML files seeded
from Dreamstone), a working pokeemerald applier, a gated harvest path, and a
design note that unblocks the future Essentials applier.

What was achieved against the original purpose:

- The Ruleset is the single source of truth, in plain names, seeded once from
  Dreamstone against unmodified pokeemerald-expansion 1.11.2 (758 species, 216
  learnsets, 45 owned moves, 57 owned abilities, 7 type-chart overrides).
- One command applies the whole Ruleset onto a fresh pokeemerald fork. A full
  apply onto a clean base-1.11.2 copy lands 1055 entries with zero blocked and
  zero partial: Goodra becomes Water/Dragon with Poison Heal, the custom move
  Excalibur is created and cited by a real species, and Ice resists Flying. Every
  run is idempotent, and the Apply Report classifies every entry — nothing
  silently dropped.
- v1's duplicate-move bug is structurally retired: learnsets are owned whole and
  replaced outright, proven by a regression test.
- Harvest pulls in-game tuning back into the Ruleset one confirmed field at a
  time, keeping the Ruleset canonical.

What remains / was deliberately deferred:

- The pokeemerald `make` compile is now verified: an applied clean base-1.11.2 copy
  builds a 33 MB `pokeemerald.gba` (`make` exit 0) inside the pinned devkitPro image
  `devkitpro/devkitarm:20240202` (gcc 13.2). The proof caught and fixed a real
  charmap/backslash bug in created descriptions. The system devkitARM (gcc 15/16) is
  too new for this base and cannot build it, applied or pristine.
- Evolutions are modeled and have a working applier, but the real seed carries no
  evolution data (M2 deferred seeding them); harvest can pull them in later.
- Other species fields beyond types/abilities/stats/learnset (catch rate, EV
  yields, …) are outside the neutral schema and not captured — a future schema
  extension if Chris wants them.
- The Essentials applier is designed (M7) but not built.

Lessons learned, in short: the two bugs both came from C being less regular than
it looks — fields and learnset arrays are duplicated across `#if P_GEN/P_UPDATED_*`
branches, and emitted strings must escape newlines. Both were caught because the
plan insisted on idempotence and on a reverse (harvest) path that exercised apply
from the other side. Test count grew from 0 to 65, all green.

## Code Review Findings

A two-agent review fan-out ran against the full change set after Milestone 7. The
established contracts were confirmed intentional and left as-is: an applier reports
`applied` when the Override is in effect (not only when a byte changed — the CLI
reports file-change counts separately), and `--category species`/`learnset` are raw
single-tier runs that deliberately skip the create tier. The actionable findings
below were fixed via TDD (8 new regression tests; 73 passing total).

### High Risk

- Fixed: the loader silently dropped typo'd Overrides. A misspelled stat key
  (`spee`) or move category (`phyiscal`) passed validation and then never landed,
  violating the project's fail-fast / nothing-silently-dropped invariant. The
  loader now validates stat keys against `STAT_KEYS` and move category against
  `MOVE_CATEGORIES`, raising a clear error naming the bad value and file.
- Fixed: the seed YAML writer left descriptions containing ` #...` unquoted, so
  YAML parsed the `#` as a comment and silently truncated the value (real example:
  `ruleset/moves/icefang.yaml`). The writer now quotes any scalar with a YAML
  indicator lead character, an inline ` #`, or embedded quotes/backslashes, and the
  re-seeded Ruleset preserves these descriptions in full.

### Medium Risk

- Fixed: the C entry editor's brace/expression scanners counted `{`/`}`/`,` inside
  C string literals, which could mis-slice an entry whose name or description holds
  those characters (e.g. `_("Nidoran{F}")`). `c_edit` is now string-literal aware.
- Fixed: the seed could silently overwrite one entity when two distinct sources
  slug to the same `chrooked_id`; the seed now fails fast on a collision. (No
  collision occurs in the real Dreamstone seed.)
- Fixed: `creation._escape` now also escapes `\r`; `harvest` now imports a public
  `species_yaml` instead of a private helper; added git-guard tests (dirty tree
  blocks, `--force` bypasses, non-git target allowed by design).

### Low Risk

- Noted, not changed: `_diff_abilities` does not record a fork that zeroes an
  ability slot back to `ABILITY_NONE` (treated as "no override"); acceptable for
  v0. The `test_smoke_real_fork` path is hardcoded and skips when absent.
