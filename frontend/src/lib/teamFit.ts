/* Team-fit derivations over the Team tab's defense matrix: the Holes list (the
   grid summarized in words) and, from #119, the Defense-first candidate score.
   Reuses teamMatchups for every multiplier — nothing here re-derives the type
   math. Pure, no React; unit-tested in teamFit.test.ts. */

import {
  isUnbalanced,
  memberDefense,
  memberOffense,
  type DefenseRow,
  type TeamMatchups,
  type TeamMember,
} from "./teamMatchups";
import type { DexEntry, TypeChartCell } from "../types";

/** One attacking type the team is weak to. */
export interface Hole {
  type: string;
  /** Members hit for more than ×1. */
  weak: number;
  /** Members that resist (×<1) or are immune (×0). */
  answers: number;
  isUnbalanced: boolean;
  /** The hardest hit on any member, and who takes it (first in party order). */
  worst: number;
  worstIndex: number;
}

/** Every defense row with at least one weak member, worst first: unbalanced
    rows, then the widest weak-minus-answers gap, then the hardest single hit,
    then the chart's axis order. Always a new array. */
export function teamHoles(defense: readonly DefenseRow[]): Hole[] {
  const holes = defense.flatMap((row, axisIndex) => {
    if (row.weak === 0) return [];
    let worst = 0;
    let worstIndex = -1;
    row.cells.forEach((mult, i) => {
      if (mult !== null && mult > worst) {
        worst = mult;
        worstIndex = i;
      }
    });
    const hole: Hole = {
      type: row.type,
      weak: row.weak,
      answers: row.resist + row.immune,
      isUnbalanced: isUnbalanced(row),
      worst,
      worstIndex,
    };
    return [{ hole, axisIndex }];
  });
  holes.sort(
    (a, b) =>
      Number(b.hole.isUnbalanced) - Number(a.hole.isUnbalanced) ||
      b.hole.weak - b.hole.answers - (a.hole.weak - a.hole.answers) ||
      b.hole.worst - a.hole.worst ||
      a.axisIndex - b.axisIndex,
  );
  return holes.map((h) => h.hole);
}

// ── Defense-first candidate score (#119) ────────────────────────────────────

/** Score weights. Defense-first by design (Chris, 2026-10-14): fixing a lopsided
    row is worth the most, offense only breaks ties between equally safe picks.
    Symmetric on purpose: opening a row that ends up lopsided costs what fixing
    one earns (fixed + patched + covered = 5), so a pick can't buy three fixes
    with three fresh holes and still rank first. */
export const FIT_WEIGHTS = {
  fixed: 3,
  patched: 1,
  covered: 1,
  opened: -2,
  openedUnbalanced: -5,
  offense: 0.5,
} as const;

/** Why a candidate scores what it does. Each list is attacking (or, for
    offense, defending) types in the chart's axis order. */
export interface Fit {
  score: number;
  /** Unbalanced before, balanced with the candidate. */
  fixed: string[];
  /** The team was weak to it and the candidate resists or is immune. */
  patched: string[];
  /** Nobody answered it before and the candidate does (weak or not). */
  covered: string[];
  /** The candidate is weak to it. */
  opened: string[];
  /** Newly hit super-effectively by the candidate's STAB. */
  offense: string[];
}

/** The candidate as a team member, exactly as the grid would count it right
    after you add it: every ability under Redux mode, otherwise base typing (a
    new party slot starts on "Base typing"). The suggestion predicts the grid. */
export function candidateMember(entry: DexEntry, redux: boolean): TeamMember {
  const { primary, secondary, hidden } = entry.abilities;
  const names = [primary, secondary, hidden].filter((a): a is string => !!a);
  return {
    id: entry.chrooked_id,
    name: entry.name,
    types: entry.types,
    ability: redux ? names : null,
  };
}

/** How much `candidate` improves the team whose matrices are `before`. Only the
    candidate's own column is computed (memberDefense / memberOffense) and added
    to the team's existing row totals — the same result as rebuilding the matrix
    with the candidate in it, at a seventh of the cost across the whole pool. */
export function teamFit(
  before: TeamMatchups,
  candidate: TeamMember,
  byKey: ReadonlyMap<string, TypeChartCell>,
): Fit {
  const fit: Fit = { score: 0, fixed: [], patched: [], covered: [], opened: [], offense: [] };
  let score = 0;

  for (const row of before.defense) {
    const mult = memberDefense(candidate, row.type, byKey);
    if (mult === null) continue;
    const answers = row.resist + row.immune;
    const isAnswer = mult < 1;
    const after: DefenseRow = {
      ...row,
      weak: row.weak + (mult > 1 ? 1 : 0),
      resist: row.resist + (mult > 0 && mult < 1 ? 1 : 0),
      immune: row.immune + (mult === 0 ? 1 : 0),
    };
    if (isUnbalanced(row) && !isUnbalanced(after)) {
      fit.fixed.push(row.type);
      score += FIT_WEIGHTS.fixed;
    }
    if (row.weak > 0 && isAnswer) {
      fit.patched.push(row.type);
      score += FIT_WEIGHTS.patched;
    }
    if (answers === 0 && isAnswer) {
      fit.covered.push(row.type);
      score += FIT_WEIGHTS.covered;
    }
    if (mult > 1) {
      fit.opened.push(row.type);
      score += isUnbalanced(after) ? FIT_WEIGHTS.openedUnbalanced : FIT_WEIGHTS.opened;
    }
  }

  for (const row of before.offense) {
    const mult = memberOffense(candidate, row.type, byKey);
    if (mult !== null && mult > 1 && row.strong === 0) {
      fit.offense.push(row.type);
      score += FIT_WEIGHTS.offense;
    }
  }

  return { ...fit, score };
}
