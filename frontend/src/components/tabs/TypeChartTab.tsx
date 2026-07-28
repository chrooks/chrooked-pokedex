import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import { PokeballSpinner } from "../PokeballSpinner";
import { EditedLed } from "../EditedLed";
import { useResource } from "../../hooks/useResource";
import { useSubmit } from "../../hooks/useSubmit";
import { useUrlState } from "../../hooks/useUrlState";
import { typeSlug } from "../../lib/format";
import { TypeChip } from "../TypeChip";
import {
  axisOrder,
  baseOf,
  cellKey,
  cellMap,
  cycle,
  fitCellSize,
  isCellEdited,
  matchups,
  toOverrides,
} from "../../lib/typeChartGrid";
import type { Matchups, MatchupMember } from "../../lib/typeChartGrid";
import { useFitBox } from "../../lib/useFitBox";
import type { TypeChartCell } from "../../types";
import { ErrorView, EmptyView } from "../StatusView";
import { FormError } from "../editors/FormFeedback";
import "./tabs.css";
import "./type-chart.css";
import "../editors/editors.css";

/** The N×N type chart at dex parity: the FULL merged grid (base ⊕ Ruleset) is
    BOTH the canon browse view AND the editor. In canon (no backdrop) a click
    cycles a cell 0/½/×1/×2, dirty cells light up against base, and Save writes
    only the override set via PUT. In backdrop mode the grid swaps to the
    selected fork's chart ⊕ Ruleset and goes read-only; the BackdropChip rides
    along in the readout. The ×1 neutral majority is quieted so the off-neutral
    matchups — and the Ruleset's edits — are what the eye lands on. */
