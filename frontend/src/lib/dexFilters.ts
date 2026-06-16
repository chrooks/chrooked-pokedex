/* The dex's FieldRegistry: the entity-specific half of the shared filter engine
   for DexEntry. The boolean machinery (FilterEntry, NUMERIC_OPERATORS,
   appendNameFilter, evalGroup) lives in filterEngine.ts and is re-exported here
   for back-compat; this module only supplies the dex defs + value extraction and
   wraps the generic evaluators with dex-bound signatures the dex callers use. */

import type { DexEntry } from "../types";
import { STAT_ORDER, TYPES, bst, isEdited } from "./format";
import { COLUMNS } from "./dexColumns";
import { CLASS_VALUES, classesOf } from "./dexTags";
import type { ClassValue } from "./dexTags";
import {
  applyFilter as applyFilterGeneric,
  evalEntries as evalEntriesGeneric,
  type FieldRegistry,
  type FilterDef,
} from "./filterEngine";

export {
  appendNameFilter,
  NUMERIC_OPERATORS,
  type FilterDef,
  type FilterEntry,
  type NumericOperator,
} from "./filterEngine";
export type { FieldRegistry } from "./filterEngine";

/** The filterable fields, derived once. Numeric fields are derived straight from
    the column registry (every number column is filterable) so they can't drift
    from COLUMNS; Type and Class are derived (virtual) select fields. The
    `entries` arg is accepted for signature symmetry with data-derived value sets
    but the value sets here are static (TYPES, CLASS_VALUES). */
export function buildFilterDefs(_entries: DexEntry[]): FilterDef[] {
  const numericDefs: FilterDef[] = COLUMNS.filter(
    (column) => column.cellType === "number",
  ).map((column) => ({
    field: column.key,
    label: column.label,
    method: "numeric",
  }));
  return [
    ...numericDefs,
    { field: "type", label: "Type", method: "select", values: [...TYPES] },
    { field: "class", label: "Class", method: "select", values: [...CLASS_VALUES] },
    {
      field: "edited",
      label: "Edited",
      method: "select",
      values: ["Edited", "Not edited"],
    },
    { field: "name", label: "Name", method: "text" },
    { field: "abilities", label: "Abilities", method: "text" },
    { field: "moves", label: "Moves", method: "text" },
  ];
}

const STAT_FIELDS = new Set<string>(STAT_ORDER);

function numericValue(field: string, entry: DexEntry): number | undefined {
  if (field === "dex") {
    return entry.dex ?? undefined;
  }
  if (field === "bst") {
    return bst(entry.stats);
  }
  // Only the six stat keys read from entry.stats; any other field fails safe so
  // a future numeric column without a stats backing never silently matches.
  return STAT_FIELDS.has(field) ? entry.stats[field] : undefined;
}

function abilityText(entry: DexEntry): string {
  const { primary, secondary, hidden } = entry.abilities;
  return [primary, secondary, hidden].filter(Boolean).join(" ");
}

function learnsetText(entry: DexEntry): string {
  return entry.learnset.map((e) => e.move).join(" ");
}

function selectMatch(field: string, entry: DexEntry, value: string): boolean {
  if (field === "type") {
    return entry.types.includes(value); // array-contains: Fire matches Fire/Water
  }
  if (field === "class") {
    return classesOf(entry).includes(value as ClassValue);
  }
  if (field === "edited") {
    return value === "Edited" ? isEdited(entry) : !isEdited(entry);
  }
  return false;
}

function textHaystack(field: string, entry: DexEntry): string {
  if (field === "name") {
    return entry.name;
  }
  if (field === "moves") {
    return learnsetText(entry);
  }
  return abilityText(entry);
}

/** The dex registry: the DexEntry binding of the shared filter engine. */
export const DEX_REGISTRY: FieldRegistry<DexEntry> = {
  defs: buildFilterDefs([]),
  numericValue,
  selectMatch,
  textHaystack,
};

/** Evaluate a single predicate against one dex entry. Dex-bound wrapper over the
    generic evaluator so existing dex callers keep the `(def, entry, value)`
    signature. */
export function applyFilter(
  def: FilterDef,
  entry: DexEntry,
  value: string,
): boolean {
  return applyFilterGeneric(DEX_REGISTRY, def, entry, value);
}

/** True when `entry` satisfies the whole filter expression. Dex-bound wrapper
    over the generic evaluator (keeps the `(entry, entries)` signature). */
export function evalEntries(
  entry: DexEntry,
  entries: Parameters<typeof evalEntriesGeneric<DexEntry>>[2],
): boolean {
  return evalEntriesGeneric(DEX_REGISTRY, entry, entries);
}
