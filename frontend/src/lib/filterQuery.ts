/* The command-bar grammar: a text form of the SAME FilterEntry[] the query line
   builds. Parse and format are inverses, so switching between the two modes is
   a re-render, never a conversion that can lose a term.

     name:fros -class:mega bst>=500
     type:grass or weakto:fire
     ( class:starter or class:legendary ) bst>=540

   Shape of a term:  ["-"] key (":" | ">=" | "<=" | ">" | "<" | "=") value
   `-` excludes (the model's `negated`). Bare `or` sets the next term's
   connector; bare `(` / `)` become paren entries. Everything is
   case-insensitive on input and normalized to the registry's canonical casing
   on the way in, so `class:MEGA` and `class:mega` both store "Mega".

   Keys come from the FilterDef registry, never a hardcoded list, so a new
   filterable field is spellable here the day it is added. A def carrying
   relation `operators` (the dex Type field) contributes one key per operator —
   `type:` for the default plus `weak:`, `resists:`, `se:` and friends — which
   reads far better than packing the relation into the value.

   Pure, no React, no DOM. Unit-tested in filterQuery.test.ts. */

import type { FilterDef, FilterEntry, NumericOperator } from "./filterEngine";

/** ASCII spellings accepted for the model's numeric operators, longest first so
    ">=" is matched before ">". The model stores the typographic forms. */
const OPERATOR_SPELLINGS: [string, NumericOperator][] = [
  [">=", "≥"],
  ["<=", "≤"],
  ["≥", "≥"],
  ["≤", "≤"],
  [">", ">"],
  ["<", "<"],
  ["=", "="],
];

/** The ASCII spelling used when formatting, so a query is copy-pasteable and
    typeable on any keyboard. */
const OPERATOR_TEXT: Record<string, string> = { "≥": ">=", "≤": "<=" };

/** One spellable key: the token a human types, and what it resolves to. */
export type QueryKey = {
  /** The typed token, e.g. "bst", "class", "weak". */
  key: string;
  def: FilterDef;
  /** For a def with relation operators, which operator this key selects. */
  operator?: string;
  /** Menu hint: what may follow the key. */
  hint: string;
  /** An example of the whole term, for the suggestion list. */
  example: string;
};

/** Suggestion ordering: text, then categories, then numbers. A stable sort keeps
    registry order inside each band. */
function methodRank(key: QueryKey): number {
  if (key.def.method === "text") return 0;
  if (key.def.method === "numeric") return 2;
  return 1;
}

/** Every key spellable for one entity, in registry order. */
export function queryKeys(defs: FilterDef[]): QueryKey[] {
  const keys: QueryKey[] = [];
  for (const def of defs) {
    if (def.method === "numeric") {
      keys.push({ key: def.field, def, hint: "number", example: `${def.field}>=100` });
      continue;
    }
    if (def.method === "text") {
      keys.push({ key: def.field, def, hint: "text", example: `${def.field}:fros` });
      continue;
    }
    const sample = (def.values?.[0] ?? "value").toLowerCase();
    if (def.method === "selectnum") {
      keys.push({
        key: def.field,
        def,
        hint: `${def.values?.length ?? 0} kinds, optional number`,
        example: `${def.field}:${sample}`,
      });
      continue;
    }
    // select — with relation operators, each operator is its own key.
    if (!def.operators || def.operators.length === 0) {
      keys.push({
        key: def.field,
        def,
        hint: `${def.values?.length ?? 0} values`,
        example: `${def.field}:${sample}`,
      });
      continue;
    }
    const [first, ...rest] = def.operators;
    keys.push({
      key: def.field,
      def,
      operator: first.op,
      hint: first.label,
      example: `${def.field}:${sample}`,
    });
    for (const op of rest) {
      keys.push({
        key: op.op,
        def,
        operator: op.op,
        hint: op.label,
        example: `${op.op}:${sample}`,
      });
    }
  }
  return keys;
}

