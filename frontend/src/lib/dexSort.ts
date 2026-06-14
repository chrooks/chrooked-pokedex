/* Stable, numeric-aware, multi-key sorting over dex rows. Missing values always
   sort to the end regardless of direction (a row with no BST is "least known",
   not "smallest"). Pure, no React. */

import type { DexEntry } from "../types";
import type { ColumnKey } from "./dexColumns";
import { COLUMN_BY_KEY } from "./dexColumns";

export interface SortKey {
  field: ColumnKey;
  direction: "asc" | "desc";
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
  // Also guards standalone callers; stableMultiSort pre-checks missing values
  // so it can keep them direction-independent, but compareVals must stand alone.
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
    stay at the end either way. Returns a new array; does not mutate input. */
export function stableMultiSort(rows: DexEntry[], keys: SortKey[]): DexEntry[] {
  if (keys.length === 0) {
    return rows.slice();
  }
  const decorated = rows.map((row, index) => ({ row, index }));
  decorated.sort((left, right) => {
    for (const key of keys) {
      const column = COLUMN_BY_KEY.get(key.field);
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
