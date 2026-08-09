/* The learnset pacing-band rubric, consumed by the workbench's learnset stage.
   The band data itself is served by the backend (`GET /api/meta/learnset-rubric`,
   the single source of truth) — this module is only the pure lookup + the row
   annotation (ac4). A proposal row whose BP exceeds its level band's ceiling gets
   a mono flag, e.g. `L8 · 75BP · BAND ≤60`. */

export interface RubricBand {
  level_min: number;
  level_max: number;
  bp_max?: number;
  bp_min?: number;
  label: string;
}

export interface LearnsetRubric {
  version: number;
  note?: string;
  bands: RubricBand[];
}

/** The band a level falls in, or null if no band covers it (defensive — the
    served rubric spans L1–100). */
export function bandForLevel(rubric: LearnsetRubric | null, level: number): RubricBand | null {
  if (rubric === null) return null;
  for (const band of rubric.bands) {
    if (level >= band.level_min && level <= band.level_max) return band;
  }
  return null;
}

/** One rung of the ladder: the levels a band actually governs, plus its window. */
export interface LadderRung {
  levelMin: number;
  levelMax: number;
  /** The band's own label, as the violation flag words it. */
  label: string;
  /** The numeric BP window, rendered when the label alone hides it. */
  bpMin?: number;
  bpMax?: number;
}

/** The ladder as the checker sees it: one rung per band, level ranges disjoint.

    The served bands OVERLAP on purpose (L1-12, L10-22, L18-32…) — the extra room
    is slack for the suggester. `bandForLevel` takes the FIRST match, so the range
    a band really governs starts after every earlier band's ceiling. Drawing the
    raw ranges would show rungs the flags do not enforce; these are the enforced
    ones. A band wholly shadowed by an earlier one is dropped. */
export function ladderRungs(rubric: LearnsetRubric | null): LadderRung[] {
  if (rubric === null) return [];
  const rungs: LadderRung[] = [];
  let covered = 0;
  for (const band of rubric.bands) {
    const levelMin = Math.max(band.level_min, covered + 1);
    covered = Math.max(covered, band.level_max);
    if (levelMin > band.level_max) continue;
    rungs.push({
      levelMin,
      levelMax: band.level_max,
      label: band.label,
      bpMin: band.bp_min,
      bpMax: band.bp_max,
    });
  }
  return rungs;
}

/** A band-violation annotation for one proposal row, or null when the row is in
    band (or exempt). L0 rows are on-evolution rewards — exempt. Status/utility
    moves (no power) are exempt. The flagged case is the documented hard cap: a
    move whose BP exceeds its band ceiling (e.g. a 75BP hit at L8). */
export function bandViolation(
  rubric: LearnsetRubric | null,
  level: number,
  power: number | null | undefined,
): string | null {
  if (rubric === null) return null;
  if (level === 0) return null;
  if (power === null || power === undefined) return null;
  const band = bandForLevel(rubric, level);
  if (band === null || band.bp_max === undefined) return null;
  if (power > band.bp_max) {
    return `L${level} · ${power}BP · BAND ${band.label}`;
  }
  return null;
}
