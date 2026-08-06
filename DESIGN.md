# DESIGN.md

The visual system for chrooked-pokedex. Concrete tokens and component rules; pairs with [PRODUCT.md](./PRODUCT.md). All color in OKLCH, never `#000`/`#fff`, every neutral tinted toward the warm device hue.

## Direction

Terminal / data-dense **spine** (monospace data, dense grid, keyboard nav) carrying restrained **Pokédex-device** character (a thin device frame, a status LED for edited, a segmented readout for the dex number). A power tool that happens to feel like a handheld.

**Scene sentence (forces the theme):** *Chris scanning a dense species ledger on a handheld-style screen, focused, the readout the bright object in the room.* → **dark** is the default identity, warm-tinted screen surface. A **light theme exists as an explicit opt-in** (header toggle → `data-theme="light"` on the root, persisted in `localStorage`, never inferred from the OS) — dark stays what the tool *is*.

## Color

Restrained surface + tinted neutrals, with three **semantic** color jobs that never overlap. Values below are the **dark (default) theme**, red-shifted to the brand palette (hue ~19–28); the light theme re-solves every token in `tokens.css` under `:root[data-theme="light"]`:

| Job | Token | Meaning | OKLCH (dark) |
|---|---|---|---|
| Surface inset | `--surface-0` | wells, fields, sprite bg | `oklch(12.4% 0.011 19)` |
| Surface | `--surface-1` | the screen | `oklch(16.4% 0.011 19)` |
| Surface raised | `--surface-2` | cells, panels | `oklch(20.4% 0.011 19)` |
| Hairline | `--line` | borders, dividers | `oklch(30.4% 0.011 19)` |
| Ink | `--text` | primary text | `oklch(98.3% 0.001 17)` |
| Ink dim | `--text-dim` | labels, secondary | `oklch(77.3% 0.001 17)` |
| Chrome | `--chrome` | device structure (frame, active rail) | `oklch(57.9% 0.203 26)` red, sparing, ≤10% area |
| Edited | `--edited` | the **only** thing that means "Ruleset touched this" | `oklch(80% 0.15 80)` amber LED |

`--chrome` is structure, not emphasis; `--edited` is the single attention signal. Don't reach for either decoratively. The source palette's fifth swatch (`#bc0101`) is **deliberately unassigned** — every color job above is taken, and giving it one would break the one-color-one-job rule.

**Light theme rules:** each light value is **re-solved, not inverted** — checked against the real formulas that consume it (type-chip `color-mix`, `--chrome`/`--edited` as text) so everything still clears AA. The **brand lamp and favicon** (a tilted Premier Ball) keep their own fixed shell/seam colors; they never borrow `--text`/`--surface-0`, which swap meaning between themes.

### Type colors — semantic token set

All 18, used **wherever a type renders** (grid codes, detail chips, type-chart tab). Sourced from the franchise hues, **dark-tuned**: lightness lifted to ~58–85% and chroma held so each stays legible and passes AA on `--surface`. Lock exact values in `tokens.css` with a contrast check; these are the targets. The light theme carries its own **light-tuned** set (lightness pulled to ~53–57%, same hues) solved against the light chip formulas the same way.

| Type | `--type-*` (OKLCH) | Type | `--type-*` (OKLCH) |
|---|---|---|---|
| normal | `72% 0.03 95` | ground | `70% 0.13 60` |
| fire | `72% 0.17 50` | flying | `76% 0.09 270` |
| water | `68% 0.13 250` | psychic | `70% 0.16 10` |
| electric | `85% 0.16 95` | bug | `78% 0.16 130` |
| grass | `75% 0.16 145` | rock | `74% 0.06 90` |
| ice | `83% 0.09 195` | ghost | `60% 0.13 290` |
| fighting | `62% 0.18 18` | dragon | `60% 0.18 265` |
| poison | `64% 0.17 320` | dark | `52% 0.04 300` |
| steel | `70% 0.05 220` | fairy | `80% 0.11 350` |

