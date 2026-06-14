# Dex table sort / filter / search / column-toggle controls

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository checks in `~/.claude/PLAN.md`; this document must be maintained in accordance with that guide (prose-first, self-contained, novice-guiding, outcome-focused).

It implements GitHub issue #2 and is the heavy detail behind the control file `feature_requests/table-controls-throughline.md`. The Throughline's resolved Decision Ledger is the contract; this plan honors those decisions and does not reopen them.


## Purpose / Big Picture

Today the Canon dex (the `Dex` tab of the web tool at `frontend/`) gives you two ways to narrow ~1451 species: a name/number search box and an "Edited only" toggle, both in the left rail. You cannot ask questions like "show me every Fire-or-Water species with Attack at least 100, sorted by base-stat total" or "hide the special-stat columns and sort by Speed". This change adds a full data-table control surface over the dex: a boolean **filter builder**, a multi-key **sort** row, **column show/hide**, and free-text **search**, with the whole configured view saved in the URL so it survives a reload and can be shared as a link.

After this change, on the `Dex` tab you can:

- Build a filter expression out of **pills** — e.g. `Atk ≥ 100` AND `NOT Type:"Bug"` AND `( Class:"Legendary" OR BST ≥ 600 )` — combining them with per-pill AND/OR, negating any with NOT, grouping with parentheses, and dragging pills to reorder.
- Filter by **Type** (matches a species that *has* that type, so Fire matches a Fire/Water species) and by **Class** — Legendary, Mythical, or Starter — a category that is not stored on a species but baked into `frontend/src/data/tags.json` keyed by national dex number.
- **Sort** the table by clicking a column header (click again to flip direction), add secondary/tertiary sort keys (shift-click a header, or use the "+ Add sort" menu), and see a sort-chip row showing the active keys in priority order.
- **Show or hide** any data column from a "Columns" checklist; hiding a column also drops it from the sort.
- Have all of the above — filters, sort, hidden columns, search — **persist in the URL** and restore exactly on reload.

You can see it working by running the app (`cd frontend && npm run dev`, then open the printed `http://localhost:5173` URL), clicking the `Dex` tab, switching to the `Table` layout, and exercising the controls; the row-count readout in the header updates live as you filter.

The exact behavior is ported from the `/table html` skill template at `~/.claude/skills/table/templates/table-template.html` (itself ported from a "Cornerstone playerFilters / SortControls" implementation), adapted from its vanilla-JS + pagination shape to this repo's React + TypeScript + virtualized table.


## Progress

- [x] (2026-06-13) Scope + grill complete; nine decisions resolved and recorded in `feature_requests/table-controls-throughline.md`.
- [x] (2026-06-13) ExecPlan authored.
- [x] (2026-06-14) Milestone 1 — Pure logic core + Vitest (filter model, sort, columns registry, tags, URL codec). 42 unit tests green. Commit `618114f` (+ data `7734b49`).
- [x] (2026-06-14) Milestone 2 — State + pipeline: extended URL state, wired the filter/sort/hidden pipeline into `App.tsx`, proven via a hand-crafted URL (Type=Fire AND Atk≥100, sort bst desc) before any UI. Commit `7d58cfd`.
- [x] (2026-06-14) Milestone 3 — Control UI: filter builder, sort row, columns panel, dynamic-column sortable-header table, rendered above both views. Full Playwright runtime verification (ac7–ac12). Commit `8883621`.


## Surprises & Discoveries

- Observation: the `frontend/` workspace has **no test runner** — no Vitest, no Playwright, no test files; `package.json` scripts are only `dev`, `build`, `lint`, `preview`. Every prior milestone was proven by `tsc -b && vite build` + ESLint + manual runtime smoke.
  Evidence: `frontend/package.json` devDependencies list contains no test framework; `find src -name '*.test.*'` returns nothing.
  Impact: Milestone 1 introduces Vitest specifically for the pure logic (boolean evaluator, multi-key sort, URL codec) where hand-checking in a browser is unreliable; UI behavior is proven by documented runtime steps, consistent with repo practice.

