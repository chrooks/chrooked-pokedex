/* Pure seed/serialize logic for the species editor's evolution method form.
   Kept framework-free so it's testable without rendering.

   The form is a discriminated union over a method *kind*:
     - Level → a number param → serializes to { level: <int> }
     - Item  → an item internal name → { item: "<string>" }
     - Other → a compact raw key/value row for the ~40 long-tail engine methods,
               preserving the engine-hint fallback shape
               { essentials|pokeemerald: <token>, param?: <value> }.

   evolution.method has TWO runtime shapes (see types.ts Evolution):
     1. an Override dict ({ level: 54 }, { item: "FIRESTONE" }, ...), or
     2. a backdrop display STRING ("Level 36") with structured data alongside in
        method_detail ({ kind: "Level", param: "36" }).
   A string must NEVER be char-split — the read view already guards with
   `typeof method === "object"`; this mirrors that discipline. */

import type { Evolution } from "../../types";
import { rowId } from "../../lib/rowId";

export type MethodKind = "level" | "item" | "other";

/** A raw key/value row for the Other kind (the existing mechanism). */
export type MethodRow = { _id: number; key: string; value: string };

/** The seeded form state: the chosen kind, the single param (Level/Item), and
    the raw rows (Other). Only the field for the active kind is meaningful. */
export type MethodForm = {
  kind: MethodKind;
  /** Param for Level (the number, as a string) and Item (the internal name). */
  param: string;
  /** Raw key/value rows for the Other kind. */
  rows: MethodRow[];
};

/** Number coercion shared with the editor: a clean integer stays a number. */
export function parseMethodValue(value: string): number | string {
  const trimmed = value.trim();
  return /^-?\d+$/.test(trimmed) ? Number(trimmed) : trimmed;
}

/** Normalize a method_detail `kind` token (display or raw engine) to a kind.
    "Level"/"EVO_LEVEL" → level; "Item"/"EVO_ITEM" → item; else → other. */
function kindFromToken(token: string): MethodKind {
  const t = token.trim().toLowerCase();
  if (t === "level" || t === "evo_level") return "level";
  if (t === "item" || t === "evo_item") return "item";
  return "other";
}

/** An empty Other form carrying one blank row to type into. */
function emptyOther(): MethodForm {
  return { kind: "other", param: "", rows: [{ _id: rowId(), key: "", value: "" }] };
}

/** Seed the form from a method dict (the Override shape). */
function seedFromDict(method: Record<string, unknown>): MethodForm {
  if ("level" in method) {
    return { kind: "level", param: String(method.level), rows: [emptyRow()] };
  }
  if ("item" in method) {
    return { kind: "item", param: String(method.item), rows: [emptyRow()] };
  }
  // Other: carry every pair as a raw row (never char-split — this is an object).
  const rows = Object.entries(method).map(([key, value]) => ({
    _id: rowId(),
    key,
    value: String(value),
  }));
  return {
    kind: "other",
    param: "",
    rows: rows.length > 0 ? rows : [emptyRow()],
  };
}

/** Seed the form from the backdrop display string, using method_detail. */
function seedFromString(detail: Evolution["method_detail"]): MethodForm {
  // No structured detail to lean on: fall back to Other, never char-split.
  if (detail === undefined || detail === null) return emptyOther();

  const kind = kindFromToken(detail.kind);
  if (kind === "level" || kind === "item") {
    return { kind, param: detail.param ?? "", rows: [emptyRow()] };
  }
  // Other: carry the raw engine token + param as one row.
  return {
    kind: "other",
    param: "",
    rows: [{ _id: rowId(), key: detail.kind, value: detail.param ?? "" }],
  };
}

function emptyRow(): MethodRow {
  return { _id: rowId(), key: "", value: "" };
}

/** Seed the editor's method form from an Evolution (handles BOTH method shapes,
    or null for "no evolution Override"). */
export function seedMethodForm(evolution: Evolution | null): MethodForm {
  if (evolution === null) return emptyOther();
  const { method } = evolution;
  if (typeof method === "object" && method !== null) {
    return seedFromDict(method as Record<string, unknown>);
  }
  // method is a string (or absent): use method_detail, never char-split.
  return seedFromString(evolution.method_detail);
}

/** Serialize the form back to a clean Override method dict. */
export function serializeMethod(form: MethodForm): Record<string, number | string> {
  if (form.kind === "level") {
    const n = Number(form.param);
    return Number.isFinite(n) && form.param.trim() !== "" ? { level: n } : {};
  }
  if (form.kind === "item") {
    const item = form.param.trim();
    return item !== "" ? { item } : {};
  }
  // Other: every non-blank-key row, with the existing numeric coercion.
  const out: Record<string, number | string> = {};
  for (const row of form.rows) {
    const key = row.key.trim();
    if (key !== "") out[key] = parseMethodValue(row.value);
  }
  return out;
}
