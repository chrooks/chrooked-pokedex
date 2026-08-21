/* The dex binding of the generic view codec. Validation + JSON shape live in
   viewCodec.ts; this module supplies the dex's valid-key sets and re-exports the
   (en/de)coders with dex-typed signatures (ColumnKey / dex SortKey) so existing
   dex callers and the codec tests stay unchanged. Pure, no React. */

import { DEX_REGISTRY, type FilterEntry } from "./dexFilters";
import { COLUMNS, type ColumnKey } from "./dexColumns";
import type { SortKey } from "./dexSort";
import { makeViewCodec } from "./viewCodec";

const FILTER_FIELDS = new Set(DEX_REGISTRY.defs.map((def) => def.field));
const SORTABLE_KEYS = new Set<string>(
  COLUMNS.filter((column) => column.sortable).map((column) => column.key),
);
const HIDEABLE_KEYS = new Set<string>(
  COLUMNS.filter((column) => !column.locked).map((column) => column.key),
);

/** The raw dex codec. Exported for surfaces that filter species under their OWN
    namespaced params (the Team pool's `tfilter`) via `useEntityView`, which takes
    a whole ViewCodec rather than the dex-typed re-exports below. */
export const dexCodec = makeViewCodec({
  filterFields: FILTER_FIELDS,
  sortableKeys: SORTABLE_KEYS,
  hideableKeys: HIDEABLE_KEYS,
});

const codec = dexCodec;

export function encodeFilter(entries: FilterEntry[]): string {
  return codec.encodeFilter(entries);
}
export function decodeFilter(raw: string | null): FilterEntry[] {
  return codec.decodeFilter(raw);
}
export function encodeSort(keys: SortKey[]): string {
  return codec.encodeSort(keys);
}
export function decodeSort(raw: string | null): SortKey[] {
  return codec.decodeSort(raw) as SortKey[];
}
export function encodeHidden(keys: ColumnKey[]): string {
  return codec.encodeHidden(keys);
}
export function decodeHidden(raw: string | null): ColumnKey[] {
  return codec.decodeHidden(raw) as ColumnKey[];
}
