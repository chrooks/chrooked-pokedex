/* The filter model: a per-field descriptor set (FilterDef), a single-predicate
   evaluator (applyFilter), and a recursive boolean evaluator (evalEntries) over
   a flat list of pills with AND/OR connectors, NOT negation, and parenthesis
   grouping. OR binds looser than AND. Pure, no React. */

import type { DexEntry } from "../types";
import { STAT_ORDER, TYPES, bst, isEdited } from "./format";
import { COLUMNS } from "./dexColumns";
import { CLASS_VALUES, classesOf } from "./dexTags";
import type { ClassValue } from "./dexTags";

/** One pill in the builder: a leaf predicate or a parenthesis token. Each
    non-first entry carries the connector that joins it to the entry before. */
export type FilterEntry =
  | {
      kind: "filter";
      id: string;
      field: string;
      /** For numeric fields, "op|number" (e.g. "≥|100"); otherwise the raw
          select value or text substring. */
      value: string;
      connector: "AND" | "OR";
      negated: boolean;
    }
  | {
      kind: "paren";
      id: string;
      paren: "(" | ")";
      connector: "AND" | "OR";
    };

export interface FilterDef {
  field: string;
  label: string;
  method: "numeric" | "select" | "text";
  /** Allowed values for a `select` field. */
  values?: string[];
}

/** The numeric comparison operators, in menu order. */
export const NUMERIC_OPERATORS = ["≥", "≤", "=", ">", "<"] as const;
export type NumericOperator = (typeof NUMERIC_OPERATORS)[number];

/** The builder caps at 10 filter pills (matches the codec). */
const MAX_FILTERS = 10;

/** Promote a search term to a Name filter pill: append a `Name: <query>` pill to
    the filter tree. Returns the SAME array reference (no change) when the query is
    blank, the pill cap is reached, or an identical Name pill already exists — the
    caller uses that to decide whether to clear the search box. Pure; `id` is
    passed in so the function stays deterministic and testable. */
export function appendNameFilter(
  filter: FilterEntry[],
  query: string,
  id: string,
): FilterEntry[] {
  const trimmed = query.trim();
  if (trimmed === "") return filter;
  const filterCount = filter.filter((e) => e.kind === "filter").length;
  if (filterCount >= MAX_FILTERS) return filter;
  const duplicate = filter.some(
    (e) =>
      e.kind === "filter" &&
      e.field === "name" &&
      e.value.toLowerCase() === trimmed.toLowerCase(),
  );
  if (duplicate) return filter;
  return [
    ...filter,
    { kind: "filter", id, field: "name", value: trimmed, connector: "AND", negated: false },
  ];
}

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

/** Defs keyed by field, built once at module load (pure + static), so the
    per-row evaluator never re-derives them. */
const DEF_BY_FIELD = new Map(
  buildFilterDefs([]).map((def) => [def.field, def] as const),
);

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

function compareNumeric(cell: number, op: string, threshold: number): boolean {
  switch (op) {
    case "≥":
      return cell >= threshold;
    case "≤":
      return cell <= threshold;
    case "=":
      return cell === threshold;
    case ">":
      return cell > threshold;
    case "<":
      return cell < threshold;
    default:
      return false;
  }
}

/** Strip diacritics and lowercase, so "Flabébé" matches "flabebe". */
function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function abilityText(entry: DexEntry): string {
  const { primary, secondary, hidden } = entry.abilities;
  return [primary, secondary, hidden].filter(Boolean).join(" ");
}

function learnsetText(entry: DexEntry): string {
  return entry.learnset.map((e) => e.move).join(" ");
}

/** Evaluate a single predicate against one entry. A missing/invalid value or an
    unparseable numeric threshold fails the predicate (never throws). */
export function applyFilter(
  def: FilterDef,
  entry: DexEntry,
  value: string,
): boolean {
  if (def.method === "numeric") {
    const [op, numberPart] = value.split("|");
    const threshold = Number(numberPart);
    const cell = numericValue(def.field, entry);
    if (cell === undefined || Number.isNaN(threshold)) {
      return false;
    }
    return compareNumeric(cell, op, threshold);
  }

  if (def.method === "select") {
    if (def.field === "type") {
      return entry.types.includes(value); // array-contains: Fire matches Fire/Water
    }
    if (def.field === "class") {
      return classesOf(entry).includes(value as ClassValue);
    }
    if (def.field === "edited") {
      return value === "Edited" ? isEdited(entry) : !isEdited(entry);
    }
    return false;
  }

  // text
  if (value === "") {
    return true;
  }
  let haystack: string;
  if (def.field === "name") {
    haystack = entry.name;
  } else if (def.field === "moves") {
    haystack = learnsetText(entry);
  } else {
    haystack = abilityText(entry);
  }
  return normalize(haystack).includes(normalize(value));
}

// --- Recursive boolean evaluator -------------------------------------------

interface EvalNode {
  connector: "AND" | "OR";
  evaluate: () => boolean;
}

/** Evaluate one group of nodes honoring AND-over-OR precedence: split into
    OR-separated runs, AND within each run, then OR the runs together. The first
    node's connector is ignored (nothing precedes it). Empty group passes. */
function evalGroup(nodes: EvalNode[]): boolean {
  if (nodes.length === 0) {
    return true;
  }
  let orResult = false;
  let andRun = nodes[0].evaluate();
  for (let index = 1; index < nodes.length; index += 1) {
    const node = nodes[index];
    const value = node.evaluate();
    if (node.connector === "OR") {
      orResult = orResult || andRun;
      andRun = value;
    } else {
      andRun = andRun && value;
    }
  }
  return orResult || andRun;
}

/** True when `entry` satisfies the whole filter expression. An empty list
    passes everything. Unknown fields are treated as neutral (always true). */
export function evalEntries(entry: DexEntry, entries: FilterEntry[]): boolean {
  if (entries.length === 0) {
    return true;
  }

  let position = 0;

  // `isRoot` distinguishes the top-level call from a recursive paren group: a
  // stray ")" at the root (possible from a hand-mangled URL) is consumed and
  // skipped rather than ending the whole expression early.
  function parseGroup(isRoot: boolean): EvalNode[] {
    const nodes: EvalNode[] = [];
    while (position < entries.length) {
      const current = entries[position];
      if (current.kind === "paren" && current.paren === ")") {
        position += 1; // consume the closer
        if (isRoot) {
          continue; // unmatched at root — ignore, keep scanning
        }
        break;
      }
      if (current.kind === "paren" && current.paren === "(") {
        const { connector } = current;
        position += 1; // consume the opener
        const inner = parseGroup(false);
        nodes.push({ connector, evaluate: () => evalGroup(inner) });
        continue;
      }
      // a filter leaf — defer applyFilter to evaluation time so the closure
      // captures the leaf, not a precomputed value (refactor-safe).
      const leaf = current as Extract<FilterEntry, { kind: "filter" }>;
      const def = DEF_BY_FIELD.get(leaf.field);
      nodes.push({
        connector: leaf.connector,
        evaluate: () => {
          const passes = def ? applyFilter(def, entry, leaf.value) : true;
          return leaf.negated ? !passes : passes;
        },
      });
      position += 1;
    }
    return nodes;
  }

  return evalGroup(parseGroup(true));
}