- Observation: the dex table is a single static CSS grid — `grid-template-columns` is hardcoded with twelve tracks in `frontend/src/components/dex-table.css`.
  Evidence: `dex-table.css` lines 16–30 define `1.5rem 3.5rem minmax(11rem,1.4fr) 5.5rem repeat(6,3rem) 3.5rem minmax(12rem,1.6fr)`.
  Impact: column show/hide requires the grid template to be computed at render time from the visible-column set, not left static.

- Observation: `frontend/src/data/tags.json` is keyed by national dex number (string) → array of tags; 175 entries, each with exactly one tag (81 `starter`, 71 `legendary`, 23 `mythical`), zero multi-tag entries.
  Evidence: `python3 -c "...Counter..."` over the file.
  Impact: a `classOf(dex)` helper that returns a single class string (or null) is sufficient; no need to model multiple simultaneous classes. Forms share their species' dex number, so a form inherits its species' class for free.


## Decision Log

- Decision: Introduce **Vitest** as the frontend unit-test runner, scoped to the pure-logic modules added by this feature.
  Rationale: the recursive boolean evaluator (AND/OR precedence, parentheses, NOT), the stable multi-key comparator, and the URL codec have real edge cases that are unreliable to verify by clicking in a browser; they are pure functions, ideal unit targets; the user's standards require automated tests. Playwright/E2E is deliberately *not* added here — it is a heavier lift and the repo has always proven UI via runtime smoke; UI acceptance below uses documented manual steps.
  Date/Author: 2026-06-13, Claude (plan stage).

- Decision: The row-identity columns — edited-LED, № (dex number), and Name — are **always visible (locked)**; only the data columns (Types, the six stats, BST, Abilities) are toggleable and sortable-by-header.
  Rationale: a table with no name/number column is unusable as an identity anchor; the template allows hiding everything, but that freedom is a footgun here. Recorded as a deliberate divergence from the template.
  Date/Author: 2026-06-13, Claude (plan stage).

- Decision: Support **both** the template's header-click→replace-sort + "+ Add sort" menu **and** shift-click-header→append-sort.
  Rationale: issue #2's acceptance literally says "shift-click adds secondary sort keys"; the template uses an explicit menu instead. Supporting both satisfies the issue wording and the spec anchor, and shift-click is a cheap addition to the header handler.
  Date/Author: 2026-06-13, Claude (plan stage).

- Decision: Persisted view state (filter tree, sort keys, hidden columns) lives in the **URL via the existing `useUrlState`**; the filter builder's ephemeral compose-row working values (currently-picked field/operator/value, the pending AND/OR connector) live in **component-local `useState`** and are not persisted.
  Rationale: persisted state must be readable by both views and survive reload — that is exactly what `useUrlState` already does for `kind`/`query`/`edited`/`view`; half-typed compose state is transient and would pollute the URL.
  Date/Author: 2026-06-13, Claude (plan stage).

(The nine product/architecture decisions D1–D8 + placement are recorded in full in `feature_requests/table-controls-throughline.md` and summarized in Architecture Decisions below.)


## Outcomes & Retrospective

**Completed 2026-06-14.** Yes to every Purpose question. A user can build
`Atk ≥ 100 AND NOT Type:"Bug" AND ( Class:"Legendary" OR BST ≥ 600 )` out of
pills (per-pill AND/OR, NOT, parens, drag + Alt+Arrow reorder), sort by multiple
column-header keys (click + shift-click, arrows + priority ordinals), hide data
columns (LED/№/Name locked), and restore the whole view — filters, sort, hidden,
search — from a shared/reloaded URL. Filters apply to both grid and table; sort
and columns are table-only; virtualization stayed intact (~23 row nodes for
1451 species).

**What shaped the build vs. the plan:**
- Introduced Vitest as planned (42 tests) for the pure logic; UI proven by
  documented Playwright runtime steps.
- The static grid template became a `--dexcols` CSS custom property computed from
  the visible-column set, as anticipated.
- Two refinements surfaced during review/verification: the URL filter param was
  double-encoded (codec did `encodeURIComponent` on top of `URLSearchParams`) —
  fixed to single-encode; and the table header/cells were iterating two
  different column lists — unified to one `visible` list so they cannot drift.

