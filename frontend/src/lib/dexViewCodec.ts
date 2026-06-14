/* URL (de)serialization for the configured view: the boolean filter tree goes
   in one JSON param; sort and hidden columns stay human-readable and flat. Every
   decoder validates against the column registry + filter defs and drops anything
   malformed, so a stale or hand-mangled URL decodes to a safe state, never a
   throw. Pure, no React. */

import { buildFilterDefs, type FilterEntry } from "./dexFilters";
import { COLUMNS, type ColumnKey } from "./dexColumns";
import type { SortKey } from "./dexSort";

/** Per the Decision Ledger: the builder caps at 10 filter pills. */
const MAX_FILTERS = 10;
/** Sort is capped at three keys (primary/secondary/tertiary). */
const MAX_SORT_KEYS = 3;

const FILTER_FIELDS = new Set(buildFilterDefs([]).map((def) => def.field));
const SORTABLE_KEYS = new Set<ColumnKey>(
  COLUMNS.filter((column) => column.sortable).map((column) => column.key),
);
const HIDEABLE_KEYS = new Set<ColumnKey>(
  COLUMNS.filter((column) => !column.locked).map((column) => column.key),
);

// --- filter -----------------------------------------------------------------

// The filter tree serializes to plain JSON; URLSearchParams owns percent-
// encoding on write and decoding on read, so the codec must not add its own
// encodeURIComponent layer (that double-encodes the param in the address bar).
export function encodeFilter(entries: FilterEntry[]): string {
  return JSON.stringify(entries);
}

function isConnector(value: unknown): value is "AND" | "OR" {
  return value === "AND" || value === "OR";
}

/** Return a typed FilterEntry if the raw item is a well-formed, known-field
    pill or a parenthesis token; otherwise null (caller drops it). */
function validateEntry(raw: unknown): FilterEntry | null {
  if (typeof raw !== "object" || raw === null) {
    return null;
  }
  const item = raw as Record<string, unknown>;
  if (!isConnector(item.connector) || typeof item.id !== "string") {
    return null;
  }
  if (item.kind === "paren") {
    if (item.paren !== "(" && item.paren !== ")") {
      return null;
    }
    return { kind: "paren", id: item.id, paren: item.paren, connector: item.connector };
  }
  if (item.kind === "filter") {
    if (
      typeof item.field !== "string" ||
      !FILTER_FIELDS.has(item.field) ||
      typeof item.value !== "string" ||
      typeof item.negated !== "boolean"
    ) {
      return null;
    }
    return {
      kind: "filter",
      id: item.id,
      field: item.field,
      value: item.value,
      connector: item.connector,
      negated: item.negated,
    };
  }
  return null;
}

export function decodeFilter(raw: string | null): FilterEntry[] {
  if (!raw) {
    return [];
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return [];
  }
  if (!Array.isArray(parsed)) {
    return [];
  }
  const result: FilterEntry[] = [];
  let filterCount = 0;
  for (const item of parsed) {
    const entry = validateEntry(item);
    if (!entry) {
      continue;
    }
    if (entry.kind === "filter") {
      if (filterCount >= MAX_FILTERS) {
        continue;
      }
      filterCount += 1;
    }
    result.push(entry);
  }
  return result;
}

// --- sort -------------------------------------------------------------------

export function encodeSort(keys: SortKey[]): string {
  return keys.map((key) => `${key.field}:${key.direction}`).join(",");
}

export function decodeSort(raw: string | null): SortKey[] {
  if (!raw) {
    return [];
  }
  const result: SortKey[] = [];
  const seen = new Set<string>();
  for (const part of raw.split(",")) {
    const [field, direction] = part.split(":");
    if (!SORTABLE_KEYS.has(field as ColumnKey)) continue;
    if (direction !== "asc" && direction !== "desc") continue;
    if (seen.has(field)) continue;
    seen.add(field);
    result.push({ field: field as ColumnKey, direction });
    if (result.length >= MAX_SORT_KEYS) break;
  }
  return result;
}

// --- hidden columns ---------------------------------------------------------

export function encodeHidden(keys: ColumnKey[]): string {
  return keys.join(",");
}

export function decodeHidden(raw: string | null): ColumnKey[] {
  if (!raw) {
    return [];
  }
  const result: ColumnKey[] = [];
  const seen = new Set<ColumnKey>();
  for (const part of raw.split(",")) {
    const key = part as ColumnKey;
    if (HIDEABLE_KEYS.has(key) && !seen.has(key)) {
      seen.add(key);
      result.push(key);
    }
  }
  return result;
}
