import type { SortKey } from "../../lib/sortEngine";

/** A sortable field offered by the sort row: a stable key + a human label. The
    dex/move column registries and the ability sort list all reduce to this. */
export type SortableField = { key: string; label: string };

type Props = {
  /** The fields this entity can sort by, in menu order. */
  sortable: SortableField[];
  /** A DOM-id stem so each surface's sort row carries distinct ids. */
  idPrefix?: string;
  sort: SortKey[];
  onChange: (sort: SortKey[]) => void;
};

const MAX_SORT_KEYS = 3;

/**
 * The active multi-key sort, shown as priority-ordered chips (1, 2, 3) with a
 * direction arrow you click to flip and an × to drop. "+ Add sort" appends an
 * unused column; column-header clicks in the table drive the same state.
 */
export function SortRow({ sortable, idPrefix = "dexc", sort, onChange }: Props) {
  const label = new Map(sortable.map((c) => [c.key, c.label]));
  const unused = sortable.filter((c) => !sort.some((s) => s.field === c.key));
  const atCap = sort.length >= MAX_SORT_KEYS;

  function flip(field: string) {
    onChange(
      sort.map((s) =>
        s.field === field ? { ...s, direction: s.direction === "asc" ? "desc" : "asc" } : s,
      ),
    );
  }
  function drop(field: string) {
    onChange(sort.filter((s) => s.field !== field));
  }
  function add(field: string) {
    if (atCap || !field) return;
    onChange([...sort, { field, direction: "asc" }]);
  }

  return (
    <div className="dexc-row" id={`${idPrefix}-sort-row`}>
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
              <span className="dexc-sortchip__label">{label.get(key.field) ?? key.field}</span>
              <button
                type="button"
                className="dexc-sortchip__dir"
                aria-label={`${label.get(key.field)} ${
                  key.direction === "asc" ? "ascending" : "descending"
                }; click to flip`}
                onClick={() => flip(key.field)}
              >
                {key.direction === "asc" ? "▲" : "▼"}
              </button>
              <button
                type="button"
                className="dexc-sortchip__x"
                aria-label={`Remove ${label.get(key.field)} from sort`}
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
          id={`${idPrefix}-add-sort`}
          className="dexc-select dexc-select--add"
          aria-label="Add a sort key"
          value=""
          onChange={(e) => add(e.target.value)}
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
          id={`${idPrefix}-clear-sort`}
          aria-label="Clear all sort keys"
          onClick={() => onChange([])}
        >
          Clear
        </button>
      )}
    </div>
  );
}
