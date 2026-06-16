/* The dex binding of the shared sort engine. The comparison logic lives in
   sortEngine.ts; this module narrows SortKey to the dex's ColumnKey and wraps
   stableMultiSort with the dex column map so existing dex callers keep the
   `(rows, keys)` signature. Pure, no React. */

import type { DexEntry } from "../types";
import type { ColumnKey } from "./dexColumns";
import { COLUMN_BY_KEY } from "./dexColumns";
import {
  compareVals as compareValsGeneric,
  stableMultiSort as stableMultiSortGeneric,
  type SortColumn,
} from "./sortEngine";

export interface SortKey {
  field: ColumnKey;
  direction: "asc" | "desc";
}

export const compareVals = compareValsGeneric;

// The dex column registry already matches SortColumn<DexEntry> structurally; the
// map is built once and reused on every sort.
const DEX_SORT_COLUMNS: Map<string, SortColumn<DexEntry>> = new Map(
  [...COLUMN_BY_KEY.entries()].map(([key, column]) => [key as string, column]),
);

/** Sort dex rows by the multi-key spec; missing-to-end, stable, non-mutating. */
export function stableMultiSort(rows: DexEntry[], keys: SortKey[]): DexEntry[] {
  return stableMultiSortGeneric(rows, keys, DEX_SORT_COLUMNS);
}
