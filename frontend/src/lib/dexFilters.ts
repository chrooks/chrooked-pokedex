/* The dex's FieldRegistry: the entity-specific half of the shared filter engine
   for DexEntry. The boolean machinery (FilterEntry, NUMERIC_OPERATORS,
   appendNameFilter, evalGroup) lives in filterEngine.ts and is re-exported here
   for back-compat; this module only supplies the dex defs + value extraction and
   wraps the generic evaluators with dex-bound signatures the dex callers use. */

import type { DexEntry, TypeChartCell } from "../types";
import { STAT_ORDER, TYPES, bst, isEdited } from "./format";
import { COLUMNS, EVO_KINDS, evoKind, evoLevel } from "./dexColumns";
import { CLASS_VALUES, classesOf } from "./dexTags";
import type { ClassValue } from "./dexTags";
import { memberDefense, memberOffense } from "./teamMatchups";
import { applyAbilityModifier } from "./abilityTypeModifiers";
import type { AbilitySlots } from "../types";
import {
  applyFilter as applyFilterGeneric,
  evalEntries as evalEntriesGeneric,
  type FieldRegistry,
  type FilterDef,
} from "./filterEngine";

/** The Type filter's relation operator. `is` is a plain membership test (no
    chart needed); the other six bucket the species against the active Ruleset
    type chart — three defensive (how the selected type hits this species) and
    three offensive (how this species' STAB hits the selected type). The `op`
    token is stored as a `"<op>|<type>"` value; a bare type (no pipe) is `is`. */
export const TYPE_OPERATORS = [
  { op: "is", label: "is" },
  { op: "weak", label: "is weak to" },
  { op: "resists", label: "is resistant to" },
  { op: "immune", label: "is immune to" },
  { op: "se", label: "is SE against" },
  { op: "nve", label: "is NVE against" },
  { op: "noeffect", label: "can't effect" },
] as const;

export type TypeOperator = (typeof TYPE_OPERATORS)[number]["op"];

/** Split a stored Type value into its operator + type. A bare type (no pipe,
    from an older URL) reads as the `is` membership test. */
export function parseTypeValue(value: string): { op: string; type: string } {
  const bar = value.indexOf("|");
  return bar === -1
    ? { op: "is", type: value }
    : { op: value.slice(0, bar), type: value.slice(bar + 1) };
}

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
    // Evolution is numeric for sorting (evo level) but filters as a method-kind
    // select with an optional level clause, so it gets its own def below.
    (column) => column.cellType === "number" && column.key !== "evolution",
  ).map((column) => ({
    field: column.key,
    label: column.label,
    method: "numeric",
  }));
  return [
    ...numericDefs,
    {
      field: "evolution",
      label: "Evolution",
      method: "selectnum",
      values: [...EVO_KINDS],
      numericValues: ["Level"],
    },
    {
      field: "type",
      label: "Type",
      method: "select",
      values: [...TYPES],
      operators: [...TYPE_OPERATORS],
    },
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
  if (field === "evolution") {
    return evoLevel(entry);
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

/** The species' distinct ability names (any slot), casing preserved. */
function abilityNames(abilities: AbilitySlots): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const name of [abilities.primary, abilities.secondary, abilities.hidden]) {
    if (name && !seen.has(name.toLowerCase())) {
      seen.add(name.toLowerCase());
      names.push(name);
    }
  }
  return names;
}

/** Match a Type pill against one species. `is` is the plain array-contains
    test; the matchup operators read the merged chart (`byKey`) via the same
    combined-defense / best-STAB-offense math the Team tab uses. Until the chart
    loads (`byKey` null) a matchup operator matches nothing — fail safe, never a
    false positive.

    Defensive operators fold in the species' abilities: a species matches when
    ANY ability it can hold produces that matchup. So a Levitate mon reads as
    immune to Ground, and a Dry Skin mon (Fire ×1.25) reads as weak to Fire even
    when its typing alone is neutral. Offense is unmodified — every ability in
    the modifier table is defensive. */