**Review caught (and fixed) four real defects:** a stray-`)` filter bypass, a
`NUMERIC_FIELDS`/`COLUMNS` single-source-of-truth drift, header/cell alignment
drift, and pill accessibility gaps (no accessible name, drag-only reorder).


## Code Review Findings

Populated after code review — leave blank until review is complete.

### High Risk

### Medium Risk

### Low Risk


## Context and Orientation

The web tool is a single-page React app in `frontend/`, built with Vite and TypeScript. It talks to a FastAPI backend, but **this feature is frontend-only** — it adds no endpoints and changes no Python. Everything operates on data already fetched by `GET /api/dex`.

The pieces a newcomer must know, by full path:

- `frontend/src/types.ts` — the JSON shapes. The relevant one is `DexEntry`: a merged species row with `dex: number | null`, `chrooked_id: string`, `name: string`, `types: string[]` (one or two type names like `"Fire"`), `abilities: { primary, secondary, hidden }` (each `string | null`), `stats: Record<string, number>` (keys `hp atk def spa spd spe`), and `overridden_fields: string[]` (non-empty ⇒ the species is "edited" by the Ruleset).
- `frontend/src/lib/format.ts` — pure display helpers already present: `STAT_ORDER` (`["hp","atk","def","spa","spd","spe"]`), `STAT_LABEL`, `TYPES` (the 18 type display names), `bst(stats)` (sum of the six stats, or `undefined` if any is missing), `isEdited(entry)`, `dexLabel(dex)`.
- `frontend/src/hooks/useUrlState.ts` — a tiny hand-rolled router. It exposes `useUrlState(): [ViewState, (patch) => void]`. `ViewState` currently is `{ kind, query, editedOnly, selected, layout }`. It reads from `window.location.search`, caches a stable snapshot keyed by the raw query string (required by `useSyncExternalStore`), and writes via `history.replaceState` + a custom `chrooked:urlchange` event. **This is the file the new persisted state plugs into.**
- `frontend/src/App.tsx` — the shell. It fetches the dex (`useResource<DexEntry[]>(api.dex)`), holds the `useUrlState` pair, computes a `filtered` list in a `useMemo` (currently: `editedOnly` filter + lowercased `query` substring on name/dex), and passes `filtered` to `DexView`. **This is where the filter/sort pipeline extends.**
- `frontend/src/components/DexView.tsx` — resolves load/error/empty, then renders `DexTable` (when `layout==="table"`) or `DexGrid` (when `"grid"`). **The new control bars render here, above whichever view is shown.**
- `frontend/src/components/DexTable.tsx` — the dense table: a windowed list (via `@tanstack/react-virtual`) of `role="table"` div rows. The header row and each data row are CSS grids sharing one `grid-template-columns`. Columns in order: edited-LED, №, Name (sprite + button), Types (chips), six stat cells, BST, Abilities. **This gains sortable headers and dynamic columns.**
- `frontend/src/components/dex-table.css` — the static grid template (lines 16–30) that must become dynamic.
- `frontend/src/components/tabs/MovesTab.tsx` — *reference only.* It already implements the repo's filter idiom: a `tab-filterbar` with a search input and AND-combined toggle chips (`data-on` / `aria-pressed`). The new controls are richer, but match this CSS/aria vocabulary.
- `frontend/src/data/tags.json` — `{ "<dexNumber>": ["legendary"|"mythical"|"starter"], ... }`. Baked by `scripts/build_tags.py`. The source for the **Class** filter.

Terms defined in plain language:

- **Filter builder** — the compose row plus the list of pill chips that together express a boolean filter. A *pill* is one predicate (e.g. `Atk ≥ 100`) or a parenthesis token. Each non-paren pill carries a field, an operator/value, an AND-or-OR connector to the pill before it, and a NOT flag.
- **Filter def** — a per-field descriptor telling the builder how to filter that field: `numeric` (operator `≥ ≤ = > <` + a number), `select` (a dropdown of allowed values), or `text` (substring match). Derived once from the column registry + data.
- **Sort key** — one `{ field, direction }`; the sort is an ordered list of these (priority 1, 2, 3), capped at three.
- **Column registry** — a single in-code list describing every table column: its key, label, the cell type (`number` or `string`) used for sorting and filtering, whether it is locked, and how to read its value from a `DexEntry`. The table render, the filter defs, the sort comparators, and the columns panel all derive from this one list so they cannot drift.


