/* Pure draft logic for distributing a MOVE onto species learnsets — the learnset
   twin of distributionDraft.ts. No React, unit-tested in the node environment.
   The move-distribute panel builds a working MoveDistRow[] as the author adds
   species + a level, then the write merges each row into its species learnset.
   Immutable ops, dedupe on add (re-add replaces the row's level). */

import type { DexEntry } from "../../types";

/** One distribution target: the species (chrooked_id) and the level the move
    lands at in that species' learnset. */
export interface MoveDistRow {
  species: string;
  level: number;
}

/** The level at which `species` already learns `moveName` in its (merged)
    learnset, or null when it doesn't. Learnsets store the display move NAME, so
    the panel's chosen move name matches directly. Derived live for the add-row's
    "currently: L{n}" / "not learned" hint (the move twin of `deriveReplaces`). */
export function deriveCurrentLevel(
  byId: ReadonlyMap<string, DexEntry>,
  species: string,
  moveName: string,
): number | null {
  const row = (byId.get(species)?.learnset ?? []).find((e) => e.move === moveName);
  return row ? row.level : null;
}

/** Set the level of the row at `index` (immutable). Out-of-range index is a no-op. */
export function setLevel(
  rows: readonly MoveDistRow[],
  index: number,
  level: number,
): MoveDistRow[] {
  return rows.map((row, i) => (i === index ? { ...row, level } : row));
}

/** Drop the row at `index` (immutable). Out-of-range index is a no-op. */
export function removeRow(rows: readonly MoveDistRow[], index: number): MoveDistRow[] {
  return rows.filter((_, i) => i !== index);
}

/** Add a row, deduped by species: re-adding a species REPLACES its existing row
    (so the last level chosen for a species wins) rather than appending a duplicate. */
export function addRow(rows: readonly MoveDistRow[], row: MoveDistRow): MoveDistRow[] {
  const withoutSpecies = rows.filter((r) => r.species !== row.species);
  return [...withoutSpecies, { species: row.species, level: row.level }];
}
