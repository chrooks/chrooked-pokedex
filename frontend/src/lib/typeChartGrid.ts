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

/** Cell-size bounds for the fit-to-viewport sizing. Min keeps glyphs legible;
    max stops the grid ballooning in a huge container. */
export const TC_CELL_MIN = 16;
export const TC_CELL_MAX = 44;
/** The header track is sized proportional to the cell so the band stays in
    rhythm as the grid scales. */
export const TC_HEAD_RATIO = 1.2;

export interface FitResult {
  /** The fitted cell edge, in px, clamped to [TC_CELL_MIN, TC_CELL_MAX]. */
  cell: number;
  /** The header track edge, in px (cell × ratio). */
  head: number;
  /** True when even the minimum cell overflows the box — the grid must scroll. */
  overflow: boolean;
}

/** Size the N×N grid's cell so the whole matrix + one header track fits BOTH the
    container width and height with no scrollbar.

      cell = floor(min((W - head) / N, (H - head) / N))

    The header track is `cell × ratio`, so it scales with the cell; we solve the
    fit against the clamped-max head first (the generous case) then re-derive the
    head from the chosen cell. The result is clamped to [min, max]; when the
    clamped cell still overflows the box, `overflow` is true so the caller can
    fall back to scrolling (graceful, only at tiny sizes). */
export function fitCellSize(box: { width: number; height: number }, n: number): FitResult {
  if (n <= 0 || box.width <= 0 || box.height <= 0) {
    const cell = TC_CELL_MAX;
    return { cell, head: Math.round(cell * TC_HEAD_RATIO), overflow: false };
  }
  // Available room for the N matchup tracks once a header track (cell × ratio)
  // is reserved. Solve W = head + N·cell with head = cell·ratio:
  //   cell = W / (ratio + N)
  const byWidth = box.width / (TC_HEAD_RATIO + n);
  const byHeight = box.height / (TC_HEAD_RATIO + n);
  const ideal = Math.floor(Math.min(byWidth, byHeight));
  const cell = Math.max(TC_CELL_MIN, Math.min(TC_CELL_MAX, ideal));
  const head = Math.round(cell * TC_HEAD_RATIO);
  // At the clamped min, does the grid still fit? If not, the caller scrolls.
  const needed = head + n * cell;
  const overflow = cell === TC_CELL_MIN && (needed > box.width || needed > box.height);
  return { cell, head, overflow };
}

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

/** One member of a matchup bucket: the OTHER type in the pairing, plus whether
    THAT specific matchup cell is a Ruleset override — so the breakdown panel can
    carry the same edited indicator (and Edited-only highlight) the grid shows. */
export interface MatchupMember {
  type: string;
  /** True iff this matchup cell differs from base (same test the grid cell uses). */
  edited: boolean;
}

/** The defensive matchup buckets for the selected type: every attacker bucketed
    by the multiplier of (attacker → selectedType). Each list is ordered by the
    grid axis so the panel reads in the same order as the rows. */
export interface DefenseMatchups {
  /** Attackers that hit the type for ×2 — what the type is "weak to". */
  weak: MatchupMember[];
  /** Attackers at ×1 — the boring neutral majority. */
  neutral: MatchupMember[];
  /** Attackers at ×0.5 — what the type "resists". */
  resist: MatchupMember[];
  /** Attackers at ×0 — what the type is "immune to". */
  immune: MatchupMember[];
}

/** The offensive matchup buckets for the selected type: every defender bucketed
    by the multiplier of (selectedType → defender). Ordered by the grid axis. */
export interface OffenseMatchups {
  /** Defenders the type hits for ×2 — what it is "strong against". */
  strong: MatchupMember[];
  /** Defenders at ×1 — neutral hits. */
  neutral: MatchupMember[];
  /** Defenders at ×0.5 — what "resists" the type's attacks. */
  resisted: MatchupMember[];
  /** Defenders at ×0 — what the type "can't hit". */
  noEffect: MatchupMember[];
}

export interface Matchups {
  defense: DefenseMatchups;
  offense: OffenseMatchups;
}

/** Bucket the selected type's whole row and column into the eight matchup lists,
    reading the SAME merged cells + valueOf the grid shows (so it reflects working
    edits in canon and the fork's chart in backdrop).

    Defense buckets the COLUMN — every (attacker → type) — by effectiveness.
    Offense buckets the ROW — every (type → defender). The axis (derived via
    {@link axisOrder}) drives both iteration order, so a type that appears only as
    an attacker still shows up in the offense buckets, and one that appears only
    as a defender still shows up in the defense buckets. A pair with no cell is
    skipped (it cannot be classified). */
export function matchups(
  type: string,
  cells: readonly TypeChartCell[],
  valueOf: (cell: TypeChartCell) => number,
): Matchups {
  const axis = axisOrder(cells);
  const byKey = cellMap(cells);

  const defense: DefenseMatchups = {
    weak: [],
    neutral: [],
    resist: [],
    immune: [],
  };
  const offense: OffenseMatchups = {
    strong: [],
    neutral: [],
    resisted: [],
    noEffect: [],
  };

  for (const other of axis) {
    // Defense: how `other` (attacker) hits the selected type (defender).
    const incoming = byKey.get(cellKey(other, type));
    if (incoming) {
      const value = valueOf(incoming);
      const member: MatchupMember = {
        type: other,
        edited: isCellEdited(value, incoming),
      };
      if (value === 2) defense.weak.push(member);
      else if (value === 1) defense.neutral.push(member);
      else if (value === 0.5) defense.resist.push(member);
      else if (value === 0) defense.immune.push(member);
    }

    // Offense: how the selected type (attacker) hits `other` (defender).
    const outgoing = byKey.get(cellKey(type, other));
    if (outgoing) {
      const value = valueOf(outgoing);
      const member: MatchupMember = {
        type: other,
        edited: isCellEdited(value, outgoing),
      };
      if (value === 2) offense.strong.push(member);
      else if (value === 1) offense.neutral.push(member);
      else if (value === 0.5) offense.resisted.push(member);
      else if (value === 0) offense.noEffect.push(member);
    }
  }

  return { defense, offense };
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
