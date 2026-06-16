/* Entity-generic URL (de)serialization for a configured view: the boolean
   filter tree goes in one JSON param; sort and hidden columns stay human-
   readable and flat. Every decoder validates against the supplied field / sort /
   hide sets and drops anything malformed, so a stale or hand-mangled URL decodes
   to a safe state, never a throw. The dex/move/ability codecs are thin bindings
   that pass their own valid-key sets. Pure, no React. */

import type { FilterEntry } from "./filterEngine";
import type { SortKey } from "./sortEngine";

/** Per the Decision Ledger: the builder caps at 10 filter pills. */
const MAX_FILTERS = 10;
/** Sort is capped at three keys (primary/secondary/tertiary). */
const MAX_SORT_KEYS = 3;

/** The valid-key sets one entity's codec validates against. */
export interface CodecConfig {
  filterFields: Set<string>;
  sortableKeys: Set<string>;
  hideableKeys: Set<string>;
}

/** The (en/de)coders for one entity's view state. */
export interface ViewCodec {
  encodeFilter(entries: FilterEntry[]): string;
  decodeFilter(raw: string | null): FilterEntry[];
  encodeSort(keys: SortKey[]): string;
  decodeSort(raw: string | null): SortKey[];
  encodeHidden(keys: string[]): string;
  decodeHidden(raw: string | null): string[];
}

function isConnector(value: unknown): value is "AND" | "OR" {
  return value === "AND" || value === "OR";
}

/** Return a typed FilterEntry if the raw item is a well-formed, known-field pill
    or a parenthesis token; otherwise null (caller drops it). */
function validateEntry(raw: unknown, filterFields: Set<string>): FilterEntry | null {
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
      !filterFields.has(item.field) ||
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

/** Build the (en/de)coders for one entity from its valid-key sets. */
export function makeViewCodec(config: CodecConfig): ViewCodec {
  const { filterFields, sortableKeys, hideableKeys } = config;

  // The filter tree serializes to plain JSON; URLSearchParams owns percent-
  // encoding, so the codec must not add its own encodeURIComponent layer.
  function encodeFilter(entries: FilterEntry[]): string {
    return JSON.stringify(entries);
  }

  function decodeFilter(raw: string | null): FilterEntry[] {
    if (!raw) return [];
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return [];
    }
    if (!Array.isArray(parsed)) return [];
    const result: FilterEntry[] = [];
    let filterCount = 0;
    for (const item of parsed) {
      const entry = validateEntry(item, filterFields);
      if (!entry) continue;
      if (entry.kind === "filter") {
        if (filterCount >= MAX_FILTERS) continue;
        filterCount += 1;
      }
      result.push(entry);
    }
    return result;
  }

  function encodeSort(keys: SortKey[]): string {
    return keys.map((key) => `${key.field}:${key.direction}`).join(",");
  }

  function decodeSort(raw: string | null): SortKey[] {
    if (!raw) return [];
    const result: SortKey[] = [];
    const seen = new Set<string>();
    for (const part of raw.split(",")) {
      const [field, direction] = part.split(":");
      if (!sortableKeys.has(field)) continue;
      if (direction !== "asc" && direction !== "desc") continue;
      if (seen.has(field)) continue;
      seen.add(field);
      result.push({ field, direction });
      if (result.length >= MAX_SORT_KEYS) break;
    }
    return result;
  }

  function encodeHidden(keys: string[]): string {
    return keys.join(",");
  }

  function decodeHidden(raw: string | null): string[] {
    if (!raw) return [];
    const result: string[] = [];
    const seen = new Set<string>();
    for (const key of raw.split(",")) {
      if (hideableKeys.has(key) && !seen.has(key)) {
        seen.add(key);
        result.push(key);
      }
    }
    return result;
  }

  return { encodeFilter, decodeFilter, encodeSort, decodeSort, encodeHidden, decodeHidden };
}
