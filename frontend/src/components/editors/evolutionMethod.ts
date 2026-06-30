/* Pure seed/serialize logic for the species editor's evolution method form.
   Kept framework-free so it's testable without rendering.

   The form is a canonical method id plus a single value, with a raw-engine-token
   escape for the long tail:
     - A canonical id from GET /api/meta/evolution-methods (level, item, trade,
       knows_move, ...). Its `value_kind` decides whether/what the value means.
     - id === ADVANCED_ID → the raw escape: an engine hint + token + param,
       writing { pokeemerald|essentials: <token>, param?: <value> } exactly.

   Storage stays additive: `level` and `item` keep their dedicated dict shapes
   ({ level: N } / { item: X }); every other canonical method stores as
   { method: <id>, param?: <value> }; the raw escape is unchanged.

   evolution.method has TWO runtime shapes (see types.ts Evolution):
     1. an Override dict ({ level: 54 }, { method: "trade" }, ...), or
     2. a backdrop display STRING ("Level 36") with structured data alongside in
        method_detail ({ kind: "EVO_LEVEL", param: "36" }).
   A string is NEVER char-split — the read view guards with typeof === "object";
   this mirrors that discipline. */

import type { CanonicalMethod, Evolution } from "../../types";

/** The sentinel method id for the raw engine-token escape hatch. */
export const ADVANCED_ID = "advanced";

export type MethodForm = {
  /** A canonical method id, or ADVANCED_ID for the raw escape. */
  id: string;
  /** The param for a canonical method (level number, item/move/map name). */
  value: string;
  /** Advanced escape: which engine hint key to write under. */
  rawEngine: "pokeemerald" | "essentials";
  /** Advanced escape: the raw engine method token (e.g. EVO_LEVEL_FOG). */
  rawToken: string;
  /** Advanced escape: the raw param (e.g. 35, MOVE_MIMIC). */
  rawParam: string;
};

/** A blank form defaulting to Level — the overwhelmingly common method. */
export function emptyMethodForm(): MethodForm {
  return { id: "level", value: "", rawEngine: "pokeemerald", rawToken: "", rawParam: "" };
}

/** Number coercion shared with the editor: a clean integer stays a number. */
export function parseMethodValue(value: string): number | string {
  const trimmed = value.trim();
  return /^-?\d+$/.test(trimmed) ? Number(trimmed) : trimmed;
}

function valueKind(
  id: string,
  methods: readonly CanonicalMethod[],
): CanonicalMethod["value_kind"] | null {
  return methods.find((m) => m.id === id)?.value_kind ?? null;
}

/** raw engine token (either family) → canonical id, from the fetched list. */
function tokenToId(methods: readonly CanonicalMethod[]): Map<string, string> {
  const map = new Map<string, string>();
  for (const m of methods) {
    map.set(m.tokens[0], m.id);
    map.set(m.tokens[1], m.id);
  }
  return map;
}

/** True when the form's selected method needs a Value the author hasn't filled:
    a canonical level/item/move/map method with a blank value, or the Advanced
    escape with a blank token. `none`-kind methods (Trade, Friendship) need none. */
export function requiredValueMissing(
  form: MethodForm,
  methods: readonly CanonicalMethod[],
): boolean {
  if (form.id === ADVANCED_ID) return form.rawToken.trim() === "";
  const kind = valueKind(form.id, methods);
  const needsValue = kind === "level" || kind === "item" || kind === "move" || kind === "map";
  return needsValue && form.value.trim() === "";
}

/** Seed the form from an Evolution (handles both method shapes, or null). */
export function seedMethodForm(
  evolution: Evolution | null,
  methods: readonly CanonicalMethod[],
): MethodForm {
  if (evolution === null) return emptyMethodForm();
  const { method } = evolution;
  if (typeof method === "object" && method !== null) {
    return seedFromDict(method as Record<string, unknown>, methods);
  }
  return seedFromDetail(evolution.method_detail, methods);
}

function seedFromDict(
  method: Record<string, unknown>,
  methods: readonly CanonicalMethod[],
): MethodForm {
  if ("level" in method) {
    return { ...emptyMethodForm(), id: "level", value: String(method.level) };
  }
  if ("item" in method) {
    return { ...emptyMethodForm(), id: "item", value: String(method.item) };
  }
  if ("method" in method && typeof method.method === "string") {
    const id = method.method;
    if (valueKind(id, methods) !== null) {
      return {
        ...emptyMethodForm(),
        id,
        value: "param" in method ? String(method.param) : "",
      };
    }
    // An unrecognized canonical id (older/newer ruleset) falls through to raw.
  }
  // Raw engine hint: { pokeemerald: EVO_X, param: Y } or { essentials: ... }.
  return seedAdvancedFromDict(method);
}

function seedAdvancedFromDict(method: Record<string, unknown>): MethodForm {
  const engine: MethodForm["rawEngine"] = "essentials" in method ? "essentials" : "pokeemerald";
  const token = engine in method ? String(method[engine]) : "";
  const param = "param" in method ? String(method.param) : "";
  return { id: ADVANCED_ID, value: "", rawEngine: engine, rawToken: token, rawParam: param };
}

function seedFromDetail(
  detail: Evolution["method_detail"],
  methods: readonly CanonicalMethod[],
): MethodForm {
  if (!detail) return emptyMethodForm();
  const id = tokenToId(methods).get(detail.kind);
  const kind = id ? valueKind(id, methods) : null;
  // Seed a canonical method only when its param can't be engine-mangled: `none`
  // (no param) and `level` (a clean integer). item/move/map params come back
  // engine-formatted in a backdrop detail, so route those to the raw escape to
  // preserve an exact round-trip; the user can pick the clean method to refine.
  if (id && (kind === "none" || kind === "level")) {
    return { ...emptyMethodForm(), id, value: kind === "level" ? detail.param : "" };
  }
  // The backdrop token's family: pokeemerald EVO_* constants are UPPER_SNAKE
  // with an EVO_ prefix; Essentials tokens (HasMove, LevelDay) are CamelCase.
  const rawEngine: MethodForm["rawEngine"] = detail.kind.startsWith("EVO_")
    ? "pokeemerald"
    : "essentials";
  return {
    id: ADVANCED_ID,
    value: "",
    rawEngine,
    rawToken: detail.kind,
    rawParam: detail.param,
  };
}

/** Serialize the form back to a clean Override method dict. */
export function serializeMethod(
  form: MethodForm,
  methods: readonly CanonicalMethod[],
): Record<string, number | string> {
  if (form.id === ADVANCED_ID) {
    const token = form.rawToken.trim();
    if (token === "") return {};
    const out: Record<string, number | string> = { [form.rawEngine]: token };
    const param = form.rawParam.trim();
    if (param !== "") out.param = parseMethodValue(param);
    return out;
  }
  if (form.id === "level") {
    const n = Number(form.value);
    return Number.isFinite(n) && form.value.trim() !== "" ? { level: n } : {};
  }
  if (form.id === "item") {
    const item = form.value.trim();
    return item !== "" ? { item } : {};
  }
  const kind = valueKind(form.id, methods);
  if (kind === "none") return { method: form.id };
  const value = form.value.trim();
  return value !== ""
    ? { method: form.id, param: parseMethodValue(value) }
    : { method: form.id };
}
