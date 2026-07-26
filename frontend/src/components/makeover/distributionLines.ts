/* Pure grouping + include-set logic for the distribute panels' "by evo line, not
   individual mon" view. No React, unit-tested in the node env. A big ✦ Suggest
   result (Bioturbation → 150 mons) is folded into one group per evolution family
   so the controlling unit is the LINE. The breadth slider is a pure client-side
   trim over the already-fetched proposal (top-K lines by rank) — it fires NO new
   LLM call. Immutable throughout; mirrors the distributionDraft ops' style. */

import type { DexEntry } from "../../types";
import { expandEvoLines } from "../../lib/evoLine";

/** One evolution family folded out of the proposal. `members` are only the
    family members actually PRESENT in the proposal (a species whose relatives
    weren't suggested groups alone), in dex order for a readable label. `rank` is
    the order the line first appears in the proposal (its min member row index) —
    the breadth slider's top-K ordering. `lineId` is the family's stable key,
    identical for every member of the same family whether or not all are present. */
export interface LineGroup {
  lineId: string;
  members: string[];
  rank: number;
}

/** The family's stable key: the lexicographically smallest chrooked_id across the
    WHOLE family (present or not), so every member folds to the same group and the
    key survives a partial proposal. */
function familyKeyFrom(memberIds: readonly string[]): string {
  return [...memberIds].sort()[0];
}

/** The stable line id for one species' whole evolution family. Unknown species
    (not in the dex) are their own single-member line. Exported for the panels'
    per-add include bookkeeping. */
export function lineIdOf(species: string, byId: ReadonlyMap<string, DexEntry>): string {
  const entry = byId.get(species);
  if (entry === undefined) return species;
  const family = expandEvoLines([entry], [...byId.values()]);
  return familyKeyFrom(family.map((e) => e.chrooked_id));
}

/** Fold species rows into ordered `LineGroup[]`, one per evolution family, rank
    preserved by first appearance. Members present in the proposal only, deduped,
    ordered by dex position for the group label. A family with just one present
    member still becomes a (single-member) group under the family's stable id. */
export function groupByLine<T extends { species: string }>(
  rows: readonly T[],
  byId: ReadonlyMap<string, DexEntry>,
): LineGroup[] {
  const all = [...byId.values()];
  const dexIndex = new Map(all.map((e, i) => [e.chrooked_id, i]));
  const keyCache = new Map<string, string>();
  const keyOf = (species: string): string => {
    const cached = keyCache.get(species);
    if (cached !== undefined) return cached;
    const entry = byId.get(species);
    const key =
      entry === undefined
        ? species
        : familyKeyFrom(expandEvoLines([entry], all).map((e) => e.chrooked_id));
    keyCache.set(species, key);
    return key;
  };

  const order: string[] = [];
  const membersByKey = new Map<string, string[]>();
  for (const row of rows) {
    const key = keyOf(row.species);
    let members = membersByKey.get(key);
    if (members === undefined) {
      members = [];
      membersByKey.set(key, members);
      order.push(key);
    }
    if (!members.includes(row.species)) members.push(row.species);
  }

  return order.map((lineId, rank) => ({
    lineId,
    members: [...membersByKey.get(lineId)!].sort(
      (a, b) => (dexIndex.get(a) ?? 0) - (dexIndex.get(b) ?? 0),
    ),
    rank,
  }));
}

/** The first `k` line ids by rank (k clamped to [0, groups.length]). Moving the
    breadth slider to K sets the include-set to exactly this prefix. */
export function topLineIds(groups: readonly LineGroup[], k: number): string[] {
  const clamped = Math.max(0, Math.min(Math.trunc(k), groups.length));
  return groups.slice(0, clamped).map((g) => g.lineId);
}

/** Every line id — the "all" bulk action's include-set. */
export function allLineIds(groups: readonly LineGroup[]): string[] {
  return groups.map((g) => g.lineId);
}

/** Toggle one line's membership immutably (the include checkbox). Toggling edits
    the set's size, so the slider's K reading (= included.size) stays in sync. */
export function toggleIncluded(
  included: ReadonlySet<string>,
  lineId: string,
): Set<string> {
  const next = new Set(included);
  if (next.has(lineId)) next.delete(lineId);
  else next.add(lineId);
  return next;
}

/** The included member (mon) count — the group members whose line is included.
    Drives the "distribution (N mons · K lines)" readout and the DISTRIBUTE gate. */
export function includedMemberCount(
  groups: readonly LineGroup[],
  included: ReadonlySet<string>,
): number {
  return groups.reduce(
    (sum, g) => (included.has(g.lineId) ? sum + g.members.length : sum),
    0,
  );
}