export function TypeChartTab() {
  const [view] = useUrlState();
  // Swap the fetcher to the Target's backdrop (fork ⊕ Ruleset) when one is set;
  // otherwise read the base ⊕ Ruleset canon. Memoized by backdrop id so
  // useResource sees a stable fetcher and refetches only when the backdrop flips.
  const fetcher = useMemo(
    () => (view.backdrop ? api.targetTypeChart(view.backdrop) : api.typeChart),
    [view.backdrop],
  );
  const { data, error, status, isLoading, reload } =
    useResource<TypeChartCell[]>(fetcher);
  const { isSaving, error: saveError, citing, run } = useSubmit();

  // Local working edits, keyed by `attacker|defender`. Absent ⇒ use the cell's
  // own multiplier. Cleared on Discard and after a successful Save (reload re-
  // reads the canonical merged grid). Read-only in backdrop mode.
  const [working, setWorking] = useState<Map<string, number>>(new Map());
  // The "Edited only" emphasis is driven by the shared rail flag (ac12), so the
  // left-rail toggle and the `E` shortcut dim untouched cells/chips here too.
  // Single source of truth — no local toggle state.
  const editedOnly = view.editedOnly;

  // The type whose matchup breakdown panel is open (row + column highlighted).
  // null ⇒ no panel. Selecting either axis for a type sets it; clicking the same
  // header, the panel's close button, or Escape clears it.
  const [selectedType, setSelectedType] = useState<string | null>(null);

  const readOnly = view.backdrop !== null;

  // Belt-and-suspenders: a read-only backdrop must never carry working edits, so
  // clear them whenever the backdrop selection flips. valueOf also short-circuits
  // in read-only, so this is defence in depth, not the sole guard.
  useEffect(() => {
    if (readOnly) setWorking(new Map());
  }, [view.backdrop, readOnly]);

  const cells = useMemo(() => data ?? [], [data]);
  const axis = useMemo(() => axisOrder(cells), [cells]);
  const byKey = useMemo(() => cellMap(cells), [cells]);

  function valueOf(cell: TypeChartCell): number {
    // On a read-only backdrop the working map must never bleed through — the
    // grid shows the fork's chart as-is. (Belt-and-suspenders to the cleared
    // working state; see the effect that resets working when the backdrop flips.)
    if (readOnly) return cell.multiplier;
    return working.get(cellKey(cell.attacker, cell.defender)) ?? cell.multiplier;
  }

  // If the selected type leaves the axis (e.g. a backdrop swap to a chart that
  // lacks it), drop the selection so the panel never references a missing type.
  useEffect(() => {
    if (selectedType !== null && !axis.includes(selectedType)) {
      setSelectedType(null);
    }
  }, [axis, selectedType]);

  // The rail search opens a type's breakdown panel by name (ac10): as the user
  // types, a matching type on the axis becomes the selected type. Exact (case-
  // insensitive) match wins; otherwise a UNIQUE prefix match, else a UNIQUE
  // substring match. A blank or ambiguous query leaves the current selection
  // alone, so clicking a header and Escape keep working. The single dispatch is
  // the URL query, shared with the rail input.
  useEffect(() => {
    // Keep-alive: this tab stays mounted when another kind is active, and the
    // query is shared across tabs — only react to it while we own the screen.
    if (view.kind !== "type-chart") return;
    const match = matchType(axis, view.query);
    if (match !== null) {
      setSelectedType(match);
    }
  }, [axis, view.query, view.kind]);

  // The breakdown lists for the open type, recomputed whenever the type, the
  // cells, or the working edits change. Built off the SAME valueOf the grid
  // shows, so it reflects edits in canon and the fork's chart in backdrop.
  const breakdown: Matchups | null = useMemo(
    () =>
      selectedType !== null
        ? matchups(selectedType, cells, valueOf)
        : null,
    // valueOf closes over `working` + `readOnly`; both are deps via `working`
    // and `view.backdrop`. eslint-disable to keep the dep list honest below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selectedType, cells, working, readOnly],
  );

  function toggleType(type: string) {
    setSelectedType((prev) => (prev === type ? null : type));
  }

  // Escape closes the breakdown panel — a LOCAL listener so it does not collide
  // with the app's detail-dialog Escape (which only fires when a detail is open).
  // We swallow the event only while a type is selected, so the global handler
  // keeps working for the dialog the rest of the time.
  useEffect(() => {
    // Keep-alive: never attach while hidden behind another tab — a capture-phase
    // listener here would steal Escape from the active tab's dialogs.
    if (selectedType === null || view.kind !== "type-chart") return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        setSelectedType(null);
      }
    }
    // Capture phase so we run before the app's window-level handler.
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [selectedType, view.kind]);

  const overrides = useMemo(
    () => toOverrides(working, cells),
    [working, cells],
  );
  const dirty = working.size > 0;
  const editedCount = overrides.length;

  function cycleCell(cell: TypeChartCell) {
    if (readOnly) return;
    const key = cellKey(cell.attacker, cell.defender);
    const next = cycle(valueOf(cell));
    setWorking((prev) => {
      const map = new Map(prev);
      // Snap back to "no working edit" when the cycle lands on the cell's own
      // merged value, so the dirty count reflects real divergence from disk.
      if (next === cell.multiplier) map.delete(key);
      else map.set(key, next);
      return map;
    });
  }

  async function save() {
    const ok = await run(() => api.putTypeChart(overrides));
    if (ok) {
      setWorking(new Map());
      reload();
    }
  }

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading)
    return (
      <div className="tab-loading">
        <PokeballSpinner label="Loading type chart…" />
      </div>
    );

  return (
    <div className="tab tab--type-chart" id="tab-type-chart">
      <div className="tab-toolbar">
        <span className="tab-toolbar__title">
          {axis.length} × {axis.length} matchups
          {editedCount > 0 && (
            <span className="tc-toolbar__edited">
              <EditedLed on variant="dot" />
              {editedCount} overridden
              <span className="sr-only"> by the Ruleset</span>
            </span>
          )}
        </span>
        <div className="tc-actions">
          {!readOnly && (
            <>
              <button
                type="button"
                id="type-chart-discard"
                className="btn"
                disabled={!dirty || isSaving}
                onClick={() => setWorking(new Map())}
              >
                Discard
              </button>
              <button
                type="button"
                id="type-chart-save"
                className="btn btn--primary"
                disabled={!dirty || isSaving}
                onClick={() => void save()}
              >
                {isSaving ? "Saving…" : "Save changes"}
              </button>
            </>
          )}
        </div>
      </div>

      {saveError !== null && (
        <FormError key={saveError} message={saveError} citing={citing} />
      )}

      {axis.length === 0 ? (
        <EmptyView message="No type chart yet. Build or regenerate the base snapshot." />
      ) : (
        <div className="tc-body" id="type-chart-body" data-paneled={selectedType !== null}>
          <TypeChartGrid
            axis={axis}
            byKey={byKey}
            valueOf={valueOf}
            onCell={cycleCell}
            onSelectType={toggleType}
            selectedType={selectedType}
            readOnly={readOnly}
            editedOnly={editedOnly}
          />
          {selectedType !== null && breakdown !== null && (
            <BreakdownPanel
              type={selectedType}
              breakdown={breakdown}
              editedOnly={editedOnly}
              onClose={() => setSelectedType(null)}
            />
          )}
        </div>
      )}

      <p className="tc-legend" aria-hidden="true">
        <span className="tc-legend__item tc-cell" data-mult="0">
          0
        </span>
        immune
        <span className="tc-legend__item tc-cell" data-mult="0.5">
          ½
        </span>
        resisted
        <span className="tc-legend__item tc-cell" data-mult="1">
          ·
        </span>
        neutral
        <span className="tc-legend__item tc-cell" data-mult="2">
          2
        </span>
        super
        {readOnly ? (
          <span className="tc-legend__hint tc-legend__hint--readonly">
            — read-only backdrop
          </span>
        ) : (
          <span className="tc-legend__hint">— click a cell to cycle</span>
        )}
      </p>
    </div>
  );
}