## Architecture Decisions

The table records the approved snapshot; the Throughline's Decision Ledger and this plan's Decision Log hold the reasoning history.

| Decision | Choice | Reason |
|----------|--------|--------|
| Control scope across views | Filter builder + search apply to **both** grid and table; sort + columns are **table-only** | Filters are row predicates on the dataset; only column-level controls are intrinsically table-bound |
| Control layout | Port `/table html`'s stacked bars: filter-builder + pills, sort-chip row, toolbar (search/Columns/Reset), collapsible column panel | Chris pointed at `/table html` as the exact target |
| Filter combination | **Full boolean builder** — per-pill AND/OR, NOT, parentheses (OR lower precedence than AND), drag-reorder, 10-filter cap | Faithful port chosen at grill |
| Numeric filtering | Operator + value (`≥ ≤ = > <`); a closed range is two pills | Template model; precise for integer stats |
| Types & semantic tags | Derived filter fields: **Type** = array-contains select; **Class** = select baked from `tags.json` | One filter mental model; tags already baked |
| Architecture | **Hand-roll** in React/TS (no TanStack Table) | Filter half already hand-rolled; table is custom + react-virtual; TanStack's strengths don't apply |
| Big list | **Keep virtualization**, drop the template's pager | Matches existing dex; pagination would regress smooth scroll |
| URL encoding | JSON filter param + flat `sort=` / `hide=`; defensive parse | Builder state is a tree (JSON round-trips it); sort/hide stay readable |
| Locked columns | edited-LED, №, Name always visible | Identity anchor; hiding them is a footgun |
| Test runner | Introduce **Vitest** for pure logic; UI proven by runtime steps | Boolean evaluator/sort/codec need real tests; repo has no test infra and proves UI by smoke |


## File Changes

### New Files

- `frontend/src/lib/dexColumns.ts` — the column registry: `ColumnKey` union, `Column` type (`key`, `label`, `cellType: "number" | "string"`, `locked: boolean`, `accessor: (e: DexEntry) => string | number | null`, `sortValue: (e) => string | number | undefined`), and the exported `COLUMNS: Column[]` in display order. Single source of truth.
- `frontend/src/lib/dexFilters.ts` — the filter model: `FilterEntry` discriminated union, `FilterDef`, `NUMERIC_OPERATORS`, `buildFilterDefs(entries: DexEntry[]): FilterDef[]`, `applyFilter(def, entry, value): boolean`, and `evalEntries(entry, filterEntries): boolean` (the recursive boolean evaluator). Pure.
- `frontend/src/lib/dexSort.ts` — `SortKey`, `compareVals(a, b, type)`, `stableMultiSort(rows, sortKeys): DexEntry[]`. Pure.
- `frontend/src/lib/dexTags.ts` — imports `tags.json`; exports `CLASS_VALUES` (`["Legendary","Mythical","Starter"]`) and `classOf(dex: number | null): string | null`. Pure.
- `frontend/src/lib/dexViewCodec.ts` — `encodeFilter` / `decodeFilter` (JSON ⇄ URL-safe string), `encodeSort` / `decodeSort` (`"atk:desc,bst:asc"`), `encodeHidden` / `decodeHidden` (`"spa,spd"`). All decoders validate against the column registry + filter defs and drop anything malformed. Pure.
- `frontend/src/components/filters/FilterBuilder.tsx` — the compose row + pills (AND/OR/NOT/parens/drag-reorder). Owns ephemeral compose state; emits the new `FilterEntry[]` via a callback.
- `frontend/src/components/filters/SortRow.tsx` — the sort-chip row + "+ Add sort" menu + "Clear sorts".
- `frontend/src/components/filters/ColumnsControl.tsx` — the "Columns" button, the collapsible checkbox panel, and "Reset all".
- `frontend/src/components/filters/DexControls.tsx` — the container that lays out FilterBuilder + (table-only) SortRow + toolbar/ColumnsControl above the view; receives the view state + setters.
- `frontend/src/components/filters/filters.css` — styling for the bars, pills, chips, menus, matching the existing token vocabulary (`var(--surface)`, `var(--line)`, etc.).
- `frontend/src/lib/dexFilters.test.ts`, `frontend/src/lib/dexSort.test.ts`, `frontend/src/lib/dexViewCodec.test.ts`, `frontend/src/lib/dexTags.test.ts` — Vitest unit tests.
- `frontend/vitest.config.ts` — minimal Vitest config (Node environment; the logic is pure, no DOM needed).

