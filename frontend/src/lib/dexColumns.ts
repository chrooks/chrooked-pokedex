/* The column registry: one in-code list describing every table column. The
   table render, the filter defs, the sort comparators, and the columns panel
   all derive from this single source so they cannot drift. Pure, no React. */

import type { CanonicalMethod, DexEntry, Evolution } from "../types";
import { STAT_LABEL, bst } from "./format";

export type ColumnKey =
  | "led"
  | "dex"
  | "name"
  | "types"
  | "hp"
  | "atk"
  | "def"
  | "spa"
  | "spd"
  | "spe"
  | "bst"
  | "abilities"
  | "evolution";

export interface Column {
  key: ColumnKey;
  label: string;
  /** Drives both sort comparison and (for numeric) the filter method. */
  cellType: "number" | "string";
  /** led, dex, name — always visible, never hideable. */
  locked: boolean;
  /** Every data column is sortable by clicking its header. */
  sortable: boolean;
  /** Value used to sort a row by this column; undefined sorts to the end. */
  sortValue: (entry: DexEntry) => string | number | undefined;
}

/** Columns in display order. led/dex/name are the locked identity anchor; the
    rest are toggleable data columns sortable by header click. */
export const COLUMNS: Column[] = [
  {
    key: "led",
    label: "",
    cellType: "string",
    locked: true,
    sortable: false,
    sortValue: () => undefined,
  },
  {
    key: "dex",
    label: "№",
    cellType: "number",
    locked: true,
    sortable: false,
    sortValue: (entry) => entry.dex ?? undefined,
  },
  {
    key: "name",
    label: "Name",
    cellType: "string",
    locked: true,
    sortable: false,
    sortValue: (entry) => entry.name,
  },
  {
    key: "types",
    label: "Types",
    cellType: "string",
    locked: false,
    sortable: true,
    sortValue: (entry) => entry.types[0],
  },
  {
    key: "hp",
    label: STAT_LABEL.hp,
    cellType: "number",
    locked: false,
    sortable: true,
    sortValue: (entry) => entry.stats.hp,
  },
  {
    key: "atk",
    label: STAT_LABEL.atk,
    cellType: "number",
    locked: false,
    sortable: true,
    sortValue: (entry) => entry.stats.atk,
  },
  {
    key: "def",
    label: STAT_LABEL.def,
    cellType: "number",
    locked: false,
    sortable: true,
    sortValue: (entry) => entry.stats.def,
  },
  {
    key: "spa",
    label: STAT_LABEL.spa,
    cellType: "number",
    locked: false,
    sortable: true,
    sortValue: (entry) => entry.stats.spa,
  },
  {
    key: "spd",
    label: STAT_LABEL.spd,
    cellType: "number",
    locked: false,
    sortable: true,
    sortValue: (entry) => entry.stats.spd,
  },
  {
    key: "spe",
    label: STAT_LABEL.spe,
    cellType: "number",
    locked: false,
    sortable: true,
    sortValue: (entry) => entry.stats.spe,
  },
  {
    key: "bst",
    label: "BST",
    cellType: "number",
    locked: false,
    sortable: true,
    sortValue: (entry) => bst(entry.stats),
  },
  {
    key: "abilities",
    label: "Abilities",
    cellType: "string",
    locked: false,
    sortable: true,
    sortValue: (entry) => entry.abilities.primary ?? undefined,
  },
  {
    key: "evolution",
    label: "Evolution",
    cellType: "number",
    locked: false,
    sortable: true,
    sortValue: evoLevel,
  },
];

/** An evolution method as one readable string, across every shape the API can
    ship: a base-derived display string ("Level 26"), an Override dict
    (`{level: 26}`, `{item: …}`, `{method, param}`, the raw engine-token escape),
    or the structured `method_detail`. The single place that shape-switching
    lives — the column sort, the kind/level extraction, and the table cell label
    all read through it, so no caller can miss a shape. Empty = no method. */
export function evoMethodText(
  evolution: Evolution | null,
  methods?: readonly CanonicalMethod[],
): string {
  if (!evolution || !evolution.from) return "";
  const method = evolution.method;
  if (typeof method === "string") return method;
  if (method && typeof method === "object") {
    const dict = method as Record<string, unknown>;
    if ("level" in dict) return `Level ${dict.level}`;
    if ("item" in dict) return String(dict.item);
    if ("method" in dict) {
      // Humanize the canonical id ("knows_move" -> "Knows move") via the fetched
      // methods when available; the raw id is the fallback for callers (sort,
      // filter) that don't hold the list.
      const id = String(dict.method);
      const label = methods?.find((m) => m.id === id)?.label ?? id;
      return `${label}${"param" in dict ? ` ${dict.param}` : ""}`;
    }
    const values = Object.values(dict).map(String).join(" ");
    if (values !== "") return values;
  }
  const detail = evolution.method_detail;
  return detail ? `${detail.kind} ${detail.param}` : "";
}

/** The level a species evolves at, or undefined for base mons and level-less
    methods (they sort and filter to the end). */
export function evoLevel(entry: DexEntry): number | undefined {
  const match = /level\D*(\d+)/i.exec(evoMethodText(entry.evolution));
  return match ? Number(match[1]) : undefined;
}

/** The evolution method families, in filter-menu order. "None" is a base mon (or
    any species with no pre-evolution); "Other" is anything unmodeled. */
export const EVO_KINDS = [
  "None",
  "Level",
  "Item",
  "Friendship",
  "Trade",
  "Move",
  "Location",
  "Other",
] as const;
export type EvoKind = (typeof EVO_KINDS)[number];

/** Classify a species' evolution method into one family. Reads the method text
    rather than the engine token so Override and base-derived edges classify
    identically. */
export function evoKind(entry: DexEntry): EvoKind {
  const evolution = entry.evolution;
  if (!evolution || !evolution.from) return "None";
  const text = evoMethodText(evolution).toLowerCase();
  if (text === "") return "Other";
  if (/level/.test(text)) return "Level";
  if (text.includes("friendship")) return "Friendship";
  if (text.includes("trade")) return "Trade";
  if (text.includes("move") || text.startsWith("knows")) return "Move";
  if (text.startsWith("at ") || text.startsWith("in ") || text.includes("map")) {
    return "Location";
  }
  if (text.includes("stone") || text.includes("item")) return "Item";
  return "Other";
}

/** Lookup a column by key. */
export const COLUMN_BY_KEY: Map<ColumnKey, Column> = new Map(
  COLUMNS.map((column) => [column.key, column]),
);
