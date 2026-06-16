/* The Moves table column registry: one in-code list describing every column.
   The table render, filter defs, sort comparators, and columns panel all derive
   from this single source so they cannot drift. Mirrors dexColumns.ts. Pure, no
   React. */

import type { Move } from "../types";
import type { SortColumn } from "./sortEngine";

export type MoveColumnKey =
  | "led"
  | "name"
  | "type"
  | "category"
  | "power"
  | "accuracy"
  | "pp"
  | "flags";

export interface MoveColumn extends SortColumn<Move> {
  key: MoveColumnKey;
  label: string;
  cellType: "number" | "string";
  /** led + name are the always-visible identity anchor, never hideable. */
  locked: boolean;
  /** Whether the column can be a sort key (header click + sort row). */
  sortable: boolean;
  sortValue: (move: Move) => string | number | undefined;
}

/** Columns in display order. led/name are the locked identity anchor; the rest
    are toggleable data columns. `flags` (Tags) is hideable but not sortable. */
export const MOVE_COLUMNS: MoveColumn[] = [
  {
    key: "led",
    label: "",
    cellType: "string",
    locked: true,
    sortable: false,
    sortValue: () => undefined,
  },
  {
    key: "name",
    label: "Move",
    cellType: "string",
    locked: true,
    sortable: false,
    sortValue: (move) => move.name,
  },
  {
    key: "type",
    label: "Type",
    cellType: "string",
    locked: false,
    sortable: true,
    sortValue: (move) => move.type,
  },
  {
    key: "category",
    label: "Cat",
    cellType: "string",
    locked: false,
    sortable: true,
    sortValue: (move) => move.category,
  },
  {
    key: "power",
    label: "Pow",
    cellType: "number",
    locked: false,
    sortable: true,
    sortValue: (move) => move.power ?? undefined,
  },
  {
    key: "accuracy",
    label: "Acc",
    cellType: "number",
    locked: false,
    sortable: true,
    sortValue: (move) => move.accuracy ?? undefined,
  },
  {
    key: "pp",
    label: "PP",
    cellType: "number",
    locked: false,
    sortable: true,
    sortValue: (move) => move.pp ?? undefined,
  },
  {
    key: "flags",
    label: "Tags",
    cellType: "string",
    locked: false,
    sortable: false,
    sortValue: () => undefined,
  },
];

export const MOVE_COLUMN_BY_KEY: Map<MoveColumnKey, MoveColumn> = new Map(
  MOVE_COLUMNS.map((column) => [column.key, column]),
);

export const MOVE_SORT_COLUMNS: Map<string, SortColumn<Move>> = new Map(
  MOVE_COLUMNS.map((column) => [column.key as string, column]),
);
