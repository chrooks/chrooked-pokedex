/* The column registry: one in-code list describing every table column. The
   table render, the filter defs, the sort comparators, and the columns panel
   all derive from this single source so they cannot drift. Pure, no React. */

import type { DexEntry } from "../types";
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
  | "abilities";

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
];

/** Lookup a column by key. */
export const COLUMN_BY_KEY: Map<ColumnKey, Column> = new Map(
  COLUMNS.map((column) => [column.key, column]),
);
