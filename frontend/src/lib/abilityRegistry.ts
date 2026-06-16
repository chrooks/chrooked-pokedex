/* The Abilities FieldRegistry: the Ability binding of the shared filter engine.
   Abilities have no numeric fields — just Edited (select) and Name/Description
   (text). The boolean machinery lives in filterEngine.ts. Pure, no React. */

import type { Ability } from "../types";
import { isAbilityEdited } from "./format";
import type { FieldRegistry, FilterDef } from "./filterEngine";
import type { SortColumn } from "./sortEngine";

/** The filterable ability fields. */
export function buildAbilityFilterDefs(): FilterDef[] {
  return [
    {
      field: "edited",
      label: "Edited",
      method: "select",
      values: ["Edited", "Not edited"],
    },
    { field: "name", label: "Name", method: "text" },
    { field: "description", label: "Description", method: "text" },
  ];
}

function numericValue(): number | undefined {
  return undefined;
}

function selectMatch(field: string, ability: Ability, value: string): boolean {
  if (field === "edited") {
    return value === "Edited" ? isAbilityEdited(ability) : !isAbilityEdited(ability);
  }
  return false;
}

function textHaystack(field: string, ability: Ability): string {
  if (field === "description") return ability.description;
  return ability.name;
}

export const ABILITY_REGISTRY: FieldRegistry<Ability> = {
  defs: buildAbilityFilterDefs(),
  numericValue,
  selectMatch,
  textHaystack,
};

/** Abilities render as a def-list, not a table, so there are no columns. The two
    sort keys (Name, Edited) are virtual columns over the same accessors the
    sort engine consumes. Used by the sort row + URL codec only. */
export const ABILITY_SORT_COLUMNS: Map<string, SortColumn<Ability>> = new Map([
  ["name", { key: "name", cellType: "string", sortValue: (a: Ability) => a.name }],
  [
    "edited",
    {
      key: "edited",
      cellType: "number",
      // Edited rows (1) sort above base (0) when descending; asc puts base first.
      sortValue: (a: Ability) => (isAbilityEdited(a) ? 1 : 0),
    },
  ],
]);

/** Sortable ability fields, in sort-row menu order (no table headers exist). */
export const ABILITY_SORTABLE: { key: string; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "edited", label: "Edited" },
];
