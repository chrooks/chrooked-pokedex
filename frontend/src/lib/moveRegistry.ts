/* The Moves FieldRegistry: the Move binding of the shared filter engine. Numeric
   defs (Power/Accuracy/PP) derive from the column registry so they can't drift;
   Type/Category/Edited are select fields; Name/Description/Flags are text. The
   boolean machinery lives in filterEngine.ts. Pure, no React. */

import type { Move } from "../types";
import { TYPES, MOVE_FLAGS, MOVE_TARGETS, isMoveEdited } from "./format";
import { MOVE_COLUMNS } from "./moveColumns";
import type { FieldRegistry, FilterDef } from "./filterEngine";

const MOVE_CATEGORIES = ["physical", "special", "status"] as const;

/** The filterable move fields, derived once. Numeric defs come straight from the
    number columns; the rest are explicit virtual fields. */
export function buildMoveFilterDefs(): FilterDef[] {
  const numericDefs: FilterDef[] = MOVE_COLUMNS.filter(
    (column) => column.cellType === "number",
  ).map((column) => ({
    field: column.key,
    label: column.label,
    method: "numeric",
  }));
  return [
    ...numericDefs,
    { field: "type", label: "Type", method: "select", values: [...TYPES] },
    {
      field: "category",
      label: "Category",
      method: "select",
      values: [...MOVE_CATEGORIES],
    },
    { field: "flags", label: "Flag", method: "select", values: [...MOVE_FLAGS] },
    { field: "target", label: "Target", method: "select", values: [...MOVE_TARGETS] },
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

function numericValue(field: string, move: Move): number | undefined {
  if (field === "power") return move.power ?? undefined;
  if (field === "accuracy") return move.accuracy ?? undefined;
  if (field === "pp") return move.pp ?? undefined;
  return undefined;
}

function selectMatch(field: string, move: Move, value: string): boolean {
  if (field === "type") return move.type === value;
  if (field === "category") return move.category === value;
  if (field === "flags") return move.flags.includes(value);
  if (field === "target") return move.target === value;
  if (field === "edited") {
    return value === "Edited" ? isMoveEdited(move) : !isMoveEdited(move);
  }
  return false;
}

function textHaystack(field: string, move: Move): string {
  if (field === "description") return move.description;
  return move.name;
}

export const MOVE_REGISTRY: FieldRegistry<Move> = {
  defs: buildMoveFilterDefs(),
  numericValue,
  selectMatch,
  textHaystack,
};
