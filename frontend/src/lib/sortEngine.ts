/* Stable, numeric-aware, multi-key sorting — entity-generic. Missing values
   always sort to the end regardless of direction (a row with no value is "least
   known", not "smallest"). The per-entity column set supplies the sortValue
   accessors and cell types; the comparison logic here never touches the entity.
   Pure, no React. */

export interface SortKey {
  field: string;
  direction: "asc" | "desc";
}

/** The minimal column shape the sort engine needs: a key, a cell type, and an
    accessor. The dex/move/ability column registries are supersets of this. */
export interface SortColumn<T> {
  key: string;
  cellType: "number" | "string";
  sortValue: (item: T) => string | number | undefined;
}

type CellValue = string | number | undefined;

function isMissing(value: CellValue): boolean {
  return (
    value === undefined ||
    value === null ||
    (typeof value === "number" && Number.isNaN(value))
  );
}

/** Ascending comparison of two cell values, missing-to-end. Never collapses a
    missing value to 0, so a present value always outranks a missing one. */
export function compareVals(
  a: CellValue,
  b: CellValue,
  type: "number" | "string",
): number {
  const aMissing = isMissing(a);
  const bMissing = isMissing(b);
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;
  if (type === "number") {
    return (a as number) - (b as number);
  }
  return String(a).localeCompare(String(b), undefined, { numeric: true });
}

/** Sort rows by each key in priority order; ties fall back to original order
    (stable). Direction flips the order of present values only — missing values
    stay at the end either way. Returns a new array; does not mutate input. The
    `columnByKey` map supplies the per-field accessor + cell type. */
export function stableMultiSort<T>(
  rows: T[],
  keys: SortKey[],
  columnByKey: Map<string, SortColumn<T>>,
): T[] {
  if (keys.length === 0) {
    return rows.slice();
  }
  const decorated = rows.map((row, index) => ({ row, index }));
  decorated.sort((left, right) => {
    for (const key of keys) {
      const column = columnByKey.get(key.field);
      if (!column) continue;
      const a = column.sortValue(left.row);
      const b = column.sortValue(right.row);
      const aMissing = isMissing(a);
      const bMissing = isMissing(b);
      let comparison: number;
      if (aMissing || bMissing) {
        if (aMissing && bMissing) {
          comparison = 0;
        } else {
          comparison = aMissing ? 1 : -1; // missing last, direction-independent
        }
      } else {
        comparison = compareVals(a, b, column.cellType);
        if (key.direction === "desc") {
          comparison = -comparison;
        }
      }
      if (comparison !== 0) {
        return comparison;
      }
    }
    return left.index - right.index;
  });
  return decorated.map((entry) => entry.row);
}