/** How a multiplier reads in one cell: a quiet middle dot for the ×1 neutral
    majority so off-neutral cells pop; the rest are short glyphs. */
function glyph(multiplier: number): string {
  if (multiplier === 0) return "0";
  if (multiplier === 0.5) return "½";
  if (multiplier === 1) return "·";
  if (multiplier === 2) return "2";
  return `${multiplier}`;
}

/** A spoken multiplier for aria labels — "immune", "resisted", "neutral",
    "super effective", or the raw "×N" for any non-standard value. */
function spoken(multiplier: number): string {
  if (multiplier === 0) return "immune";
  if (multiplier === 0.5) return "resisted";
  if (multiplier === 1) return "neutral";
  if (multiplier === 2) return "super effective";
  return `×${multiplier}`;
}

/** Resolve a rail-search query to a type on the axis (ac10). Exact match (case-
    insensitive) wins; otherwise a UNIQUE prefix match, then a UNIQUE substring
    match. Returns null for a blank or ambiguous query so the current selection is
    left untouched — typing keeps narrowing without clobbering a click. */
function matchType(axis: readonly string[], query: string): string | null {
  const q = query.trim().toLowerCase();
  if (q === "") return null;
  const exact = axis.find((type) => type.toLowerCase() === q);
  if (exact) return exact;
  const prefix = axis.filter((type) => type.toLowerCase().startsWith(q));
  if (prefix.length === 1) return prefix[0];
  const substr = axis.filter((type) => type.toLowerCase().includes(q));
  if (substr.length === 1) return substr[0];
  return null;
}

type GridProps = {
  axis: string[];
  byKey: Map<string, TypeChartCell>;
  valueOf: (cell: TypeChartCell) => number;
  onCell: (cell: TypeChartCell) => void;
  onSelectType: (type: string) => void;
  selectedType: string | null;
  readOnly: boolean;
  editedOnly: boolean;
};

/** The matrix itself: a CSS grid with sticky type-colored headers on both axes
    (rows = attacker, columns = defender) and one cell per matchup.

    Keyboard model — a single tab stop with ROVING TABINDEX. One active cell
    coordinate {row,col} lives in state; that cell is tabIndex=0, every other is
    tabIndex=-1. Arrow keys move the active coordinate (clamped at the edges),
    Home/End jump to row ends. In canon mode Enter/Space cycle the active cell; on
    a read-only backdrop cells stay focusable (so values can be read) but
    Enter/Space are inert. Read-only cells are <div>s with no click/key handlers. */