### Modified Files

- `frontend/src/hooks/useUrlState.ts` — extend `ViewState` with `filter: FilterEntry[]`, `sort: SortKey[]`, `hidden: string[]`; read them in `readState` via the codec; write them in `writeState`. Keep the stable-snapshot caching contract intact.
- `frontend/src/App.tsx` — extend the pipeline: `filtered` becomes `editedOnly` + `query` + `evalEntries(filter)`; add a `tableRows` memo applying `stableMultiSort(filtered, sort)`. Render `<DexControls>` (passing state + setters) inside the screen; pass `sort`/`hidden`/setters down to the table path; grid receives `filtered` (dex order preserved), table receives `tableRows`.
- `frontend/src/components/DexView.tsx` — accept and render the control bars above the grid/table; thread `hidden` + sort state + `onSort` into `DexTable`.
- `frontend/src/components/DexTable.tsx` — render only visible columns (from `COLUMNS` minus `hidden`); compute `grid-template-columns` dynamically; make data-column headers clickable to sort with ▲/▼ arrows and shift-click-to-append; keep edited-LED/№/Name locked.
- `frontend/src/components/dex-table.css` — remove the static `grid-template-columns` value (it moves to an inline style / CSS custom property driven by the visible set); keep the rest.
- `frontend/package.json` — add `vitest` (and `@vitest/coverage-v8` optional) to devDependencies; add `"test": "vitest run"` and `"test:watch": "vitest"` scripts.

### Deleted Files

- None.


## Data & API Changes

No data or API changes. No new endpoints, no schema changes, no migrations. `tags.json` already exists (committed by a prior session via `scripts/build_tags.py`). The feature is pure frontend over the existing `GET /api/dex` payload.


## Plan of Work

The work proceeds bottom-up: pure logic first (testable in isolation), then the state/pipeline wiring (provable with a hand-made URL before any UI exists), then the control UI.

**Column registry first.** In `frontend/src/lib/dexColumns.ts`, define `COLUMNS` covering: `led` (locked, not sortable/filterable — identity LED), `dex` (locked, number), `name` (locked, string), `types` (string cell; sortValue = first type; filter via array-contains), `hp atk def spa spd spe` (number), `bst` (number; accessor uses `bst(entry.stats)`), `abilities` (string cell; sortValue = primary; filter via text across the three slots), and a virtual `class` field for filtering only (not a visible column — Legendary/Mythical/Starter from `classOf`). Mark which are `locked` (led/dex/name) and which are sortable-by-header (all data columns). The `class` and `type` filter behaviors are special-cased in `buildFilterDefs`/`applyFilter` since they are not plain scalar cells.

**Filter model.** In `dexFilters.ts`, port the template's logic:

    type FilterEntry =
      | { kind: "filter"; id: string; field: string; op?: string; value: string; connector: "AND" | "OR"; negated: boolean }
      | { kind: "paren"; id: string; paren: "(" | ")"; connector: "AND" | "OR" }

`buildFilterDefs(entries)` returns one `FilterDef` per filterable field: `numeric` for number columns (`dex`, the six stats, `bst`), `select` for `type` (values = `TYPES`) and `class` (values = `CLASS_VALUES`), `text` for `name` and `abilities`. `applyFilter(def, entry, value)` evaluates one predicate: numeric splits `"op|number"` and applies `≥ ≤ = > <`; `type` select tests `entry.types.includes(value)` (array-contains — the key dex adaptation); `class` select tests `classOf(entry.dex) === value`; `text` does an accent-stripped substring match against the field's string (abilities joins its slots). `evalEntries(entry, filterEntries)` is the recursive evaluator ported verbatim in spirit from the template: split into OR-separated groups, AND within a group, recurse into paren groups, apply NOT per leaf. Empty list ⇒ everything passes.

