import { useCallback, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { DexEntry } from "../types";
import { STAT_ORDER, STAT_LABEL, bst, dexLabel, isEdited } from "../lib/format";
import { spriteUrl } from "../lib/sprites";
import { TypeChip } from "./TypeChip";
import { EditedLed } from "./EditedLed";
import "./dex-table.css";

type Props = {
  entries: DexEntry[];
  selected: string | null;
  onOpen: (chrookedId: string) => void;
};

const ROW_HEIGHT = 38;

/**
 * The dense table view of the Canon dex — the docs.xlsx "Species Profile" sheet,
 * live. Mono data, tabular figures, a column per base stat; an overridden value
 * is keyed amber (the edit stays the hero) and the row carries the edited LED.
 * Rows are windowed (~1451 species); the header stays pinned. Form isn't a
 * separate column because the API folds it into the species name.
 */
export function DexTable({ entries, selected, onOpen }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const rowVirtualizer = useVirtualizer({
    count: entries.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  return (
    <div className="dex-table" ref={scrollRef} id="dex-table">
      <div
        className="dex-table__inner"
        role="table"
        aria-label={`Canon dex — ${entries.length} species`}
        aria-rowcount={entries.length + 1}
      >
        <div className="dex-table__head" role="row" aria-rowindex={1}>
          <span className="dex-table__h dex-table__led" role="columnheader">
            <span className="sr-only">Edited</span>
          </span>
          <span className="dex-table__h dex-table__num" role="columnheader">
            №
          </span>
          <span className="dex-table__h dex-table__name" role="columnheader">
            Name
          </span>
          <span className="dex-table__h dex-table__types" role="columnheader">
            Types
          </span>
          {STAT_ORDER.map((key) => (
            <span
              key={key}
              className="dex-table__h dex-table__stat mono"
              role="columnheader"
            >
              {STAT_LABEL[key]}
            </span>
          ))}
          <span className="dex-table__h dex-table__stat mono" role="columnheader">
            BST
          </span>
          <span className="dex-table__h dex-table__abil" role="columnheader">
            Abilities
          </span>
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
                top={vrow.start}
                onOpen={onOpen}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

type RowProps = {
  entry: DexEntry;
  rowIndex: number;
  isSelected: boolean;
  top: number;
  onOpen: (id: string) => void;
};

function DexRow({ entry, rowIndex, isSelected, top, onOpen }: RowProps) {
  const edited = isEdited(entry);
  const total = bst(entry.stats);
  const changedStats = entry.base.stats ?? {};
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
      <span className="dex-table__c dex-table__led" role="cell">
        <EditedLed on={edited} />
      </span>
      <span className="dex-table__c dex-table__num mono" role="cell">
        {dexLabel(entry.dex).replace("№ ", "")}
      </span>
      <span className="dex-table__c dex-table__name" role="cell">
        <Sprite entry={entry} />
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
      <span className="dex-table__c dex-table__types" role="cell">
        {entry.types.map((t) => (
          <TypeChip key={t} type={t} variant="code" />
        ))}
      </span>
      {STAT_ORDER.map((key) => (
        <span
          key={key}
          className="dex-table__c dex-table__stat mono"
          role="cell"
          data-changed={key in changedStats || undefined}
        >
          {entry.stats[key] ?? "—"}
        </span>
      ))}
      <span className="dex-table__c dex-table__stat dex-table__bst mono" role="cell">
        {total ?? "—"}
      </span>
      <span className="dex-table__c dex-table__abil" role="cell">
        {abilityList(entry)}
      </span>
    </div>
  );
}

function Sprite({ entry }: { entry: DexEntry }) {
  const src = spriteUrl(entry.chrooked_id, entry.dex);
  if (src === null) {
    return <span className="dex-table__sprite dex-table__sprite--empty" aria-hidden="true" />;
  }
  return (
    <img
      className="dex-table__sprite"
      src={src}
      alt=""
      width={28}
      height={28}
      loading="lazy"
      decoding="async"
    />
  );
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