function TypeChartGrid({
  axis,
  byKey,
  valueOf,
  onCell,
  onSelectType,
  selectedType,
  readOnly,
  editedOnly,
}: GridProps) {
  // The active cell coordinate into the N×N matchup grid (header tracks are not
  // part of this — they are not part of the roving group).
  const [active, setActive] = useState<{ row: number; col: number }>({
    row: 0,
    col: 0,
  });
  const gridRef = useRef<HTMLDivElement>(null);
  const n = axis.length;

  // Fit-to-viewport: measure the scroll wrapper and size each cell so the whole
  // matrix + a header track fits BOTH axes with no scrollbar. Re-runs on resize
  // AND when the panel opens (the wrapper shrinks), so the grid re-fits beside
  // the panel. The clamped cell + proportional head feed CSS vars on the grid.
  const { box, measureRef } = useFitBox();
  const fit = fitCellSize(box, n);

  // Keep the active coordinate in range if the axis shrinks (e.g. backdrop swap).
  useEffect(() => {
    setActive((prev) => ({
      row: Math.min(prev.row, n - 1),
      col: Math.min(prev.col, n - 1),
    }));
  }, [n]);

  function focusCell(row: number, col: number) {
    const atk = axis[row];
    const def = axis[col];
    const el = gridRef.current?.querySelector<HTMLElement>(
      `#tc-cell-${CSS.escape(atk)}-${CSS.escape(def)}`,
    );
    el?.focus();
  }

  function moveActive(row: number, col: number) {
    const clamped = {
      row: Math.max(0, Math.min(n - 1, row)),
      col: Math.max(0, Math.min(n - 1, col)),
    };
    setActive(clamped);
    focusCell(clamped.row, clamped.col);
  }

  function onGridKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const { row, col } = active;
    switch (event.key) {
      case "ArrowRight":
        event.preventDefault();
        moveActive(row, col + 1);
        break;
      case "ArrowLeft":
        event.preventDefault();
        moveActive(row, col - 1);
        break;
      case "ArrowDown":
        event.preventDefault();
        moveActive(row + 1, col);
        break;
      case "ArrowUp":
        event.preventDefault();
        moveActive(row - 1, col);
        break;
      case "Home":
        event.preventDefault();
        moveActive(row, 0);
        break;
      case "End":
        event.preventDefault();
        moveActive(row, n - 1);
        break;
      case "Enter":
      case " ": {
        if (readOnly) break;
        event.preventDefault();
        const cell = byKey.get(cellKey(axis[row], axis[col]));
        if (cell) onCell(cell);
        break;
      }
      default:
        break;
    }
  }

  // CSS vars: the fitted cell + head sizes, the axis length, and the index of
  // the selected type so the highlight band can be drawn purely in CSS.
  const selectedIndex = selectedType !== null ? axis.indexOf(selectedType) : -1;
  const gridStyle = {
    "--tc-n": n,
    "--tc-cell": `${fit.cell}px`,
    "--tc-head": `${fit.head}px`,
    "--tc-glyph": `${Math.max(0.6, fit.cell / 36).toFixed(3)}rem`,
  } as React.CSSProperties;

  return (
    <div
      className="tc-fit"
      id="type-chart-fit"
      ref={measureRef}
      data-overflow={fit.overflow}
    >
    <div
      id="type-chart-grid"
      className="tc-grid"
      role="grid"
      aria-label={
        readOnly
          ? "Type effectiveness chart, attacker rows by defender columns — read-only backdrop"
          : "Type effectiveness chart, attacker rows by defender columns"
      }
      aria-readonly={readOnly}
      data-edited-only={editedOnly}
      data-readonly={readOnly}
      data-has-selection={selectedType !== null}
      ref={gridRef}
      onKeyDown={onGridKeyDown}
      style={gridStyle}
    >
      <div className="tc-row" role="row">
        <div className="tc-corner" role="presentation">
          <span className="tc-corner__atk">ATK</span>
          <span className="tc-corner__def">DEF</span>
        </div>
        {axis.map((def) => (
          <TypeHeader
            key={`col-${def}`}
            type={def}
            axis="col"
            selected={def === selectedType}
            onSelect={onSelectType}
          />
        ))}
      </div>

      {axis.map((atk, rowIndex) => (
        <div className="tc-row" role="row" key={`row-${atk}`}>
          <TypeHeader
            type={atk}
            axis="row"
            selected={atk === selectedType}
            onSelect={onSelectType}
          />
          {axis.map((def, colIndex) => {
            const inSelectedBand =
              selectedIndex !== -1 &&
              (rowIndex === selectedIndex || colIndex === selectedIndex);
            const isPivot =
              rowIndex === selectedIndex && colIndex === selectedIndex;
            const isActive =
              active.row === rowIndex && active.col === colIndex;
            const cell = byKey.get(cellKey(atk, def));
            if (!cell) {
              return (
                <div
                  key={cellKey(atk, def)}
                  className="tc-cell tc-cell--missing"
                  role="gridcell"
                  tabIndex={isActive ? 0 : -1}
                  data-band={inSelectedBand}
                  data-pivot={isPivot}
                  aria-label={`${atk} vs ${def}, no data`}
                  onFocus={() =>
                    setActive({ row: rowIndex, col: colIndex })
                  }
                />
              );
            }
            return (
              <GridCell
                key={cellKey(atk, def)}
                cell={cell}
                value={valueOf(cell)}
                onCell={onCell}
                readOnly={readOnly}
                isActive={isActive}
                inSelectedBand={inSelectedBand}
                isPivot={isPivot}
                onFocus={() =>
                  setActive({ row: rowIndex, col: colIndex })
                }
              />
            );
          })}
        </div>
      ))}
    </div>
    </div>
  );
}

