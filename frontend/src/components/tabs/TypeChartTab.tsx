import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import { EditedLed } from "../EditedLed";
import { useResource } from "../../hooks/useResource";
import { useSubmit } from "../../hooks/useSubmit";
import { useUrlState } from "../../hooks/useUrlState";
import { typeSlug } from "../../lib/format";
import {
  axisOrder,
  baseOf,
  cellKey,
  cellMap,
  cycle,
  isCellEdited,
  toOverrides,
} from "../../lib/typeChartGrid";
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
  const [editedOnly, setEditedOnly] = useState(false);

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

  const overrides = useMemo(
    () => toOverrides(working, cells),
    [working, cells],
  );
  const dirty = working.size > 0;
  const editedCount = overrides.length;

  function valueOf(cell: TypeChartCell): number {
    // On a read-only backdrop the working map must never bleed through — the
    // grid shows the fork's chart as-is. (Belt-and-suspenders to the cleared
    // working state; see the effect that resets working when the backdrop flips.)
    if (readOnly) return cell.multiplier;
    return working.get(cellKey(cell.attacker, cell.defender)) ?? cell.multiplier;
  }

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
  if (isLoading) return <p className="tab-loading">Loading type chart…</p>;

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
          <button
            type="button"
            id="type-chart-edited-only"
            className="tab-segmented__btn tc-edited-toggle"
            data-on={editedOnly}
            aria-pressed={editedOnly}
            onClick={() => setEditedOnly((on) => !on)}
          >
            Edited only
          </button>
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
        <TypeChartGrid
          axis={axis}
          byKey={byKey}
          valueOf={valueOf}
          onCell={cycleCell}
          readOnly={readOnly}
          editedOnly={editedOnly}
        />
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

type GridProps = {
  axis: string[];
  byKey: Map<string, TypeChartCell>;
  valueOf: (cell: TypeChartCell) => number;
  onCell: (cell: TypeChartCell) => void;
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

  return (
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
      ref={gridRef}
      onKeyDown={onGridKeyDown}
      style={{ "--tc-n": axis.length } as React.CSSProperties}
    >
      <div className="tc-row" role="row">
        <div className="tc-corner" role="presentation">
          <span className="tc-corner__atk">ATK</span>
          <span className="tc-corner__def">DEF</span>
        </div>
        {axis.map((def) => (
          <TypeHeader key={`col-${def}`} type={def} axis="col" />
        ))}
      </div>

      {axis.map((atk, rowIndex) => (
        <div className="tc-row" role="row" key={`row-${atk}`}>
          <TypeHeader type={atk} axis="row" />
          {axis.map((def, colIndex) => {
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
                onFocus={() =>
                  setActive({ row: rowIndex, col: colIndex })
                }
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}

function TypeHeader({ type, axis }: { type: string; axis: "row" | "col" }) {
  const slug = typeSlug(type);
  const style = { "--type": `var(--type-${slug}, var(--text-dim))` } as React.CSSProperties;
  // Attacker headers run down the LEFT edge — they are ROW headers; defender
  // headers run across the top — COLUMN headers. aria-label carries the full
  // name so AT reads "Fighting", not the truncated "FIG".
  return (
    <div
      className={`tc-head tc-head--${axis}`}
      role={axis === "row" ? "rowheader" : "columnheader"}
      data-type={slug}
      style={style}
      title={type}
      aria-label={type}
    >
      <span className="tc-head__label" aria-hidden="true">
        {type.slice(0, 3).toUpperCase()}
      </span>
    </div>
  );
}

type CellProps = {
  cell: TypeChartCell;
  value: number;
  onCell: (cell: TypeChartCell) => void;
  readOnly: boolean;
  isActive: boolean;
  onFocus: () => void;
};

function GridCell({
  cell,
  value,
  onCell,
  readOnly,
  isActive,
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
