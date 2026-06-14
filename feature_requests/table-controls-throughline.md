---
devos_version: 1
project: chrooked-pokedex
issue: 2
slug: table-controls
stage: implement
grillable: true
tier: heavy
effort: high
next_action: /implement 2
acceptance_criteria:
  - id: ac1
    statement: Boolean evaluator honors AND/OR precedence (OR looser), parens, per-leaf NOT
    proof_method: "vitest dexFilters.test.ts — evalEntries over A OR B AND C, (A OR B) AND C, NOT A"
    status: pending
  - id: ac2
    statement: Numeric operators (>= <= = > <) select correct rows on stats/BST/dex
    proof_method: "vitest dexFilters.test.ts — applyFilter numeric def per operator"
    status: pending
  - id: ac3
    statement: Type filter is array-contains (Fire matches a Fire/Water species)
    proof_method: "vitest dexFilters.test.ts — type-select on a dual-type fixture"
    status: pending
  - id: ac4
    statement: Class filter selects Legendary/Mythical/Starter by national dex number
    proof_method: "vitest dexTags.test.ts + dexFilters.test.ts — classOf(144/151/1/16) and class-select"
    status: pending
  - id: ac5
    statement: Multi-key sort is stable, numeric-aware (missing to end), direction-aware
    proof_method: "vitest dexSort.test.ts — stableMultiSort by type asc then bst desc, missing-BST last"
    status: pending
  - id: ac6
    statement: URL codec round-trips filter+sort+hidden; malformed payload decodes safe
    proof_method: "vitest dexViewCodec.test.ts — decode(encode(x))==x; corrupt/unknown/locked dropped"
    status: pending
  - id: ac7
    statement: Header click sorts + shows arrow; shift-click appends; sort row shows priority
    proof_method: "manual runtime step 1; DOM aria-sort + ordinal labels"
    status: pending
  - id: ac8
    statement: Adding a filter pill narrows rows in both grid and table; readout updates
    proof_method: "manual runtime step 2"
    status: pending
  - id: ac9
    statement: Per-pill AND/OR, NOT, and parenthesis grouping change the result set
    proof_method: "manual runtime steps 3-4"
    status: pending
  - id: ac10
    statement: Column toggles hide/show data columns and drop hidden from sort; LED/№/Name locked
    proof_method: "manual runtime step 5; no checkbox for locked columns"
    status: pending
  - id: ac11
    statement: Filters+sort+hidden+search persist in URL and restore exactly on reload
    proof_method: "manual runtime step 7"
    status: pending
  - id: ac12
    statement: Full dex stays responsive and virtualized while filtering/sorting
    proof_method: "manual runtime step 9 — only ~30-40 row nodes in DOM"
    status: pending
  - id: ac13
    statement: Project stays green
    proof_method: "npm run build && npm run lint && npm run test — all exit 0"
    status: pending
status: in_progress
---

## Decision Ledger

Grill appends one entry per resolved Meaningful Decision: the question, the
choice, and a one-line rationale.

### Open (from scope — grill to resolve)

- **D1 — Control IA.** Where do the controls live: a filter drawer, inline
  per-column header popovers, or an expanded toolbar? (Toolbar already holds
  search + edited + layout toggle.) — RESOLVED (revised by the `/table html`
  spec: stacked control bars, not a chip bar)
- **D2 — Table-only vs. both views.** Sort/column-toggle/range-filters only
  apply to the table; search + edited already apply to grid too. What happens to
  the table-only controls when the user switches to the grid? — RESOLVED
- **D3 — URL encoding scheme.** How to serialize the boolean filter tree +
  multi-key sort + hidden-column set into `useUrlState`. — RESOLVED
- **D4 — Range-filter affordance.** Dual-thumb sliders, min/max number inputs,
  or presets — for 6 stats + BST. — RESOLVED (superseded by template: numeric
  operator + value)
- **D5 — Architecture.** Adopt TanStack Table for the sort/visibility model
  (already on `@tanstack/react-virtual`), or hand-roll comparators + column
  visibility onto the existing custom table. — RESOLVED