function typeMatch(
  entry: DexEntry,
  value: string,
  byKey: ReadonlyMap<string, TypeChartCell> | null,
): boolean {
  const { op, type } = parseTypeValue(value);
  if (op === "is") {
    return entry.types.includes(type); // Fire matches Fire/Water
  }
  if (!byKey) return false;
  const member = { id: entry.chrooked_id, name: entry.name, types: entry.types, ability: null };
  if (op === "weak" || op === "resists" || op === "immune") {
    const combined = memberDefense(member, type, byKey);
    if (combined === null) return false;
    // The set of multipliers the species can actually reach: one per ability it
    // can hold (an ability that doesn't touch this type leaves it unchanged). No
    // matchup-altering ability → just the base typing. Match if ANY qualifies —
    // so both immunities (Levitate → 0) and added weaknesses (Dry Skin → ×1.25)
    // surface, while a species whose only ability negates the matchup does not.
    const names = abilityNames(entry.abilities);
    const mults =
      names.length > 0
        ? names.map((name) => applyAbilityModifier(combined, type, name))
        : [combined];
    const qualifies = (mult: number) =>
      op === "weak" ? mult > 1 : op === "immune" ? mult === 0 : mult > 0 && mult < 1;
    return mults.some(qualifies);
  }
  if (op === "se" || op === "nve" || op === "noeffect") {
    const best = memberOffense(member, type, byKey);
    if (best === null) return false;
    if (op === "se") return best > 1;
    if (op === "noeffect") return best === 0;
    return best > 0 && best < 1; // NVE (excludes no-effect)
  }
  return false;
}

function makeSelectMatch(byKey: ReadonlyMap<string, TypeChartCell> | null) {
  return function selectMatch(field: string, entry: DexEntry, value: string): boolean {
    if (field === "type") {
      return typeMatch(entry, value, byKey);
    }
    if (field === "class") {
      return classesOf(entry).includes(value as ClassValue);
    }
    if (field === "evolution") {
      return evoKind(entry) === value;
    }
    if (field === "edited") {
      return value === "Edited" ? isEdited(entry) : !isEdited(entry);
    }
    return false;
  };
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

/** The dex registry: the DexEntry binding of the shared filter engine. The
    chartless default — its `selectMatch` handles `Type is …` but treats matchup
    operators as no-matches. The codec/defs and the single-predicate `applyFilter`
    wrapper read this; the live dex filter builds a chart-aware one via
    {@link dexRegistry}. */
export const DEX_REGISTRY: FieldRegistry<DexEntry> = {
  defs: buildFilterDefs([]),
  numericValue,
  selectMatch: makeSelectMatch(null),
  textHaystack,
};

// A chart-aware registry per chart map, cached by the map's identity so the
// per-entry filter pass reuses one registry instead of rebuilding it 1451×.
const registryCache = new WeakMap<object, FieldRegistry<DexEntry>>();

/** The dex registry bound to a merged type chart (`byKey`), so `Type weak to …`
    and friends can compute matchups. null → the chartless {@link DEX_REGISTRY}. */
export function dexRegistry(
  byKey: ReadonlyMap<string, TypeChartCell> | null,
): FieldRegistry<DexEntry> {
  if (!byKey) return DEX_REGISTRY;
  const cached = registryCache.get(byKey);
  if (cached) return cached;
  const registry: FieldRegistry<DexEntry> = {
    defs: DEX_REGISTRY.defs,
    numericValue,
    selectMatch: makeSelectMatch(byKey),
    textHaystack,
  };
  registryCache.set(byKey, registry);
  return registry;
}

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
    over the generic evaluator. Pass the merged chart's `byKey` map to enable the
    `Type weak to …` matchup operators; omit it for membership-only filtering. */
export function evalEntries(
  entry: DexEntry,
  entries: Parameters<typeof evalEntriesGeneric<DexEntry>>[2],
  byKey?: ReadonlyMap<string, TypeChartCell> | null,
): boolean {
  return evalEntriesGeneric(dexRegistry(byKey ?? null), entry, entries);
}