**Sort.** In `dexSort.ts`, `compareVals(a, b, type)` compares numbers (with NaN/undefined sorting to the end, never collapsing to 0) and strings (`localeCompare` with `numeric: true`); `stableMultiSort(rows, sortKeys)` decorates with original index for stability, compares by each key in priority order with direction applied, and falls back to original order.

**Tags + codec.** `dexTags.ts` wraps `tags.json` with `classOf`. `dexViewCodec.ts` encodes the filter tree as `encodeURIComponent(JSON.stringify(entries))` and decodes defensively (parse, then keep only entries whose `field` exists in the filter defs and whose shape is valid; cap at 10); `sort` encodes as comma-joined `field:dir` and decodes dropping unknown fields / bad directions / over-cap; `hidden` encodes as comma-joined keys and decodes dropping unknown or locked keys.

**State + pipeline.** Extend `ViewState` and `readState`/`writeState` in `useUrlState.ts` to carry `filter`/`sort`/`hidden` through the codec. In `App.tsx`, widen the `filtered` memo to also run `evalEntries`, add the `tableRows` sort memo, and pass everything down. At this point, before any new component renders, a URL like `?view=table&filter=%5B...%5D&sort=bst:desc` already filters and sorts the existing table — that is Milestone 2's proof.

**Control UI.** Build `FilterBuilder`, `SortRow`, `ColumnsControl`, and the `DexControls` container, styled in `filters.css`. `DexTable` switches to dynamic columns and sortable headers. `DexView` renders `DexControls` above the grid/table. Wire drag-to-reorder with the native HTML5 drag events as in the template. Respect reduced-motion (no transform animations on drag if the user prefers reduced motion). Add ARIA: the pills list is a group; connector/NOT toggles are buttons with `aria-pressed`; sortable headers expose `aria-sort`.


## Concrete Steps

All commands run from `frontend/` unless noted.

Install the test runner (Milestone 1):

    cd frontend
    npm install -D vitest
    # add "test": "vitest run" to package.json scripts

Run the unit tests (after writing them):

    npm run test
    # expect: Test Files  4 passed (4)
    #         Tests       N passed (N)

Type-check, lint, build (run at every milestone boundary):

    npm run build      # tsc -b && vite build — expect exit 0
    npm run lint       # eslint . — expect exit 0

Run the app for manual verification (Milestone 2 hand-URL, Milestone 3 full):

    npm run dev
    # open the printed http://localhost:5173

Milestone 2 hand-URL proof (no UI yet): with the app running, paste a URL that encodes one filter + one sort, e.g. a `filter=` holding `[{"kind":"filter","field":"atk","op":"≥","value":"≥|100",...}]` (the FilterBuilder will generate these; for the manual proof, construct via the browser console using the codec) and `sort=bst:desc`, then confirm the existing table shows only Atk-≥-100 species ordered by descending BST.


## Validation and Acceptance

Acceptance is phrased as observable behavior. Pure-logic criteria are proven by Vitest tests that fail before the implementation and pass after; UI criteria are proven by the manual runtime steps below.

### Manual Verification Steps

With `npm run dev` running and the `Dex` tab → `Table` layout open:

1. Click the `ATK` column header. The rows reorder by Attack and a `▼` appears on `ATK`. Click again → `▲`, order flips. Shift-click the `SPE` header → a sort-chip row shows `1. ATK ▲` and `2. SPE ▼`, and ties on Attack break by Speed.
2. In the filter builder, pick field `Type`, value `Fire`, click `Add Filter`. A pill `Type: "Fire"` appears; the row-count readout drops; only species that have Fire (including dual-types like Fire/Flying) remain. Switch to the `Grid` layout — the same species are shown (filter applies to both views); switch back.
3. Add a second pill `BST ≥ 600`. Toggle its connector to `OR`. Now species that are Fire **or** have BST ≥ 600 show. Click `( )`, drag the parens to wrap the two type/BST pills, add `AND Class: "Legendary"` outside — confirm grouping changes the result set.
4. Click `NOT` on the `Type: "Fire"` pill — it negates (now "not Fire"). Click the pill's `×` to remove it.
5. Open `Columns`, uncheck `SPA` and `SPD`. Those two columns disappear from the table and the remaining columns re-flow evenly. If `SPA` was an active sort key, it is removed from the sort row.
6. Type `char` into the search box → only species whose name/number contains "char" remain, combined (AND) with the active filters.
7. Copy the browser URL, open a new tab, paste, load. The exact same pills, sort chips, hidden columns, and search are restored.
8. Click `Reset all` → filters, sort, hidden columns, and search clear; the full dex returns.
9. With no filters, confirm scrolling the full list is smooth and the DOM holds only a windowed subset of rows (virtualization intact) — open dev tools and verify only ~30–40 `.dex-table__row` nodes exist at once.

