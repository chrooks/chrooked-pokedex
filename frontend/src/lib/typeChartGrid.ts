/* Pure grid logic for the type-chart matrix. No React — the tab consumes these
   to render the N×N grid and to derive its save payload, and they are unit-
   tested independently (typeChartGrid.test.ts).

   The grid is the full attacker×defender merged view (base ⊕ Ruleset) as
   TypeChartCell[]; the save payload is the override-only TypeChartEntry[] of
   cells whose working multiplier differs from base. A cell cycled back to base
   is ABSENT from the payload — that is how the PUT clears an override. */

import { TYPES } from "./format";
import type { TypeChartCell, TypeChartEntry } from "../types";

/** The four legal effectiveness multipliers, in cycle order. */
export const CYCLE = [0, 0.5, 1, 2] as const;

/** A stable cell key, `"${attacker}|${defender}"`. */
export function cellKey(attacker: string, defender: string): string {
  return `${attacker}|${defender}`;
}

/** The axis order, derived from the cells so the grid NEVER hides a type the API
    actually sent. Known franchise {@link TYPES} come first in canonical order
    (restricted to those present), then any present-but-unknown types are appended
    in stable sorted order. Stable regardless of cell order. */
export function axisOrder(cells: readonly TypeChartCell[]): string[] {
  const present = new Set<string>();
  for (const cell of cells) {
    present.add(cell.attacker);
    present.add(cell.defender);
  }
  const known = new Set<string>(TYPES);
  const canonical = TYPES.filter((type) => present.has(type));
  const unknown = [...present].filter((type) => !known.has(type)).sort();
  return [...canonical, ...unknown];
}

/** A `key → cell` lookup so the grid reads each pair in O(1). */
export function cellMap(
  cells: readonly TypeChartCell[],
): Map<string, TypeChartCell> {
  const map = new Map<string, TypeChartCell>();
  for (const cell of cells) {
    map.set(cellKey(cell.attacker, cell.defender), cell);
  }
  return map;
}

/** The next multiplier in the 0 → 0.5 → 1 → 2 → 0 cycle. An unknown value
    (defensive) restarts the cycle at its first step. */
export function cycle(multiplier: number): number {
  const index = CYCLE.indexOf(multiplier as (typeof CYCLE)[number]);
  if (index === -1) return CYCLE[0];
  return CYCLE[(index + 1) % CYCLE.length];
}

/** The pre-override base value of a cell: its recorded base when overridden,
    otherwise its own (un-overridden) multiplier. */
export function baseOf(cell: TypeChartCell): number {
  return cell.overridden && cell.base_multiplier !== null
    ? cell.base_multiplier
    : cell.multiplier;
}

/** True iff the working multiplier for this cell differs from its base — i.e.
    the cell is (or would become) a Ruleset override. */
export function isCellEdited(working: number, cell: TypeChartCell): boolean {
  return working !== baseOf(cell);
}

/** The PUT payload: the {@link TypeChartEntry}[] of cells whose working
    multiplier differs from base. A cell reverted to base is dropped, so saving
    a reverted override clears it. Emitted in the cells' own iteration order. */
export function toOverrides(
  working: ReadonlyMap<string, number>,
  cells: readonly TypeChartCell[],
): TypeChartEntry[] {
  const overrides: TypeChartEntry[] = [];
  for (const cell of cells) {
    const key = cellKey(cell.attacker, cell.defender);
    const value = working.get(key) ?? cell.multiplier;
    if (value !== baseOf(cell)) {
      overrides.push({
        attacker: cell.attacker,
        defender: cell.defender,
        multiplier: value,
      });
    }
  }
  return overrides;
}
