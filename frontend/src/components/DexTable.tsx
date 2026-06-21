import { useCallback, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { DexEntry } from "../types";
import { bst, dexLabel, isEdited } from "../lib/format";
import { COLUMNS, type Column, type ColumnKey } from "../lib/dexColumns";
import type { SortKey } from "../lib/dexSort";
import { TypeChip } from "./TypeChip";
import { EditedLed } from "./EditedLed";
import { DexSprite } from "./DexSprite";
import "./dex-table.css";

type Props = {
  entries: DexEntry[];
  selected: string | null;
  sort: SortKey[];
  hidden: ColumnKey[];
  onSort: (sort: SortKey[]) => void;
  onOpen: (chrookedId: string) => void;
  backdropTargetId?: string | null;
};

const ROW_HEIGHT = 38;
const MAX_SORT_KEYS = 3;

/** Grid track per column, matching the historical static template. The visible
    set joins these into `--dexcols`, so hiding a column re-flows the rest. */
const WIDTH: Record<ColumnKey, string> = {
  led: "1.5rem",
  dex: "3.5rem",
  name: "minmax(11rem, 1.4fr)",
  types: "5.5rem",
  hp: "3rem",
  atk: "3rem",
  def: "3rem",
  spa: "3rem",
  spd: "3rem",
  spe: "3rem",
  bst: "3.5rem",
  abilities: "minmax(12rem, 1.6fr)",
};

/**
 * The dense table view of the Canon dex. Columns are dynamic (the visible set
 * comes from COLUMNS minus `hidden`), and data-column headers sort on click
 * (shift-click appends a secondary key, click again flips direction). Mono data,
 * an overridden value keyed amber, the row's edited LED carrying the signal.
 * Rows are windowed; the header stays pinned.
 */
export function DexTable({ entries, selected, sort, hidden, onSort, onOpen, backdropTargetId }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const rowVirtualizer = useVirtualizer({
    count: entries.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  const hiddenSet = new Set(hidden);
  const visible = COLUMNS.filter((c) => !hiddenSet.has(c.key));
  const cols = visible.map((c) => WIDTH[c.key]).join(" ");

  const handleSort = useCallback(
    (field: ColumnKey, append: boolean) => {
      const existing = sort.find((s) => s.field === field);
      const flip = (d: "asc" | "desc"): "asc" | "desc" => (d === "asc" ? "desc" : "asc");
      if (append) {
        if (existing) {
          onSort(sort.map((s) => (s.field === field ? { ...s, direction: flip(s.direction) } : s)));
        } else if (sort.length < MAX_SORT_KEYS) {
          onSort([...sort, { field, direction: "asc" }]);
        }
      } else if (existing && sort.length === 1) {
        onSort([{ field, direction: flip(existing.direction) }]);
      } else {
        onSort([{ field, direction: "asc" }]);
      }
    },
    [sort, onSort],
  );

  return (
    <div className="dex-table" ref={scrollRef} id="dex-table">
      <div
        className="dex-table__inner"
        role="table"
        aria-label={`Canon dex — ${entries.length} species`}
        aria-rowcount={entries.length + 1}
        style={{ ["--dexcols"]: cols } as React.CSSProperties}
      >
        <div className="dex-table__head" role="row" aria-rowindex={1}>
          {visible.map((col) => (
            <HeaderCell
              key={col.key}
              col={col}
              sortIndex={sort.findIndex((s) => s.field === col.key)}
              direction={sort.find((s) => s.field === col.key)?.direction}
              multi={sort.length > 1}
              onSort={handleSort}
            />
          ))}
        </div>

        <div
          className="dex-table__body"
          style={{ height: `${rowVirtualizer.getTotalSize()}px` }}
        >
          {rowVirtualizer.getVirtualItems().map((vrow) => {
            const entry = entries[vrow.index];
            return (
              <DexRow
                key={entry.chrooked_id}
                entry={entry}
                rowIndex={vrow.index + 2}
                isSelected={entry.chrooked_id === selected}
                columns={visible}
                top={vrow.start}
                onOpen={onOpen}
                backdropTargetId={backdropTargetId}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

const HEADER_CLASS: Record<ColumnKey, string> = {
  led: "dex-table__led",
  dex: "dex-table__num",
  name: "dex-table__name",
  types: "dex-table__types",
  hp: "dex-table__stat mono",
  atk: "dex-table__stat mono",
  def: "dex-table__stat mono",
  spa: "dex-table__stat mono",
  spd: "dex-table__stat mono",
  spe: "dex-table__stat mono",
  bst: "dex-table__stat mono",
  abilities: "dex-table__abil",
};

type HeaderProps = {
  col: (typeof COLUMNS)[number];
  sortIndex: number;
  direction: "asc" | "desc" | undefined;
  multi: boolean;
  onSort: (field: ColumnKey, append: boolean) => void;
};

function HeaderCell({ col, sortIndex, direction, multi, onSort }: HeaderProps) {
  const ariaSort = direction === "asc" ? "ascending" : direction === "desc" ? "descending" : undefined;
  const label = col.key === "led" ? <span className="sr-only">Edited</span> : col.label;

  if (!col.sortable) {
    return (
      <span className={`dex-table__h ${HEADER_CLASS[col.key]}`} role="columnheader">
        {label}
      </span>
    );
  }

  return (
    <span
      className={`dex-table__h ${HEADER_CLASS[col.key]}`}
      role="columnheader"
      aria-sort={ariaSort}
    >
      <button
        type="button"
        className="dex-table__sortbtn"
        data-active={direction !== undefined || undefined}
        onClick={(e) => onSort(col.key, e.shiftKey)}
        title="Click to sort · Shift-click to add a secondary sort"
      >
        {col.label}
        {direction !== undefined && (
          <span className="dex-table__sortmark" aria-hidden="true">
            {direction === "asc" ? "▲" : "▼"}
            {multi && <span className="dex-table__sortord">{sortIndex + 1}</span>}
          </span>
        )}
      </button>
    </span>
  );
}

type RowProps = {
  entry: DexEntry;
  rowIndex: number;
  isSelected: boolean;
  columns: Column[];
  top: number;
  onOpen: (id: string) => void;
  backdropTargetId?: string | null;
};

function DexRow({ entry, rowIndex, isSelected, columns, top, onOpen, backdropTargetId }: RowProps) {
  const edited = isEdited(entry);
  const open = useCallback(() => onOpen(entry.chrooked_id), [onOpen, entry.chrooked_id]);

  return (
    <div
      className="dex-table__row"
      role="row"
      aria-rowindex={rowIndex}
      data-edited={edited || undefined}
      data-selected={isSelected || undefined}
      style={{ transform: `translateY(${top}px)` }}
      onClick={open}
    >
      {/* Cells iterate the SAME visible-column list the header uses, so header
          and data can never drift out of alignment. */}
      {columns.map((col) => renderCell(col, entry, edited, open, backdropTargetId))}
    </div>
  );
}

/** One table cell for a column. Bespoke per column kind, but always emitted from
    the shared visible-column iteration so it lines up with the header. */
function renderCell(
  col: Column,
  entry: DexEntry,
  edited: boolean,
  open: () => void,
  backdropTargetId?: string | null,
) {
  switch (col.key) {
    case "led":
      return (
        <span key="led" className="dex-table__c dex-table__led" role="cell">
          <EditedLed on={edited} />
        </span>
      );
    case "dex":
      return (
        <span key="dex" className="dex-table__c dex-table__num mono" role="cell">
          {dexLabel(entry.dex).replace("№ ", "")}
        </span>
      );
    case "name":
      return (
        <span key="name" className="dex-table__c dex-table__name" role="cell">
          <DexSprite
            chrookedId={entry.chrooked_id}
            dex={entry.dex}
            name=""
            backdropTargetId={backdropTargetId}
            size={28}
          />
          <button
            type="button"
            className="dex-table__namebtn"
            onClick={(e) => {
              e.stopPropagation();
              open();
            }}
          >
            {entry.name}
          </button>
        </span>
      );
    case "types":
      return (
        <span key="types" className="dex-table__c dex-table__types" role="cell">
          {entry.types.map((t) => (
            <TypeChip key={t} type={t} variant="code" />
          ))}
        </span>
      );
    case "bst":
      return (
        <span key="bst" className="dex-table__c dex-table__stat dex-table__bst mono" role="cell">
          {bst(entry.stats) ?? "—"}
        </span>
      );
    case "abilities":
      return (
        <span key="abilities" className="dex-table__c dex-table__abil" role="cell">
          {abilityList(entry)}
        </span>
      );
    default: {
      // one of the six stat columns
      const changed = (entry.base.stats ?? {})[col.key] !== undefined;
      return (
        <span
          key={col.key}
          className="dex-table__c dex-table__stat mono"
          role="cell"
          data-changed={changed || undefined}
        >
          {entry.stats[col.key] ?? "—"}
        </span>
      );
    }
  }
}

/** Abilities as "primary · secondary · hidden", dim, with the hidden one marked. */
function abilityList(entry: DexEntry) {
  const { primary, secondary, hidden } = entry.abilities;
  const changed = entry.base.abilities ?? null;
  const slots: { value: string | null; slot: "primary" | "secondary" | "hidden" }[] = [
    { value: primary, slot: "primary" },
    { value: secondary, slot: "secondary" },
    { value: hidden, slot: "hidden" },
  ];
  const shown = slots.filter((s) => s.value);
  if (shown.length === 0) return <span className="dex-table__faint">—</span>;
  return (
    <span className="dex-table__abils">
      {shown.map((s, i) => (
        <span
          key={s.slot}
          className="dex-table__abil-item"
          data-hidden={s.slot === "hidden" || undefined}
          data-changed={changed !== null && changed[s.slot] !== undefined ? true : undefined}
        >
          {i > 0 && <span className="dex-table__sep" aria-hidden="true"> · </span>}
          {s.value}
          {s.slot === "hidden" && <span className="sr-only"> (hidden ability)</span>}
        </span>
      ))}
    </span>
  );
}
