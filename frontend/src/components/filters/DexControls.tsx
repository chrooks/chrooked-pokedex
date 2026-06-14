import type { ColumnKey } from "../../lib/dexColumns";
import type { FilterEntry } from "../../lib/dexFilters";
import type { SortKey } from "../../lib/dexSort";
import type { DexLayout } from "../../hooks/useUrlState";
import { FilterBuilder } from "./FilterBuilder";
import { SortRow } from "./SortRow";
import { ColumnsControl } from "./ColumnsControl";
import "./filters.css";

export type DexViewPatch = {
  filter?: FilterEntry[];
  sort?: SortKey[];
  hidden?: ColumnKey[];
};

type Props = {
  filter: FilterEntry[];
  sort: SortKey[];
  hidden: ColumnKey[];
  layout: DexLayout;
  onChange: (patch: DexViewPatch) => void;
};

/**
 * The control stack above the dex. The filter builder applies to both views;
 * the sort row and column toggles are table-only (the grid is dex-ordered and
 * column-less). Switching grid→table preserves filters and reveals the rest.
 */
export function DexControls({ filter, sort, hidden, layout, onChange }: Props) {
  const isTable = layout === "table";
  const hasView = filter.length > 0 || sort.length > 0 || hidden.length > 0;

  // Hiding a column also drops it from the sort, in one atomic state change.
  function setHidden(nextHidden: ColumnKey[]) {
    const nowHidden = new Set(nextHidden);
    onChange({ hidden: nextHidden, sort: sort.filter((s) => !nowHidden.has(s.field)) });
  }

  return (
    <section className="dex-controls" id="dex-controls" aria-label="Dex view controls">
      <FilterBuilder filter={filter} onChange={(next) => onChange({ filter: next })} />

      {isTable && (
        <div className="dex-controls__table">
          <SortRow sort={sort} onChange={(next) => onChange({ sort: next })} />
          <div className="dexc-row dexc-row--end">
            <ColumnsControl hidden={hidden} onChange={setHidden} />
            {hasView && (
              <button
                type="button"
                className="dexc-clear dexc-reset"
                id="dexc-reset-all"
                onClick={() => onChange({ filter: [], sort: [], hidden: [] })}
              >
                Reset all
              </button>
            )}
          </div>
        </div>
      )}

      {!isTable && hasView && (
        <div className="dexc-row dexc-row--end">
          <button
            type="button"
            className="dexc-clear dexc-reset"
            onClick={() => onChange({ filter: [], sort: [], hidden: [] })}
          >
            Reset all
          </button>
        </div>
      )}
    </section>
  );
}