### Resolved

- **D2 — Control scope across views.** Row filters (type chips, semantic chips,
  numeric stat ranges) apply to **both** grid and table, consistent with how
  search + edited-only already work; sort + column show/hide are **table-only**
  (the grid is dex-ordered and column-less). Switching grid→table preserves
  filters; sort/columns simply aren't shown in the grid.
  *Rationale:* filters are row predicates on the dataset; only column-level
  controls are intrinsically table-bound — keeps the existing mental model.

- **D1 — Control IA.** A **top filter bar** across the top of the screen (above
  the grid/table, present in both views) holds the type chips + semantic chips
  inline and always-visible, with a "More" disclosure for the per-stat numeric
  ranges. Column show/hide is a **popover anchored to the table** (table-only).
  Sort stays on the column headers; search + edited-only stay in the left rail.
  *Rationale:* discoverability of the common filters wins (echoes the Moves tab
  `tab-filterbar` idiom already in the repo); the rare/heavy controls (ranges,
  columns) stay behind light disclosures so the table keeps its vertical space.

- **D4 — Range-filter affordance.** **Min/max number inputs** per stat (HP, Atk,
  Def, SpA, SpD, Spe, BST) — all 7 shown as compact rows in the "More"
  disclosure, each empty until constrained. No sliders.
  *Rationale:* stats are precise integers (1–255) so typing beats dragging;
  native `<input type=number>` is accessible for free and serializes to clean
  `stat=min,max` URL pairs; a slider can be layered on later without touching
  the data model.

- **D5 — Architecture.** **Hand-roll** the sort + visibility model: a sort-spec
  array with a comparator composer for multi-key sort, a `Set<columnKey>` for
  visibility, and the existing `useMemo` filter predicates. No TanStack Table.
  *Rationale:* the filter half is already hand-rolled and trivial; the table is
  custom div-based + react-virtual so TanStack's headless model would still need
  every cell hand-rendered; its strengths (server data, grouping, complex
  columns) don't apply. The only thing given up — tested multi-sort semantics —
  is ~40 lines under TDD, and TanStack stays cheap to adopt later if needed.

- **SPEC ANCHOR — `/table html` is the reference.** The filter + sort controls
  port `~/.claude/skills/table/templates/table-template.html` (itself ported
  from "Cornerstone playerFilters / SortControls"), adapted to the dex. Read
  that template for exact behavior. Hand-rolled (consistent with D5).

- **D1 (revised) — Control layout.** Adopt the template's stacked control bars,
  not a chip bar: (1) a **filter-builder bar** = compose row (field → operator/
  value → AND/OR connector → "Add Filter" + "( )") plus a **pills** row; (2) a
  **sort-chip row**; (3) a toolbar with global search + "Columns" button +
  "Reset all"; (4) a collapsible column-toggle checkbox panel.
  *Rationale:* Chris pointed at `/table html` as the exact target.

- **D4 (revised) — Numeric filtering.** Stat predicates use the template's
  **operator + value** model (`≥ ≤ = > <`), e.g. "Atk ≥ 100"; a closed range is
  two pills (`Atk ≥ x` AND `Atk ≤ y`). Supersedes the min/max-inputs call.

- **D6 — Filter combination semantics.** **Full boolean builder** (faithful):
  per-pill **AND/OR** connectors, **NOT** negation, **parentheses** grouping
  (OR lower-precedence than AND, recursive evaluator), **drag-to-reorder** pills,
  10-filter cap. User controls the whole expression — supersedes the fixed
  faceted OR/AND scheme.
  *Rationale:* Chris chose the faithful port.

- **D7 (new) — Types + semantic tags as filter fields.** Both become first-class
  **derived filter fields** in the builder: **Type** is a select whose predicate
  is *array-contains* (Fire matches a Fire/Water species, not exact-match);
  **Class** is a select baked from `tags.json` with values
  Legendary / Mythical / Starter / (none), keyed by national dex number.
  *Rationale:* keeps one filter mental model — everything flows through the
  builder; `tags.json` is already baked.

