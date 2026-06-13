# PRODUCT.md

Design context for the chrooked-pokedex web app. Loaded by `/impeccable` before any UI work.

## Register

`product` — the design serves the task. This is a local single-user tool for browsing and authoring data, not a marketing surface. Earned familiarity over novelty; the tool should disappear into the task.

## Product purpose

A local web app to manage a **Ruleset**: an engine-neutral set of Pokémon changes (types, stats, abilities, moves, learnsets, evolutions, type-chart, custom behaviors). Three jobs, built in slices:

1. **Browse** the Canon dex — the full national Pokédex with the Ruleset merged on top — and see at a glance what the Ruleset has changed vs base. *(Milestone 1)*
2. **CRUD** every Ruleset kind through typed, validated forms that write YAML. *(Milestone 2)*
3. **Apply** the Ruleset to a chosen game (a Fork or a Pokémon Essentials fangame), with a no-write preview first. *(Milestone 3)*

The deeper shape of the domain (Ruleset, Override, Canon dex, Target, Applier, Apply Report) lives in [CONTEXT.md](./CONTEXT.md) — that file is the source of truth for terms; this file is the source of truth for *who it's for and how it should feel*.

## Users

One user: Chris. A solo developer and Pokémon ROM-hack author, technically fluent, building this tool for himself. Sits at a desk, uses it in focused sessions while authoring his hack. Knows the domain cold — wants signal and density, not hand-holding or onboarding fluff. Power-user defaults: keyboard navigation, fast scanning, the diff one keystroke away.

## Tone & voice

- Terse, precise, device-flavored. `EDITED`, `№ 706`, `NO EDITS` — not "This Pokémon has been edited by your ruleset."
- Honest. Errors say what broke and how to fix it (surface the loader's real message; surface the 503 "run `snapshot`" instruction verbatim).
- No marketing voice, no celebratory copy, no emoji in the UI.

## Anti-references (what this must NOT become)

- **Red-plastic-toy Pokédex kitsch.** The device flavor is a restrained nod (chrome, a status LED, a segmented readout), not a cartoon prop.
- **Gradient type-cards / the PokéAPI-clone card grid.** Type color is semantic, not a decorative gradient skin.
- **Identical-card-grid SaaS dashboard.** Cells are sprite-led and differentiated by state.
- **Dark-by-reflex tool chrome.** Dark is chosen here because the handheld-screen metaphor earns it (see DESIGN.md scene sentence), not because tools "look cool dark."
- **Onboarding / empty-state hand-holding.** The single user is an expert; empty states teach the interface in one line, then get out of the way.

## Strategic principles

- **The edit is the hero.** The whole point is seeing what the Ruleset changed. The "edited" state and the base→now diff are first-class, but revealed on demand ([Progressive Disclosure](~/.claude/CONTEXT.md)) so the dex still reads calm by default.
- **Density with rhythm.** A power tool over ~1451 species: pack information, but vary spacing so it scans instead of blurring.
- **One color, one job.** Type color means type. Amber means edited. Brick-red means device chrome. No collisions.
- **Keyboard-first.** Every primary action has a key. Mouse is allowed, never required.