type HeaderProps = {
  type: string;
  axis: "row" | "col";
  selected: boolean;
  onSelect: (type: string) => void;
};

function TypeHeader({ type, axis, selected, onSelect }: HeaderProps) {
  const slug = typeSlug(type);
  const style = { "--type": `var(--type-${slug}, var(--text-dim))` } as React.CSSProperties;
  // Attacker headers run down the LEFT edge — they are ROW headers; defender
  // headers run across the top — COLUMN headers. The header is a BUTTON so it is
  // keyboard-reachable and toggles the matchup breakdown panel; aria-pressed
  // reports the selected state and aria-label carries the full name (not "FIG").
  // Ids are stable + human-communicatable: #tc-head-row-<Type> / #tc-head-col-<Type>.
  return (
    <button
      type="button"
      id={`tc-head-${axis}-${type}`}
      className={`tc-head tc-head--${axis}`}
      role={axis === "row" ? "rowheader" : "columnheader"}
      data-type={slug}
      data-selected={selected}
      aria-pressed={selected}
      style={style}
      title={`${type} — show matchups`}
      aria-label={`${type}, show matchups`}
      onClick={() => onSelect(type)}
    >
      <span className="tc-head__label" aria-hidden="true">
        {type.slice(0, 3).toUpperCase()}
      </span>
    </button>
  );
}

type CellProps = {
  cell: TypeChartCell;
  value: number;
  onCell: (cell: TypeChartCell) => void;
  readOnly: boolean;
  isActive: boolean;
  inSelectedBand: boolean;
  isPivot: boolean;
  onFocus: () => void;
};

function GridCell({
  cell,
  value,
  onCell,
  readOnly,
  isActive,
  inSelectedBand,
  isPivot,
  onFocus,
}: CellProps) {
  const base = baseOf(cell);
  const edited = isCellEdited(value, cell);
  const label =
    `${cell.attacker} vs ${cell.defender} ${spoken(value)}` +
    (edited ? `, edited, was ${spoken(base)}` : "");

  const common = {
    id: `tc-cell-${cell.attacker}-${cell.defender}`,
    className: "tc-cell",
    "data-mult": `${value}`,
    "data-edited": edited,
    "data-neutral": value === 1,
    "data-band": inSelectedBand,
    "data-pivot": isPivot,
    "aria-label": label,
    title: edited ? `${cell.attacker} → ${cell.defender}: was ${spoken(base)}, now ${spoken(value)}` : label,
    children: (
      <>
        <span className="tc-cell__glyph" aria-hidden="true">
          {glyph(value)}
        </span>
        {edited && <span className="tc-cell__dot" aria-hidden="true" />}
      </>
    ),
  };

  // Read-only cells are plain divs — focusable (roving tabindex) so their value
  // can be read, but with no click/key handlers, so nothing mutates the chart.
  if (readOnly) {
    return (
      <div
        role="gridcell"
        tabIndex={isActive ? 0 : -1}
        onFocus={onFocus}
        {...common}
      />
    );
  }
  return (
    <button
      type="button"
      role="gridcell"
      tabIndex={isActive ? 0 : -1}
      onFocus={onFocus}
      onClick={() => onCell(cell)}
      {...common}
    />
  );
}

/** One labelled matchup bucket: a heading, a prominent count, and the member
    types as type-colored chips. A member whose matchup the Ruleset overrides
    carries the same edited LED the grid cell shows (data-edited on the chip li),
    and an edited count rides beside the total. An empty bucket still renders
    (label + "0" + an em-dash) so the four-way structure stays legible. The
    neutral bucket carries `tone="quiet"` so the boring majority recedes. */
/** The color accent a bucket carries (ac11). Maps to a `--tc-hue-*` token in
    type-chart.css applied to the label + accent border — red/green/blue for the
    effectiveness extremes, grey for neutral, ink for the offensive no-effect. */
type BucketHue = "red" | "green" | "blue" | "grey" | "ink";

