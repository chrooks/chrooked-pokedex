/* The entity-generic filter engine. This is the single source of truth for the
   boolean machinery the dex, moves, and abilities tabs all share: a per-field
   descriptor set (FilterDef), a single-predicate evaluator (applyFilter), and a
   recursive boolean evaluator (evalEntries) over a flat list of pills with
   AND/OR connectors, NOT negation, and parenthesis grouping. OR binds looser
   than AND.

   The only entity-specific knowledge lives behind a FieldRegistry<T> seam: each
   surface supplies the defs plus the value-extraction half (numericValue /
   selectMatch / textHaystack). The boolean structure here never touches T. Pure,
   no React. */

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
  /** `selectnum` is a select narrowed by an OPTIONAL numeric clause — pick a
      category first, then (when it makes sense) constrain its number. */
  method: "numeric" | "select" | "text" | "selectnum";
  /** Allowed values for a `select` / `selectnum` field. */
  values?: string[];
  /** `selectnum` only: the values whose numeric clause is offered. Others are
      category-only. */
  numericValues?: string[];
  /** `select` only: an optional relation-operator menu shown before the value
      (e.g. the dex Type field's is / weak to / SE against). When present, a pill
      stores `"<op>|<value>"`; the registry's selectMatch owns interpreting it. */
  operators?: { op: string; label: string }[];
}

/** The seam that makes the engine entity-generic. A registry bundles the field
    descriptors with the value-extraction half of the evaluator for one entity
    type. The boolean machinery (evalEntries / evalGroup) is registry-fed and
    never imports a concrete entity type. */
export interface FieldRegistry<T> {
  defs: FilterDef[];
  /** The numeric cell for a numeric field, or undefined when absent/invalid. */
  numericValue(field: string, item: T): number | undefined;
  /** Whether a select field matches the chosen value. */
  selectMatch(field: string, item: T, value: string): boolean;
  /** The text a text field searches over (raw, un-normalized). */
  textHaystack(field: string, item: T): string;
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
    passed in so the function stays deterministic and testable. The Name field is
    `name` across every registry, so this idiom is shared verbatim. */
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
export function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

/** A leaf that constrains nothing: an unknown field, or a text pill with an
    empty value. Such leaves pass every item AND every item's negation, so the
    evaluator treats them as no-ops rather than letting `negated` invert them. */
export function isInert(def: FilterDef | undefined, value: string): boolean {
  if (!def) {
    return true;
  }
  return def.method === "text" && value === "";
}

/** Evaluate a single predicate against one item via the registry. A missing/
    invalid value or an unparseable numeric threshold fails the predicate (never
    throws). */
export function applyFilter<T>(
  registry: FieldRegistry<T>,
  def: FilterDef,
  item: T,
  value: string,
): boolean {
  if (def.method === "numeric") {
    const [op, numberPart] = value.split("|");
    const threshold = Number(numberPart);
    const cell = registry.numericValue(def.field, item);
    if (cell === undefined || Number.isNaN(threshold)) {
      return false;
    }
    return compareNumeric(cell, op, threshold);
  }

  if (def.method === "select") {
    return registry.selectMatch(def.field, item, value);
  }

  // selectnum — "Level|≥|30" (category plus clause) or "Level" (category only).
  if (def.method === "selectnum") {
    const [selected, op, numberPart] = value.split("|");
    if (!registry.selectMatch(def.field, item, selected)) {
      return false;
    }
    if (op === undefined || numberPart === undefined || numberPart === "") {
      return true;
    }
    const threshold = Number(numberPart);
    const cell = registry.numericValue(def.field, item);
    if (cell === undefined || Number.isNaN(threshold)) {
      return false;
    }
    return compareNumeric(cell, op, threshold);
  }

  // text — an empty pill filters nothing.
  if (value === "") {
    return true;
  }
  return normalize(registry.textHaystack(def.field, item)).includes(
    normalize(value),
  );
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

/** True when `item` satisfies the whole filter expression under `registry`. An
    empty list passes everything. Unknown fields are treated as neutral (always
    true). */
export function evalEntries<T>(
  registry: FieldRegistry<T>,
  item: T,
  entries: FilterEntry[],
): boolean {
  if (entries.length === 0) {
    return true;
  }

  const defByField = new Map(registry.defs.map((def) => [def.field, def] as const));
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
      const def = defByField.get(leaf.field);
      nodes.push({
        connector: leaf.connector,
        evaluate: () => {
          // An inert leaf (e.g. an empty text value) filters nothing — it must
          // stay a no-op even when negated. Otherwise `NOT <empty>` flips the
          // "matches everything" pass into "matches nothing".
          if (isInert(def, leaf.value)) {
            return true;
          }
          const passes = def ? applyFilter(registry, def, item, leaf.value) : true;
          return leaf.negated ? !passes : passes;
        },
      });
      position += 1;
    }
    return nodes;
  }

  return evalGroup(parseGroup(true));
}