A type chip is the type color as text/keyline on a low-chroma tint of itself (`color-mix` toward `--surface-2`), not a saturated fill. Two-type species show both, ordered as the data gives them.

### Damage category — one shape, one hue, everywhere

A move's physical / special / status split is **one glyph set plus one hue per category**, and every surface that shows a category renders that same pair: the moves table, the move detail, the move editor's picker, the distributor's split buttons, and a filter token. A category rendered as bare lowercase text in one place and a colored badge in another is the same data wearing two faces — the reader has to re-learn it per screen.

| Category | `--cat-*` (OKLCH, dark) | Shape |
|---|---|---|
| physical | `64% 0.19 35` — impact orange | impact burst |
| special | `62% 0.17 265` — energy blue | radiating starburst |
| status | `60% 0.03 250` — neutral slate | quiet ring |

The **shape carries identity**, so a category still reads in grayscale and never depends on the hue alone; the hue is the accent. `CategoryChip` owns the shapes and exports `CategoryGlyph` for hosts that carry their own shell. The light theme re-solves all three (see the type-color rules above).

## Typography

- **Mono** (data): dex №, stats, levels, type codes, the diff figures. A real monospace — `"JetBrains Mono", "SF Mono", ui-monospace, monospace`.
- **Sans** (prose/labels): species names, headings, button text. `ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif`.
- **Fixed rem scale** (not fluid — product UI, consistent DPI). Steps at ratio ~1.2: `0.75 / 0.8125 / 0.875 / 1 / 1.25 / 1.5 / 2 rem`.
- Mono dex № rendered with `font-variant-numeric: tabular-nums`; segmented-readout flavor via letter-spacing, not a pixel font.

## Spacing & density

- Base unit `4px`. Grid cells are tight (`8–12px` padding); panels breathe more (`16–24px`).
- Vary rhythm: the device frame and detail ledger get air; the grid is packed. Same padding everywhere is the failure mode.
- Body/prose measure capped 65–75ch; data tables may run dense and wide.

## Elevation

Flat, screen-like. Separation by hairline (`--line`) and surface-step (`--surface-0/1/2`), not drop shadows. The one allowed glow: a soft amber bloom on the edited LED, small and purposeful. No glassmorphism.

## Components

- **Grid cell** — small pixel sprite + mono dex № + mono type code(s) + amber edited-LED (top-right, only when `overridden_fields` non-empty). Sprite-missing → mono № placeholder in an inset well. Hover/focus: chrome keyline + lift via surface-step (not transform-shadow). Virtualized; stable keys by `chrooked_id`, never index.
- **Detail ledger** — opens as a side panel. Mono stat table, abilities, learnset, evolution. The **diff toggle** lives here: off = clean merged values; on = base→now on each overridden field (`SPE 90 → 80`), the changed row keyed amber. Only `overridden_fields` are annotated.
- **Type chip** — see type-color rule above.
- **Tabs** — the five kinds (Dex · Moves · Abilities · Type-chart · Behaviors) as a readout menu in the device frame. Read-only lists for the four non-dex kinds in M1.
- **Filter** — "edited only" toggle (`e`), search (`/`). URL-persisted so a view is shareable/reloadable.

Every interactive component ships all states: default, hover, focus-visible, active, disabled, loading (skeleton, no spinners), empty, error.

## Motion

- 150–250 ms, ease-out (quart/quint/expo). No bounce.
- Motion conveys state only: detail panel slide-in, diff reveal, LED bloom. No page-load choreography.
- Animate transform/opacity/filter only. Respect `prefers-reduced-motion`.

## A11y floor

WCAG AA: type chips and all text pass contrast on `--surface` (the dark-tuning targets above exist for this). Full keyboard path. Focus-visible always rendered. The edited state is never color-alone — the LED pairs with a text/`aria` signal so it survives color-blindness and grayscale.