### Acceptance Criteria

| id | statement | proof_method |
|----|-----------|--------------|
| ac1 | The boolean evaluator honors AND/OR precedence (OR binds looser), parenthesis grouping, and per-leaf NOT | vitest: `dexFilters.test.ts` — assert `evalEntries` over fixtures (`A OR B AND C`, `(A OR B) AND C`, `NOT A`) returns the expected pass/fail; fails before, passes after |
| ac2 | Numeric operators `≥ ≤ = > <` select the correct rows on stats/BST/№ | vitest: `dexFilters.test.ts` — `applyFilter` on a numeric def for each operator |
| ac3 | The Type filter is array-contains — `Fire` matches a Fire/Water species | vitest: `dexFilters.test.ts` — `applyFilter` type-select on a dual-type fixture passes for either of its types and fails for a third |
| ac4 | The Class filter selects Legendary/Mythical/Starter by national dex number | vitest: `dexTags.test.ts` + `dexFilters.test.ts` — `classOf(144)==="Legendary"`, `classOf(151)==="Mythical"`, `classOf(1)==="Starter"`, `classOf(16)===null`; `applyFilter` class-select matches accordingly |
| ac5 | Multi-key sort is stable, numeric-aware (missing values sort to the end), and direction-aware | vitest: `dexSort.test.ts` — `stableMultiSort` over a fixture sorted by `type asc` then `bst desc`; assert order + that a missing-BST row lands last |
| ac6 | The URL codec round-trips filter tree + sort + hidden, and a corrupt/unknown payload decodes to a safe state (no throw, malformed entries dropped) | vitest: `dexViewCodec.test.ts` — `decode(encode(x)) deep-equals x`; `decodeFilter("%7Bbroken")` returns `[]`; `decodeSort("atk:sideways,bogus:asc")` drops both; `decodeHidden("name,spa")` drops the locked `name` |
| ac7 | Clicking a column header sorts the table and shows ▲/▼; shift-click appends a secondary key; the sort-chip row reflects priority | manual runtime step 1; DOM: `aria-sort` on the header, ordinal labels in the sort row |
| ac8 | Adding a filter pill narrows visible rows in **both** grid and table and updates the row-count readout | manual runtime step 2 |
| ac9 | Per-pill AND/OR, NOT, and parenthesis grouping change the result set as expressed | manual runtime steps 3–4 |
| ac10 | Column toggles hide/show data columns and drop a hidden column from the sort; locked columns (LED/№/Name) cannot be hidden | manual runtime step 5; the Columns panel offers no checkbox for locked columns |
| ac11 | Filters + sort + hidden columns + search persist in the URL and restore exactly on reload | manual runtime step 7 |
| ac12 | The full dex stays responsive and virtualized while filtering/sorting | manual runtime step 9 |
| ac13 | The project stays green | run `npm run build && npm run lint && npm run test` — all exit 0 |


## Testing Plan

### Unit Tests (Vitest)

- `dexFilters.test.ts` — `buildFilterDefs` derives the right method per field; `applyFilter` for numeric/select/text including type array-contains and class-by-dex; `evalEntries` precedence, parens, NOT, empty-list-passes, 10-cap respected by the builder.
- `dexSort.test.ts` — `compareVals` number vs string, NaN/undefined-to-end; `stableMultiSort` single key, multi key, stability, direction.
- `dexViewCodec.test.ts` — round-trip identity for filter/sort/hidden; defensive decoding of malformed/unknown/locked inputs.
- `dexTags.test.ts` — `classOf` for known legendary/mythical/starter dex numbers and a plain species.