/** Split a query into terms, keeping a "quoted phrase" as one term. Trailing
    whitespace matters to the caller (it means "the last term is finished"), so
    the raw text is tokenized rather than naively split. */
export function tokenize(raw: string): string[] {
  const out: string[] = [];
  let current = "";
  let quoted = false;
  for (const ch of raw) {
    if (ch === '"') {
      quoted = !quoted;
      current += ch;
      continue;
    }
    if (!quoted && /\s/.test(ch)) {
      if (current !== "") out.push(current);
      current = "";
      continue;
    }
    current += ch;
  }
  if (current !== "") out.push(current);
  return out;
}

/** Strip surrounding quotes from a value. */
function unquote(value: string): string {
  return value.length >= 2 && value.startsWith('"') && value.endsWith('"')
    ? value.slice(1, -1)
    : value;
}

/** Quote a value that would otherwise tokenize as two terms. */
function quote(value: string): string {
  return /[\s"]/.test(value) ? `"${value.replace(/"/g, "")}"` : value;
}

/** Match a typed value against a def's canonical values, case-insensitively.
    Returns the canonical spelling, or undefined when the value is not offered. */
function canonicalValue(def: FilterDef, typed: string): string | undefined {
  return def.values?.find((v) => v.toLowerCase() === typed.toLowerCase());
}

/** One parsed term: either a resolved entry, or the reason it could not resolve
    so the bar can mark it rather than silently dropping it. */
export type ParsedTerm =
  | { ok: true; entry: Omit<Extract<FilterEntry, { kind: "filter" }>, "id" | "connector"> }
  | { ok: true; paren: "(" | ")" }
  | { ok: false; text: string; reason: string };

/** Parse one term in isolation. `or` and parens are handled by the caller. */
export function parseTerm(term: string, defs: FilterDef[]): ParsedTerm {
  const negated = term.startsWith("-");
  const body = negated ? term.slice(1) : term;

  // Find the separator: a numeric operator or a colon, whichever comes first.
  let sepIndex = -1;
  let sepText = "";
  for (const [spelling] of OPERATOR_SPELLINGS) {
    const at = body.indexOf(spelling);
    if (at > 0 && (sepIndex === -1 || at < sepIndex)) {
      sepIndex = at;
      sepText = spelling;
    }
  }
  const colon = body.indexOf(":");
  if (colon > 0 && (sepIndex === -1 || colon < sepIndex)) {
    sepIndex = colon;
    sepText = ":";
  }
  if (sepIndex === -1) {
    return { ok: false, text: term, reason: `"${body}" needs a value — try ${body}:something` };
  }

  const typedKey = body.slice(0, sepIndex).toLowerCase();
  const rawValue = unquote(body.slice(sepIndex + sepText.length));
  const match = queryKeys(defs).find((k) => k.key.toLowerCase() === typedKey);
  if (!match) return { ok: false, text: term, reason: `no field called "${typedKey}"` };
  if (rawValue === "") return { ok: false, text: term, reason: `${typedKey} needs a value` };

  const { def, operator } = match;

  if (def.method === "numeric") {
    const op = OPERATOR_SPELLINGS.find(([spelling]) => spelling === sepText)?.[1];
    if (!op) return { ok: false, text: term, reason: `${typedKey} compares numbers — use >=, >, =, <, <=` };
    if (Number.isNaN(Number(rawValue))) {
      return { ok: false, text: term, reason: `"${rawValue}" is not a number` };
    }
    return { ok: true, entry: { kind: "filter", field: def.field, value: `${op}|${rawValue}`, negated } };
  }

  if (def.method === "text") {
    return { ok: true, entry: { kind: "filter", field: def.field, value: rawValue, negated } };
  }

  if (def.method === "selectnum") {
    // "level>=45" — the choice, then an optional numeric clause.
    let choiceText = rawValue;
    let clauseOp: NumericOperator | null = null;
    let clauseNum = "";
    for (const [spelling, op] of OPERATOR_SPELLINGS) {
      const at = rawValue.indexOf(spelling);
      if (at > 0) {
        choiceText = rawValue.slice(0, at);
        clauseOp = op;
        clauseNum = rawValue.slice(at + spelling.length);
        break;
      }
    }
    const choice = canonicalValue(def, choiceText);
    if (!choice) {
      return { ok: false, text: term, reason: `${typedKey} has no kind "${choiceText}"` };
    }
    const wantsNumber = def.numericValues?.includes(choice) ?? false;
    if (clauseOp && wantsNumber && clauseNum !== "" && !Number.isNaN(Number(clauseNum))) {
      return {
        ok: true,
        entry: { kind: "filter", field: def.field, value: `${choice}|${clauseOp}|${clauseNum}`, negated },
      };
    }
    return { ok: true, entry: { kind: "filter", field: def.field, value: choice, negated } };
  }

  // select
  const choice = canonicalValue(def, rawValue);
  if (!choice) return { ok: false, text: term, reason: `${typedKey} has no value "${rawValue}"` };
  const value = def.operators ? `${operator ?? def.operators[0].op}|${choice}` : choice;
  return { ok: true, entry: { kind: "filter", field: def.field, value, negated } };
}

export type ParseResult = {
  entries: FilterEntry[];
  /** Terms that could not resolve, in the order typed. */
  problems: { text: string; reason: string }[];
};

/**
 * Parse a whole query into entries. `newId` is injected so the function stays
 * deterministic and testable. Unresolvable terms are reported, never guessed at
 * and never silently dropped — the bar marks them and the filter simply does
 * not include them.
 */
export function parseQuery(
  raw: string,
  defs: FilterDef[],
  newId: () => string,
): ParseResult {
  const entries: FilterEntry[] = [];
  const problems: { text: string; reason: string }[] = [];
  // The connector applies to the NEXT entry added, matching the model's
  // "each entry carries the connector joining it to the one before".
  let connector: "AND" | "OR" = "AND";

  for (const term of tokenize(raw)) {
    const lower = term.toLowerCase();
    if (lower === "or") {
      connector = "OR";
      continue;
    }
    if (lower === "and") {
      connector = "AND";
      continue;
    }
    if (term === "(" || term === ")") {
      entries.push({ kind: "paren", id: newId(), paren: term, connector });
      connector = "AND";
      continue;
    }
    const parsed = parseTerm(term, defs);
    if (!parsed.ok) {
      problems.push({ text: parsed.text, reason: parsed.reason });
      continue;
    }
    if ("paren" in parsed) continue;
    entries.push({ ...parsed.entry, id: newId(), connector });
    connector = "AND";
  }
  return { entries, problems };
}

/** Format one entry back to its term text (without its connector). */
export function formatEntry(entry: FilterEntry, defs: FilterDef[]): string {
  if (entry.kind === "paren") return entry.paren;
  const def = defs.find((d) => d.field === entry.field);
  if (!def) return "";
  const not = entry.negated ? "-" : "";

  if (def.method === "numeric") {
    const [op, num] = entry.value.split("|");
    return `${not}${def.field}${OPERATOR_TEXT[op] ?? op}${num}`;
  }
  if (def.method === "text") {
    return `${not}${def.field}:${quote(entry.value)}`;
  }
  if (def.method === "selectnum") {
    const [choice, op, num] = entry.value.split("|");
    const clause = op && num ? `${OPERATOR_TEXT[op] ?? op}${num}` : "";
    return `${not}${def.field}:${quote(choice.toLowerCase())}${clause}`;
  }
  // select
  if (!def.operators) return `${not}${def.field}:${quote(entry.value.toLowerCase())}`;
  const bar = entry.value.indexOf("|");
  const op = bar === -1 ? def.operators[0].op : entry.value.slice(0, bar);
  const choice = bar === -1 ? entry.value : entry.value.slice(bar + 1);
  const key = op === def.operators[0].op ? def.field : op;
  return `${not}${key}:${quote(choice.toLowerCase())}`;
}

/** Format a whole filter back to query text. The inverse of parseQuery. */
export function formatQuery(filter: FilterEntry[], defs: FilterDef[]): string {
  const parts: string[] = [];
  filter.forEach((entry, index) => {
    if (index > 0 && entry.connector === "OR") parts.push("or");
    const text = formatEntry(entry, defs);
    if (text !== "") parts.push(text);
  });
  return parts.join(" ");
}

/** One autocomplete row. `complete` is the text that replaces the partial term;
    a trailing space means the term is finished. */
export type Suggestion = {
  /** What the row shows in mono. */
  code: string;
  /** What the row explains. */
  hint: string;
  complete: string;
};

/**
 * Rank completions for the term currently under the caret. Before a separator
 * we complete keys; after one we complete that key's values. A key with free
 * values (text, numbers) has nothing to offer but its own shape, which is still
 * worth showing so the grammar never has to be memorized.
 */
export function suggest(partial: string, defs: FilterDef[]): Suggestion[] {
  const keys = queryKeys(defs);
  const negated = partial.startsWith("-");
  const body = negated ? partial.slice(1) : partial;
  const not = negated ? "-" : "";

  // Find a separator, as parseTerm does.
  let sepIndex = -1;
  let sepText = "";
  for (const [spelling] of OPERATOR_SPELLINGS) {
    const at = body.indexOf(spelling);
    if (at > 0 && (sepIndex === -1 || at < sepIndex)) {
      sepIndex = at;
      sepText = spelling;
    }
  }
  const colon = body.indexOf(":");
  if (colon > 0 && (sepIndex === -1 || colon < sepIndex)) {
    sepIndex = colon;
    sepText = ":";
  }

  if (sepIndex === -1) {
    const frag = body.toLowerCase();
    const rows: Suggestion[] = keys
      .filter((k) => k.key.toLowerCase().startsWith(frag))
      // Rank the way the field menu groups: what you reach for first, first.
      // The registry's own order leads with the stat columns, which would bury
      // `name` past the cut on an empty caret.
      .sort((a, b) => methodRank(a) - methodRank(b))
      .map((k) => ({
        code: not + k.example,
        hint: `${k.def.label} · ${k.hint}`,
        complete: `${not}${k.key}${k.def.method === "numeric" ? ">=" : ":"}`,
      }));
    // `or` and grouping are part of the grammar; offer them once typing starts.
    if ("or".startsWith(frag) && frag !== "") {
      rows.push({ code: "or", hint: "join the next term with OR", complete: "or " });
    }
    return rows;
  }

  const typedKey = body.slice(0, sepIndex).toLowerCase();
  const frag = unquote(body.slice(sepIndex + sepText.length)).toLowerCase();
  const match = keys.find((k) => k.key.toLowerCase() === typedKey);
  if (!match) return [];
  const { def } = match;

  if (def.method === "numeric") {
    return [
      {
        code: `${not}${typedKey}${sepText}${frag || "…"}`,
        hint: frag === "" ? "type a number" : `${def.label} ${sepText} ${frag}`,
        complete: frag === "" ? partial : `${partial} `,
      },
    ];
  }
  if (def.method === "text") {
    return [
      {
        code: `${not}${typedKey}:${frag || "…"}`,
        hint: frag === "" ? "type any text" : `${def.label} contains "${frag}"`,
        complete: frag === "" ? partial : `${partial} `,
      },
    ];
  }

  // select / selectnum — complete the value list.
  const values = def.values ?? [];
  return values
    .filter((v) => v.toLowerCase().startsWith(frag))
    .map((v) => ({
      code: `${not}${typedKey}:${quote(v.toLowerCase())}`,
      hint:
        def.method === "selectnum" && (def.numericValues?.includes(v) ?? false)
          ? `${def.label} — accepts a number, e.g. ${typedKey}:${v.toLowerCase()}>=45`
          : def.label,
      complete: `${not}${typedKey}:${quote(v.toLowerCase())} `,
    }));
}
