/* Pure draft logic for the CREATE NEW ability distribution — no React, unit-tested
   in the node environment. The ability-create panel seeds a working DistRow[] from
   the proposal each time one lands, then the author edits slots, removes rows, and
   adds species before CONFIRM. Mirrors learnsetDraft.ts: immutable ops, dedupe on
   add, and a derived "replaces" for the live clobber preview. */

import type { DexEntry } from "../../types";

/** One distribution target: the species (chrooked_id) and the slot the new ability
    lands in. The proposal's `replaces`/`reasoning` are display-only and derived
    live, so the working draft carries only the two fields a write needs. */
export interface DistRow {
  species: string;
  slot: "primary" | "secondary" | "hidden";
}

/** Set the slot of the row at `index` (immutable). Out-of-range index is a no-op. */
export function setSlot(
  rows: readonly DistRow[],
  index: number,
  slot: DistRow["slot"],
): DistRow[] {
  return rows.map((row, i) => (i === index ? { ...row, slot } : row));
}

/** Drop the row at `index` (immutable). Out-of-range index is a no-op. */
export function removeRow(rows: readonly DistRow[], index: number): DistRow[] {
  return rows.filter((_, i) => i !== index);
}

/** Add a row, deduped by species: re-adding a species REPLACES its existing row
    (so the last slot chosen for a species wins) rather than appending a duplicate. */
export function addRow(rows: readonly DistRow[], row: DistRow): DistRow[] {
  const withoutSpecies = rows.filter((r) => r.species !== row.species);
  return [...withoutSpecies, { species: row.species, slot: row.slot }];
}

/** The species' current occupant of `slot` — what the write would clobber. Null
    when the slot is empty or the species is unknown. Derived live so the preview
    stays honest as the author retargets a row. */
export function deriveReplaces(
  byId: ReadonlyMap<string, DexEntry>,
  species: string,
  slot: DistRow["slot"],
): string | null {
  return byId.get(species)?.abilities[slot] ?? null;
}