### Integration Tests

- None automated (no backend change). The "integration" is the URL-state pipeline, exercised by the Milestone 2 hand-URL proof and manual step 7.

### E2E Tests

- None added in this feature (the repo has no Playwright harness; adding one is out of scope). The manual verification steps stand in for E2E and are documented for repeatability. A future ExecPlan may add Playwright and convert steps 1–9 into automated journeys.


## Idempotence and Recovery

All steps are additive and repeatable. `npm install -D vitest` is idempotent. The new `lib/` modules and `components/filters/` are new files; re-running edits overwrites cleanly. The URL codec is defensive: a stale or malformed URL from an older encoding decodes to a safe default rather than crashing, so a user with a bookmarked pre-feature URL is unaffected. No destructive operations, no migrations.


## Artifacts and Notes

Expected `npm run test` transcript shape (Milestone 1):

    ✓ src/lib/dexFilters.test.ts  (12)
    ✓ src/lib/dexSort.test.ts  (6)
    ✓ src/lib/dexViewCodec.test.ts  (7)
    ✓ src/lib/dexTags.test.ts  (4)

    Test Files  4 passed (4)
    Tests       29 passed (29)


## Interfaces and Dependencies

New dependency: `vitest` (dev only). No runtime dependencies added; sort/filter/codec are hand-rolled per the architecture decision.

In `frontend/src/lib/dexColumns.ts`, define:

    export type ColumnKey =
      | "led" | "dex" | "name" | "types"
      | "hp" | "atk" | "def" | "spa" | "spd" | "spe" | "bst" | "abilities";

    export interface Column {
      key: ColumnKey;
      label: string;
      cellType: "number" | "string";
      locked: boolean;                       // led, dex, name
      sortable: boolean;                     // every data column
      sortValue: (e: DexEntry) => string | number | undefined;
    }

    export const COLUMNS: Column[];

In `frontend/src/lib/dexFilters.ts`, define:

    export type FilterEntry =
      | { kind: "filter"; id: string; field: string; value: string; connector: "AND" | "OR"; negated: boolean }
      | { kind: "paren"; id: string; paren: "(" | ")"; connector: "AND" | "OR" };

    export interface FilterDef { field: string; label: string; method: "numeric" | "select" | "text"; values?: string[]; }

    export function buildFilterDefs(entries: DexEntry[]): FilterDef[];
    export function applyFilter(def: FilterDef, entry: DexEntry, value: string): boolean;
    export function evalEntries(entry: DexEntry, entries: FilterEntry[]): boolean;

In `frontend/src/lib/dexSort.ts`, define:

    export interface SortKey { field: ColumnKey; direction: "asc" | "desc"; }
    export function stableMultiSort(rows: DexEntry[], keys: SortKey[]): DexEntry[];

In `frontend/src/lib/dexViewCodec.ts`, define:

    export function encodeFilter(entries: FilterEntry[]): string;
    export function decodeFilter(raw: string | null): FilterEntry[];
    export function encodeSort(keys: SortKey[]): string;
    export function decodeSort(raw: string | null): SortKey[];
    export function encodeHidden(keys: string[]): string;
    export function decodeHidden(raw: string | null): string[];

In `frontend/src/hooks/useUrlState.ts`, the extended contract:

    export interface ViewState {
      kind: KindKey;
      query: string;
      editedOnly: boolean;
      selected: string | null;
      layout: DexLayout;
      filter: FilterEntry[];   // new — persisted via dexViewCodec
      sort: SortKey[];         // new
      hidden: string[];        // new — hidden ColumnKeys
    }


## Note on this revision

2026-06-13 — Initial authoring at the DevOS plan stage for issue #2. Honors the nine decisions in `feature_requests/table-controls-throughline.md`. Surfaced two repo facts that shaped the plan: no frontend test runner (⇒ introduce Vitest for pure logic, prove UI by runtime steps) and a static table grid (⇒ dynamic `grid-template-columns`). Awaiting human approval before implementation.
