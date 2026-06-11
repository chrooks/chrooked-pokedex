# Behavior Layer — design record

## Problem

The Ruleset is a clean **data layer**. It carries *what* (a species is Water/Dragon,
has ability Blitz, learns these moves, evolves like this) but not *how* (what Blitz
does when it triggers). Custom ability/move **mechanics** live in engine C
(`battle_util.c`, battle scripts) and cannot travel as portable data — they differ per
engine (pokeemerald-expansion vs Pokémon Essentials) and per version.

Today, applying the Ruleset to an engine that lacks a custom mechanic silently creates
an inert ability: right name, right description, does nothing in battle. That is a
silent trap — it violates the project's Honest Signifier / Transparent Friction stance.

## Decision

Keep the data layer deterministic and pure. **Bridge** the data/behavior Boundary with a
new **behavior spec layer**, not by erasing it.

- Behavior cannot travel as data, but it can travel as a **verifiable specification**
  that a context-aware implementer (Claude) compiles to whatever target it is pointed at.
- Intent is the source of truth; implementation is delegated.

### Why a spec, not a DSL/compiler

A portable battle-script IR that compiles to each engine without an LLM is the rigorous
option, but it is a cross-engine battle-effect compiler that never covers the
weird-interaction long tail — over-engineering for ~58 mechanics. The LLM-as-compiler is
the right tool precisely because the implementer is intelligent and context-aware: this
is low-volume, high-variety, context-heavy work.

### What makes the spec reliable (not just prose)

1. **Neutral trigger vocabulary** — every effect attaches to one of ~10 engine-neutral
   battle hooks (`switch-in`, `accuracy-check`, `damage-calc`, ...). These exist in any
   turn-based Pokémon engine; they are the Seams behavior attaches to. Structured triggers
   make the spec unambiguous without making it engine-specific.
2. **Test cases are the Contract.** Each behavior carries concrete given/expect scenarios.
   This is the one place a *subtly wrong* mechanic is worse than a *missing* one — the
   tests convert "trust the LLM" into "verify against the spec".
3. **Engine hints** — optional per-engine pointers (`pokeemerald:`, `essentials:`), same
   pattern as the existing `aka` hints. Neutral by default; hints when a behavior is
   genuinely engine-touchy.

## Architecture: two appliers, one Ruleset

```
Ruleset (YAML)
 |- data fields ------> data applier (deterministic, exists today) -> stats/types/learnsets/...
 \- behavior: block --> behavior-port agent (Claude, new) ---------> implements mechanic on target
                            reads: spec + engine hints + reference-impl library
                            writes: tagged code (// chrooked:innerfocus ...)
                            checks: against test_cases
```

Discipline: keep the agent **out** of the deterministic data path. The data applier stays
pure and reproducible; the behavior path is agent-driven and test-gated.

## Slices

- **Slice 1 (this change)** — the spec layer + honest boundary, fully unit-tested:
  - neutral trigger vocabulary + behavior dataclasses
  - loader parses + fail-fast validates the `behavior:` block
  - Inner Focus behavior spec authored (the real mechanic: vanilla no-flinch + Focus
    Blast always hits)
  - manifest + portable implementation-packet renderer (the self-contained brief an agent
    uses cold)
  - loud DATA-ONLY apply warning when an ability with a behavior spec is created on a
    target that lacks its mechanic
  - `behaviors` CLI subcommand
- **Slice 2 (next)** — drive the loop live: behavior-port agent implements Inner Focus
  into a clean `pokeemerald-expansion@1.15.3`, compile, verify the three test cases;
  capture the result as a reference implementation.
- **Slice 3 (later)** — reference-implementation library that grows per engine; author the
  remaining ~57 ability specs.

## Schema (Slice 1)

```yaml
# ruleset/abilities/innerfocus.yaml
name: Inner Focus
chrooked_id: innerfocus
aka: { pokeemerald: ABILITY_INNER_FOCUS }
description: "No flinching. Focus Blast always hits."
behavior:
  effects:
    - summary: "Prevents flinching."
      trigger: status-apply
      effect: "this Pokemon cannot be made to flinch"
    - summary: "The user's Focus Blast never misses."
      trigger: accuracy-check
      when: "the move being used is Focus Blast"
      effect: "skip the accuracy roll; the move always hits"
  test_cases:
    - given: "Inner Focus user uses Focus Blast vs a +6 evasion foe"
      expect: "hits"
    - given: "Inner Focus user uses Hydro Pump"
      expect: "normal accuracy applies"
    - given: "a non-Inner-Focus user uses Focus Blast"
      expect: "normal 70% accuracy"
  notes:
    - "Mold Breaker does not bypass this (it is the user's own ability)."
  engine_hints:
    pokeemerald: "accuracy calc in battle_util.c (ref chrooked-patch-source:10807)"
    essentials: "Battle::Move#pbAccuracyCheck"
```
