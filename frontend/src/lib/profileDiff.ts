/* ac12 — the line strip's before→after diff, as pure functions (no React) so the
   changed/unchanged classification and the learnset added/moved/dropped counts are
   unit-tested without a browser. The baseline is the anchor's profile captured at
   workbench OPEN; the after-state per facet is `facts[facet] ?? entry[facet]` —
   the facet locked this session wins, everything else reflects the live entry. */

import type { AbilitySlots, DexEntry, LearnsetMove } from "../types";
import type { StageFacts } from "./makeoverApi";

/** A six-stat spread. The dex ships stats as an open record; the diff treats it
    as such and reads the canonical keys via format's STAT_ORDER at render. */
type StatSpread = Record<string, number>;

/** The anchor's profile at a moment in time — the baseline captured at OPEN. */
export interface ProfileSnapshot {
  types: string[];
  stats: StatSpread;
  abilities: AbilitySlots;
  learnset: LearnsetMove[];
}

/** One facet's before→after, with a `changed` flag the strip reads directly. */
export interface FacetDiff<T> {
  changed: boolean;
  before: T;
  after: T;
}

/** A learnset before→after as counts + the row lists behind them: rows the after
    added, rows it dropped, and rows whose level moved (same move, new level). */
export interface LearnsetDiff {
  added: LearnsetMove[];
  removed: LearnsetMove[];
  moved: { move: string; from: number; to: number }[];
}

export interface ProfileDiff {
  types: FacetDiff<string[]>;
  stats: FacetDiff<StatSpread>;
  abilities: FacetDiff<AbilitySlots>;
  learnset: LearnsetDiff;
}

/** Freeze the anchor's profile — called once at mount (the diff baseline). Copies
    the arrays/objects so a later live-entry mutation can never rewrite history. */
export function snapshotProfile(entry: DexEntry): ProfileSnapshot {
  return {
    types: [...entry.types],
    stats: { ...entry.stats },
    abilities: { ...entry.abilities },
    learnset: entry.learnset.map((row) => ({ level: row.level, move: row.move })),
  };
}

function typesChanged(before: readonly string[], after: readonly string[]): boolean {
  if (before.length !== after.length) return true;
  return before.some((t, i) => t !== after[i]);
}

function statsChanged(before: StatSpread, after: StatSpread): boolean {
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
  for (const key of keys) {
    if (before[key] !== after[key]) return true;
  }
  return false;
}

function abilitiesChanged(before: AbilitySlots, after: AbilitySlots): boolean {
  return (
    before.primary !== after.primary ||
    before.secondary !== after.secondary ||
    before.hidden !== after.hidden
  );
}

const rowKey = (row: LearnsetMove): string => `${row.level}::${row.move}`;
const byLevelThenMove = (a: LearnsetMove, b: LearnsetMove): number =>
  a.level - b.level || a.move.localeCompare(b.move);

/** Diff two learnsets by (level, move) identity, then reclassify a move that left
    one level and arrived at another as MOVED (same move name in both raw sets).
    Duplicate move names pair up greedily by name. */
export function diffLearnset(
  before: readonly LearnsetMove[],
  after: readonly LearnsetMove[],
): LearnsetDiff {
  const beforeKeys = new Set(before.map(rowKey));
  const afterKeys = new Set(after.map(rowKey));
  const addedRaw = after.filter((row) => !beforeKeys.has(rowKey(row)));
  const removedRaw = before.filter((row) => !afterKeys.has(rowKey(row)));

  const removedByMove = new Map<string, number[]>();
  for (const row of removedRaw) {
    const levels = removedByMove.get(row.move) ?? [];
    levels.push(row.level);
    removedByMove.set(row.move, levels);
  }

  const added: LearnsetMove[] = [];
  const moved: { move: string; from: number; to: number }[] = [];
  for (const row of addedRaw) {
    const fromLevels = removedByMove.get(row.move);
    if (fromLevels && fromLevels.length > 0) {
      moved.push({ move: row.move, from: fromLevels.shift() as number, to: row.level });
    } else {
      added.push(row);
    }
  }

  const removed: LearnsetMove[] = [];
  for (const [move, levels] of removedByMove) {
    for (const level of levels) removed.push({ level, move });
  }

  return {
    added: added.sort(byLevelThenMove),
    removed: removed.sort(byLevelThenMove),
    moved: moved.sort((a, b) => a.move.localeCompare(b.move)),
  };
}

/** The whole before→after profile diff. After-state per facet is `facts[facet] ??
    entry[facet]` — a facet locked THIS session shows its new value, everything
    else reflects the live entry (unchanged vs the baseline captured at open). */
export function diffProfile(
  before: ProfileSnapshot,
  entry: DexEntry,
  facts: StageFacts,
): ProfileDiff {
  const afterTypes = facts.types ?? entry.types;
  const afterStats = facts.stats ?? entry.stats;
  const afterAbilities = facts.abilities ?? entry.abilities;
  const afterLearnset = entry.learnset; // facts carry no learnset; the entry is source

  return {
    types: {
      changed: typesChanged(before.types, afterTypes),
      before: before.types,
      after: afterTypes,
    },
    stats: {
      changed: statsChanged(before.stats, afterStats),
      before: before.stats,
      after: afterStats,
    },
    abilities: {
      changed: abilitiesChanged(before.abilities, afterAbilities),
      before: before.abilities,
      after: afterAbilities,
    },
    learnset: diffLearnset(before.learnset, afterLearnset),
  };
}
