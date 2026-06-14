import { COLUMNS, type ColumnKey } from "../../lib/dexColumns";
import type { SortKey } from "../../lib/dexSort";

type Props = {
  sort: SortKey[];
  onChange: (sort: SortKey[]) => void;
};

const MAX_SORT_KEYS = 3;
const SORTABLE = COLUMNS.filter((c) => c.sortable);
const LABEL = new Map<ColumnKey, string>(SORTABLE.map((c) => [c.key, c.label]));

/**
 * The active multi-key sort, shown as priority-ordered chips (1, 2, 3) with a
 * direction arrow you click to flip and an × to drop. "+ Add sort" appends an
 * unused column; column-header clicks in the table drive the same state.
 * Table-only — the grid is dex-ordered.
 */
export function SortRow({ sort, onChange }: Props) {
  const unused = SORTABLE.filter((c) => !sort.some((s) => s.field === c.key));
  const atCap = sort.length >= MAX_SORT_KEYS;

  function flip(field: ColumnKey) {
    onChange(
      sort.map((s) =>
        s.field === field ? { ...s, direction: s.direction === "asc" ? "desc" : "asc" } : s,
      ),
    );
  }
  function drop(field: ColumnKey) {
    onChange(sort.filter((s) => s.field !== field));
  }
  function add(field: ColumnKey) {
    if (atCap || !field) return;
    onChange([...sort, { field, direction: "asc" }]);
  }

  return (
    <div className="dexc-row" id="dex-sort-row">
      <span className="dexc-label">Sort</span>
      {sort.length === 0 ? (
        <span className="dexc-hint">none — click a column header</span>
      ) : (
        <ul className="dexc-sortchips" aria-label="Active sort keys">
          {sort.map((key, index) => (
            <li key={key.field} className="dexc-sortchip">
              <span className="dexc-sortchip__ord" aria-hidden="true">
                {index + 1}
              </span>
              <span className="dexc-sortchip__label">{LABEL.get(key.field) ?? key.field}</span>
              <button
                type="button"
                className="dexc-sortchip__dir"
                aria-label={`${LABEL.get(key.field)} ${
                  key.direction === "asc" ? "ascending" : "descending"
                }; click to flip`}
                onClick={() => flip(key.field)}
              >
                {key.direction === "asc" ? "▲" : "▼"}
              </button>
              <button
                type="button"
                className="dexc-sortchip__x"
                aria-label={`Remove ${LABEL.get(key.field)} from sort`}
                onClick={() => drop(key.field)}
              >
                <span aria-hidden="true">×</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {unused.length > 0 && !atCap && (
        <select
          id="dexc-add-sort"
          className="dexc-select dexc-select--add"
          aria-label="Add a sort key"
          value=""
          onChange={(e) => add(e.target.value as ColumnKey)}
        >
          <option value="" disabled>
            + Add sort
          </option>
          {unused.map((c) => (
            <option key={c.key} value={c.key}>
              {c.label}
            </option>
          ))}
        </select>
      )}
      {sort.length > 0 && (
        <button
          type="button"
          className="dexc-clear"
          id="dexc-clear-sort"
          aria-label="Clear all sort keys"
          onClick={() => onChange([])}
        >
          Clear
        </button>
      )}
    </div>
  );
}
