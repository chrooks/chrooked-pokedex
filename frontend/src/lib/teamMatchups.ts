/* Pure team-matchup math: the per-member × per-type defensive and offensive
   multiplier matrices that power the Team tab's two tables, plus the cell
   "language" (color bucket, glyph, verdict) copied faithfully from
   tectonic-tools' TypeChartCell so the grid reads identically.

   Reuses the single-species combined-type semantics: defense multiplies both of
   a member's types together and folds in its ability; offense takes the BEST of
   the member's own types per defender (a dual-type attacker picks its better
   STAB). No React — unit-tested in teamMatchups.test.ts. */

import { applyAbilityModifier } from "./abilityTypeModifiers";
import { axisOrder, cellKey, cellMap } from "./typeChartGrid";
import type { TypeChartCell } from "../types";

export interface TeamMember {
  /** chrooked_id — stable identity for keys and URL round-trips. */
  id: string;
  name: string;
  types: readonly string[];
  /** The chosen matchup-altering ability, or null for base typing. */
  ability: string | null;
}

export type Bucket =
  | "hyper"
  | "super"
  | "neutral"
  | "not-very"
  | "barely"
  | "immune";

/** Combined defensive multiplier: `attackType` hitting this member's typing
    (both types multiplied together), then the ability folded in. null ⇒ the
    chart has no data for any of the member's types (cell renders "no data"). */
export function memberDefense(
  member: TeamMember,
  attackType: string,
  byKey: ReadonlyMap<string, TypeChartCell>,
): number | null {
  let combined = 1;
  let saw = false;
  for (const own of member.types) {
    const cell = byKey.get(cellKey(attackType, own));
    if (cell) {
      combined *= cell.multiplier;
      saw = true;
    }
  }
  if (!saw) return null;
  return applyAbilityModifier(combined, attackType, member.ability);
}

/** Best-STAB offensive multiplier: this member attacking `defendType`, taking
    the best of its own types (a dual-type attacker picks its better STAB).
    null ⇒ the chart has no data for any of the member's types. */
export function memberOffense(
  member: TeamMember,
  defendType: string,
  byKey: ReadonlyMap<string, TypeChartCell>,
): number | null {
  let best: number | null = null;
  for (const own of member.types) {
    const cell = byKey.get(cellKey(own, defendType));
    if (cell) best = best === null ? cell.multiplier : Math.max(best, cell.multiplier);
  }
  return best;
}

export interface DefenseRow {
  type: string;
  /** One multiplier per member, in party order; null ⇒ no chart data. */
  cells: (number | null)[];
  weak: number;
  resist: number;
  immune: number;
}

export interface OffenseRow {
  type: string;
  cells: (number | null)[];
  strong: number;
  resist: number;
}

export interface TeamMatchups {
  axis: string[];
  defense: DefenseRow[];
  offense: OffenseRow[];
}

/** Build both matrices + per-row totals over the merged chart's axis order.
    Totals mirror tectonic's Def/AtkTotalCell exactly: defense Weak = ×>1,
    Resist = ×<1 EXCLUDING 0, Immune = ×0; offense Super = ×>1, Resist = ×<1
    INCLUDING 0 (a no-effect column counts as resisted, per AtkTotalCell). */
export function teamMatchups(
  members: readonly TeamMember[],
  cells: readonly TypeChartCell[],
): TeamMatchups {
  const axis = axisOrder(cells);
  const byKey = cellMap(cells);

  const defense: DefenseRow[] = axis.map((type) => {
    const rowCells = members.map((m) => memberDefense(m, type, byKey));
    let weak = 0;
    let resist = 0;
    let immune = 0;
    for (const v of rowCells) {
      if (v === null) continue;
      if (v > 1) weak += 1;
      else if (v === 0) immune += 1;
      else if (v < 1) resist += 1;
    }
    return { type, cells: rowCells, weak, resist, immune };
  });

  const offense: OffenseRow[] = axis.map((type) => {
    const rowCells = members.map((m) => memberOffense(m, type, byKey));
    let strong = 0;
    let resist = 0;
    for (const v of rowCells) {
      if (v === null) continue;
      if (v > 1) strong += 1;
      else if (v < 1) resist += 1;
    }
    return { type, cells: rowCells, strong, resist };
  });

  return { axis, defense, offense };
}

/** A defensive row is UNBALANCED when more of the team is weak to the type
    than has an answer to it (a resist or an immunity). Not in tectonic-tools
    (its totals are plain counts) — added in its spirit: the Weak total lights
    up so lopsided exposures pop while scanning. */
export function isUnbalanced(row: DefenseRow): boolean {
  return row.weak > row.resist + row.immune;
}

// ── Cell language (copied faithfully from tectonic-tools TypeChartCell) ──────

/** Color bucket for a multiplier. Order is load-bearing: 0 is `immune` checked
    BEFORE the <0.5 `barely` test, so a true immunity never reads as "barely".
    Neutral ×1 is `neutral` and renders BLANK with no fill. Mirrors
    getColourClassForMult (>2 hyper / >1 super / ==0 immune / <0.5 barely /
    <1 not-very). */
export function multBucket(mult: number): Bucket {
  if (mult > 2) return "hyper";
  if (mult > 1) return "super";
  if (mult === 0) return "immune";
  if (mult < 0.5) return "barely";
  if (mult < 1) return "not-very";
  return "neutral";
}

/** The glyph shown in a cell: fraction glyphs for the common resist steps, a
    plain number otherwise, and BLANK for neutral ×1. Mirrors getTextForMult —
    ⅛, ¼, ½, and ³⁄₂ (U+00B3 U+2044 U+2082). */
export function multGlyph(mult: number): string {
  if (mult === 0.125) return "⅛";
  if (mult === 0.25) return "¼";
  if (mult === 0.5) return "½";
  if (mult === 1) return "";
  if (mult === 1.5) return "³⁄₂";
  return `${mult}`;
}

/** Spoken verdict for the tooltip. Uses the ≥4 / ≥2 thresholds of tectonic's
    tooltip scale (distinct from the color scale's >2 / >1). Mirrors
    getTooltipForMult. */
export function multVerdict(mult: number): string {
  if (mult >= 4) return "Hyper Effective";
  if (mult >= 2) return "Super Effective";
  if (mult === 0) return "No Effect";
  if (mult < 0.5) return "Barely Effective";
  if (mult < 1) return "Not Very Effective";
  return "Normal Effectiveness";
}

/** Full cell tooltip: "Atk → Def = verdict". */
export function cellTooltip(
  atkLabel: string,
  defLabel: string,
  mult: number,
): string {
  return `${atkLabel} → ${defLabel} = ${multVerdict(mult)}`;
}
