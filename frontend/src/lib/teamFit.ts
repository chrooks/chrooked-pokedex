/* Team-fit derivations over the Team tab's defense matrix: the Holes list (the
   grid summarized in words) and, from #119, the Defense-first candidate score.
   Reuses teamMatchups for every multiplier — nothing here re-derives the type
   math. Pure, no React; unit-tested in teamFit.test.ts. */

import { isUnbalanced, type DefenseRow } from "./teamMatchups";

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
