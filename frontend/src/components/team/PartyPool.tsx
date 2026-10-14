import { useCallback, useEffect, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { Fit } from "../../lib/teamFit";
import type { DexEntry } from "../../types";
import { FitChips } from "./FitChips";
import { DexCell } from "../DexCell";
import { useElementWidth } from "../DexGrid";
import "../dex-cell.css";

type Props = {
  /** The pool, already searched + filtered by the Team tab. */
  entries: readonly DexEntry[];
  /** chrooked_ids already on the team — those cards read as picked. */
  partyIds: ReadonlySet<string>;
  onAdd: (chrookedId: string) => void;
  backdropTargetId: string | null;
  /** Suggest mode: each card's team-fit reasons, shown as a chip line under it. */
  fits?: ReadonlyMap<string, Fit> | null;
  /** The card under the pointer or keyboard focus (null when it leaves). */
  onPoint?: (chrookedId: string | null) => void;
};

const CHIP_ROW = 52; // the two-line FitChips block under each card in Suggest mode
const MIN_CELL = 176; // matches the dex grid's MIN_CELL
const GAP = 12;
const ROW_HEIGHT = 214; // cell height + gap, as in DexGrid

/**
 * The available-species pool: the same sprite cards the Species grid uses, in a
 * wrapping grid that fills the Team tab's left column and scrolls on its own.
 * Rows are windowed (the DexGrid recipe) so the full ~1451-card pool costs only
 * the visible band; ARIA carries the real total that windowing hides.
 */
export function PartyPool({ entries, partyIds, onAdd, backdropTargetId, fits, onPoint }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const { width, measureRef } = useElementWidth();
  const columns = width === 0 ? 1 : Math.max(1, Math.floor((width + GAP) / (MIN_CELL + GAP)));
  const rowCount = Math.ceil(entries.length / columns);

  const virtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT + (fits ? CHIP_ROW : 0),
    overscan: 3,
  });
  // Row height changes when Suggest toggles; re-measure so rows don't overlap.
  const hasFits = !!fits;
  useEffect(() => {
    virtualizer.measure();
  }, [hasFits, virtualizer]);

  const setRefs = useCallback(
    (node: HTMLDivElement | null) => {
      scrollRef.current = node;
      measureRef(node);
    },
    [measureRef],
  );

  return (
    <div
      className="party-pool"
      id="party-pool"
      ref={setRefs}
      role="listbox"
      aria-label={`Available species — ${entries.length}`}
      tabIndex={-1}
    >
      <div className="party-pool__sizer" style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map((row) => {
          const start = row.index * columns;
          return (
            <div
              key={row.key}
              className="party-pool__row"
              style={{
                transform: `translateY(${row.start}px)`,
                gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
              }}
            >
              {entries.slice(start, start + columns).map((entry) => {
                const onTeam = partyIds.has(entry.chrooked_id);
                return (
                  <div
                    key={entry.chrooked_id}
                    className="party-pool__cell"
                    role="option"
                    aria-selected={onTeam}
                    data-on-team={onTeam}
                    onPointerEnter={onPoint && (() => onPoint(entry.chrooked_id))}
                    onPointerLeave={onPoint && (() => onPoint(null))}
                    onFocus={onPoint && (() => onPoint(entry.chrooked_id))}
                    onBlur={onPoint && (() => onPoint(null))}
                  >
                    <DexCell
                      entry={entry}
                      isSelected={onTeam}
                      onOpen={onAdd}
                      backdropTargetId={backdropTargetId}
                    />
                    {onTeam && <span className="party-pool__tag mono">on team</span>}
                    {fits && !onTeam && fits.get(entry.chrooked_id) && (
                      <FitChips fit={fits.get(entry.chrooked_id)!} />
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
