import { useState } from "react";
import type { FilterDef, FilterEntry } from "../../lib/filterEngine";
import type { SortKey } from "../../lib/sortEngine";
import { useCompactShell } from "../../hooks/useMediaQuery";
import { IconChevron, IconFilters } from "../icons";
import { FilterBuilder } from "./FilterBuilder";
import { SortRow, type SortableField } from "./SortRow";
import { ColumnsControl, type ToggleableColumn } from "./ColumnsControl";
import "./filters.css";

/** What the collapsed compact bar says, so folding the controls away never
    hides the fact that something is filtering or sorting the list. */
function describeState(filterCount: number, sortCount: number, hiddenCount: number): string {
  const parts: string[] = [];
  if (filterCount > 0) parts.push(`${filterCount} filter${filterCount === 1 ? "" : "s"}`);
  if (sortCount > 0) parts.push(`${sortCount} sort${sortCount === 1 ? "" : "s"}`);
  if (hiddenCount > 0) parts.push(`${hiddenCount} hidden`);
  return parts.length === 0 ? "No filters" : parts.join(" · ");
}

/** A partial update to one entity's control state (filter / sort / hidden). */
export type EntityViewPatch = {
  filter?: FilterEntry[];
  sort?: SortKey[];
  hidden?: string[];
};

type Props = {
  /** A DOM-id stem (e.g. "dexc", "movesc", "abilc") so each surface is distinct. */
  idPrefix: string;
  ariaLabel: string;
  /** The active entity's filterable fields. */
  defs: FilterDef[];
  /** Sortable fields; when empty the sort row is hidden. */
  sortable: SortableField[];
  /** Toggleable columns; when empty the columns control is hidden. */
  columns: ToggleableColumn[];
  filter: FilterEntry[];
  sort: SortKey[];
  hidden: string[];
  onChange: (patch: EntityViewPatch) => void;
};

/**
 * The shared control stack: a boolean filter builder, an optional sort row, and
 * an optional columns toggle, with a Reset-all. One engine, fed a per-entity
 * field registry + column set. The dex, moves, and abilities tabs all mount
 * this; abilities passes no `columns` (its def-list has none).
 */
export function EntityControls({
  idPrefix,
  ariaLabel,
  defs,
  sortable,
  columns,
  filter,
  sort,
  hidden,
  onChange,
}: Props) {
  const showSort = sortable.length > 0;
  const showColumns = columns.length > 0;
  const hasView = filter.length > 0 || sort.length > 0 || hidden.length > 0;

  // Hiding a column also drops it from the sort, in one atomic state change.
  function setHidden(nextHidden: string[]) {
    const nowHidden = new Set(nextHidden);
    onChange({ hidden: nextHidden, sort: sort.filter((s) => !nowHidden.has(s.field)) });
  }

  function reset() {
    onChange({ filter: [], sort: [], hidden: [] });
  }

  const compact = useCompactShell();
  const [open, setOpen] = useState(false);
  const summary = describeState(filter.length, sort.length, hidden.length);

  const body = (
    <>
      <FilterBuilder
        defs={defs}
        idPrefix={idPrefix}
        filter={filter}
        onChange={(next) => onChange({ filter: next })}
      />

      {(showSort || showColumns || hasView) && (
        <div className="dex-controls__table">
          {showSort && (
            <SortRow
              sortable={sortable}
              idPrefix={idPrefix}
              sort={sort}
              onChange={(next) => onChange({ sort: next })}
            />
          )}
          <div className="dexc-row dexc-row--end">
            {showColumns && (
              <ColumnsControl
                columns={columns}
                idPrefix={idPrefix}
                hidden={hidden}
                onChange={setHidden}
              />
            )}
            {hasView && (
              <button
                type="button"
                className="dexc-clear dexc-reset"
                id={`${idPrefix}-reset-all`}
                onClick={reset}
              >
                Reset all
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );

  // On a short screen this stack is pinned above a table that scrolls in its
  // own container, so it never scrolls away: 118px of a 430px viewport, always.
  // Collapsed by default, with a summary line that says what is active so
  // hiding it never hides state.
  if (compact) {
    return (
      <section
        className="dex-controls dex-controls--compact"
        id={`${idPrefix}-controls`}
        aria-label={ariaLabel}
      >
        <button
          type="button"
          className="dex-controls__disclosure"
          id={`${idPrefix}-controls-disclosure`}
          aria-expanded={open}
          onClick={() => setOpen((was) => !was)}
        >
          <IconFilters className="dex-controls__disclosure-icon" />
          <span className="dex-controls__summary mono">{summary}</span>
          <IconChevron className="dex-controls__chevron" data-open={open} />
        </button>
        {open && body}
      </section>
    );
  }

  return (
    <section className="dex-controls" id={`${idPrefix}-controls`} aria-label={ariaLabel}>
      {body}
    </section>
  );
}