function MatchupBucket({
  id,
  label,
  members,
  hue,
  tone = "loud",
}: {
  id: string;
  label: string;
  members: MatchupMember[];
  hue: BucketHue;
  tone?: "loud" | "quiet";
}) {
  const editedCount = members.filter((m) => m.edited).length;
  return (
    <div
      className="tc-bucket"
      id={id}
      data-tone={tone}
      data-hue={hue}
      data-empty={members.length === 0}
    >
      <div className="tc-bucket__head">
        <span className="tc-bucket__label">{label}</span>
        {editedCount > 0 && (
          <span className="tc-bucket__edited" title={`${editedCount} edited by the Ruleset`}>
            <EditedLed on variant="dot" />
            {editedCount}
            <span className="sr-only"> edited by the Ruleset</span>
          </span>
        )}
        <span className="tc-bucket__count" aria-label={`${members.length} types`}>
          {members.length}
        </span>
      </div>
      {members.length === 0 ? (
        <p className="tc-bucket__empty" aria-hidden="true">
          —
        </p>
      ) : (
        <ul className="tc-bucket__chips">
          {members.map((member) => (
            <li key={member.type} data-edited={member.edited}>
              <TypeChip type={member.type} variant="code" />
              {member.edited && (
                <span className="tc-chip-led" aria-hidden="true" />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The matchup breakdown for the selected type, docked to the RIGHT of the grid.
    Two sections — Defending (the type's column) and Attacking (its row) — each
    with the four effectiveness buckets in weight order. Read-only info: it looks
    identical in canon and backdrop, only the underlying numbers differ. */
function BreakdownPanel({
  type,
  breakdown,
  editedOnly,
  onClose,
}: {
  type: string;
  breakdown: Matchups;
  /** Mirrors the grid's Edited-only mode: dims the untouched chips so the
      Ruleset-overridden matchups are the figure in the panel too. */
  editedOnly: boolean;
  onClose: () => void;
}) {
  const slug = typeSlug(type);
  const style = { "--type": `var(--type-${slug}, var(--text-dim))` } as React.CSSProperties;
  const { defense, offense } = breakdown;
  return (
    <aside
      id="type-chart-breakdown"
      className="tc-breakdown"
      role="region"
      aria-labelledby="tc-breakdown-title"
      data-edited-only={editedOnly}
      style={style}
    >
      <header className="tc-breakdown__bar">
        <h3 className="tc-breakdown__title" id="tc-breakdown-title">
          <span className="tc-breakdown__dot" aria-hidden="true" />
          {type}
        </h3>
        <button
          type="button"
          id="tc-breakdown-close"
          className="tc-breakdown__close"
          aria-label="Close breakdown"
          onClick={onClose}
        >
          ✕
        </button>
      </header>

      <section
        className="tc-breakdown__section"
        id="tc-breakdown-defense"
        aria-labelledby="tc-breakdown-defense-title"
      >
        <h4 className="tc-breakdown__section-title" id="tc-breakdown-defense-title">
          Defending
        </h4>
        <MatchupBucket
          id="tc-bucket-weak"
          label="Weak to ×2"
          members={defense.weak}
          hue="red"
        />
        <MatchupBucket
          id="tc-bucket-resist"
          label="Resists ×½"
          members={defense.resist}
          hue="green"
        />
        <MatchupBucket
          id="tc-bucket-immune"
          label="Immune to ×0"
          members={defense.immune}
          hue="blue"
        />
        <MatchupBucket
          id="tc-bucket-def-neutral"
          label="Neutral ×1"
          members={defense.neutral}
          hue="grey"
          tone="quiet"
        />
      </section>

      <section
        className="tc-breakdown__section"
        id="tc-breakdown-offense"
        aria-labelledby="tc-breakdown-offense-title"
      >
        <h4 className="tc-breakdown__section-title" id="tc-breakdown-offense-title">
          Attacking
        </h4>
        <MatchupBucket
          id="tc-bucket-strong"
          label="Strong against ×2"
          members={offense.strong}
          hue="green"
        />
        <MatchupBucket
          id="tc-bucket-resisted"
          label="Resisted by ×½"
          members={offense.resisted}
          hue="red"
        />
        <MatchupBucket
          id="tc-bucket-noeffect"
          label="No effect ×0"
          members={offense.noEffect}
          hue="ink"
        />
        <MatchupBucket
          id="tc-bucket-off-neutral"
          label="Neutral ×1"
          members={offense.neutral}
          hue="grey"
          tone="quiet"
        />
      </section>
    </aside>
  );
}
