import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { DexEntry } from "../../types";
import { DexCell } from "../DexCell";
import "../dex-cell.css";

type Props = {
  /** The pool, already searched + filtered by the Team tab. */
  entries: readonly DexEntry[];
  /** chrooked_ids already on the team — those cards read as picked. */
  partyIds: ReadonlySet<string>;
  onAdd: (chrookedId: string) => void;
  backdropTargetId: string | null;
};

const CELL_WIDTH = 176; // matches the dex grid's MIN_CELL
const GAP = 12;

/**
 * The available-species pool: the same sprite cards the Species grid uses, laid
 * out as one horizontally scrolling line under the search bar. Windowed on the
 * horizontal axis so the full ~1451-card pool costs only the visible band, and
 * ARIA carries the real total that windowing hides.
 */
export function PartyPool({ entries, partyIds, onAdd, backdropTargetId }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const virtualizer = useVirtualizer({
    horizontal: true,
    count: entries.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => CELL_WIDTH + GAP,
    overscan: 6,
  });

  return (
    <div
      className="party-pool"
      id="party-pool"
      ref={scrollRef}
      role="listbox"
      aria-label={`Available species — ${entries.length}`}
      tabIndex={-1}
    >
      <div className="party-pool__sizer" style={{ width: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map((item) => {
          const entry = entries[item.index];
          const onTeam = partyIds.has(entry.chrooked_id);
          return (
            <div
              key={entry.chrooked_id}
              className="party-pool__cell"
              role="option"
              aria-selected={onTeam}
              data-on-team={onTeam}
              style={{ transform: `translateX(${item.start}px)`, width: `${CELL_WIDTH}px` }}
            >
              <DexCell
                entry={entry}
                isSelected={onTeam}
                onOpen={onAdd}
                backdropTargetId={backdropTargetId}
              />
              {onTeam && <span className="party-pool__tag mono">on team</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
