import { useCallback, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { DexEntry } from "../types";
import { DexCell } from "./DexCell";
import "./dex-grid.css";

type Props = {
  entries: DexEntry[];
  selected: string | null;
  onOpen: (chrookedId: string) => void;
};

const MIN_CELL = 138; // px; matches the grid template below
const GAP = 12;
const ROW_HEIGHT = 168; // cell height + gap

/**
 * A windowed sprite grid over the full national dex (~1451 cells). Columns flow
 * to the container width; rows are virtualized so only the visible band mounts.
 * ARIA grid semantics carry the total set size, which windowing otherwise hides.
 */
export function DexGrid({ entries, selected, onOpen }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const { width, measureRef } = useElementWidth();
  const columns = width === 0 ? 1 : Math.max(1, Math.floor((width + GAP) / (MIN_CELL + GAP)));

  const rowCount = Math.ceil(entries.length / columns);
  const rowVirtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 4,
  });

  const setRefs = useCallback(
    (node: HTMLDivElement | null) => {
      scrollRef.current = node;
      measureRef(node);
    },
    [measureRef],
  );

  return (
    <div
      className="dex-grid"
      ref={setRefs}
      id="dex-grid"
      role="grid"
      aria-label={`Canon dex — ${entries.length} species`}
      aria-rowcount={rowCount}
      aria-colcount={columns}
    >
      <div
        className="dex-grid__sizer"
        style={{ height: `${rowVirtualizer.getTotalSize()}px` }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const start = virtualRow.index * columns;
          const rowEntries = entries.slice(start, start + columns);
          return (
            <div
              key={virtualRow.key}
              className="dex-grid__row"
              role="row"
              aria-rowindex={virtualRow.index + 1}
              style={{
                transform: `translateY(${virtualRow.start}px)`,
                gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
              }}
            >
              {rowEntries.map((entry) => (
                <div key={entry.chrooked_id} className="dex-grid__cell" role="gridcell">
                  <DexCell
                    entry={entry}
                    isSelected={entry.chrooked_id === selected}
                    onOpen={onOpen}
                  />
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Track the observed width of an element via a callback ref + ResizeObserver,
    so observation starts the moment the node mounts (no null-guard race). */
function useElementWidth(): {
  width: number;
  measureRef: (node: HTMLElement | null) => void;
} {
  const [width, setWidth] = useState(0);
  const observerRef = useRef<ResizeObserver | null>(null);

  const measureRef = useCallback((node: HTMLElement | null) => {
    observerRef.current?.disconnect();
    if (node === null) {
      return;
    }
    setWidth(node.getBoundingClientRect().width);
    observerRef.current = new ResizeObserver((entries) => {
      setWidth(entries[0].contentRect.width);
    });
    observerRef.current.observe(node);
  }, []);

  return { width, measureRef };
}