- **D8 (new) — Big-list strategy.** **Keep virtualization.** Drop the template's
  pager; feed filtered+sorted rows straight into the existing
  `@tanstack/react-virtual` window — one continuous scroll, no pages.
  *Rationale:* matches what the dex already does; pagination would regress it.

- **Placement — control stack vs. view.** The **filter-builder bar + global
  search apply to BOTH grid and table** (honors D2); the **sort-chip row and
  Columns panel are table-only**. Switching grid→table keeps filters, reveals
  sort/columns.
  *Rationale:* filters are row predicates (both views); sort/columns are
  intrinsically table-bound.

- **Search + edited reconciliation (minor).** Keep the existing rail search
  (`/` shortcut, `q=` param) and rail "Edited only" toggle (`edited=1`) as-is;
  both AND with the builder. Do not duplicate edited into the builder (one
  source of truth). The template's "global search" role is filled by the
  existing rail search (name + dex); field-specific matching is available
  through builder text filters.

- **D3 — URL encoding.** **JSON-in-one-param** for the filter tree:
  `filter=` ← `encodeURIComponent(JSON.stringify(entries))`. **Flat readable
  params** for the rest: `sort=atk:desc,bst:asc` (ordered) and `hide=def,spd`
  (hidden column keys). `q=` + `edited=1` keep persisting via the rail. Parse
  defensively on read — unknown field/op drops that entry, over-cap truncates —
  matching how `readState` already guards `kind`/`view`.
  *Rationale:* the builder state is a structured object, so JSON round-trips it
  faithfully (parens/order/negation) with no custom parser or value-escaping
  bugs; sort/hide stay human-readable in the existing flat idiom. The opaque
  `filter` blob is fine — nobody hand-edits a boolean tree in the address bar.

## Plan Walkthrough

Full ExecPlan: `feature_requests/table-controls-plan.md`. Summary:

**Approach** — frontend-only, no API/data changes. Port `/table html`'s filter
builder + SortControls into React/TS over the existing virtualized dex table.
Build bottom-up across three milestones, each independently verifiable.

- **M1 — Pure logic core + Vitest.** New `lib/` modules: `dexColumns` (column
  registry, single source of truth), `dexFilters` (FilterEntry model, recursive
  boolean evaluator, array-contains Type + class-by-dex), `dexSort` (stable
  multi-key comparator), `dexTags` (`classOf`), `dexViewCodec` (JSON filter
  param + flat sort/hide, defensive decode). Introduce **Vitest** (new dev tool)
  for these. Proof: `npm run test` green (ac1–ac6).
- **M2 — State + pipeline.** Extend `useUrlState` (ViewState gains
  filter/sort/hidden via the codec) and `App.tsx` (pipeline = editedOnly + query
  + evalEntries, then stableMultiSort for the table). Proof: a hand-crafted URL
  filters + sorts the existing table before any new UI exists.
- **M3 — Control UI.** `FilterBuilder` (compose row + pills, AND/OR/NOT/parens/
  drag), `SortRow`, `ColumnsControl`, `DexControls` container; `DexTable` gains
  dynamic columns + sortable headers; rendered above both views (filters both,
  sort/columns table-only). Proof: manual runtime steps 1–9 (ac7–ac12).

**Two facts that shaped the plan:** the frontend has no test runner (⇒ add
Vitest for the pure logic, prove UI by documented runtime steps, matching repo
practice) and the table grid template is static (⇒ make `grid-template-columns`
dynamic from the visible-column set).

**Locked columns:** edited-LED, № (dex), Name stay always-visible; only data
columns toggle. **Sort:** header click replaces, shift-click appends, "+ Add
sort" menu — covers both issue #2's wording and the template's model.

Acceptance criteria with proof methods are in the frontmatter (ac1–ac13).

**APPROVED 2026-06-13** — human approved the plan as-is (incl. adding Vitest for
pure logic, locked LED/№/Name columns, no Playwright). Advanced to implement
stage; first work is Milestone 1 (pure logic core + Vitest). Resume in a new
chat with bare `/dev`.

## Proof Ledger

prove-it writes one line per acceptance criterion.
