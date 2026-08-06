/* The shared write for distributing a MOVE into each chosen species' learnset —
   read-merge-write per species, MERGING the (level, move) row so the rest of the
   learnset survives. Learnsets are stored WHOLE in an Override, so the merge base
   is the raw Override's learnset when present, else the effective (merged) learnset
   from the dex. A move already present is replaced at its new level (dedupe by move
   name). Silent so the caller flushes ONE dex refresh. The learnset twin of
   distributionWrite.ts. */

import { api, ApiError } from "../../api";
import type { DexEntry, LearnsetMove, SpeciesOverride } from "../../types";
import type { MoveDistRow } from "./moveDistribution";

function seedOverride(species: string, byId: ReadonlyMap<string, DexEntry>): SpeciesOverride {
  const target = byId.get(species);
  return {
    name: target?.name ?? species,
    chrooked_id: species,
    aka: target?.dex != null ? { dex: target.dex } : {},
    types: null,
    abilities: null,
    stats: null,
    learnset: null,
    evolution: null,
  };
}

/** Merge `moveName` at `level` into `learnset`: drop any existing row for that move
    (replace at the new level), add the new row, and keep the list level-ordered. */
function mergeLearnset(
  learnset: readonly LearnsetMove[],
  moveName: string,
  level: number,
): LearnsetMove[] {
  return [
    ...learnset.filter((entry) => entry.move !== moveName),
    { level, move: moveName },
  ].sort((a, b) => a.level - b.level);
}

/** Write `moveName` into each row's species learnset at its level. Returns the
    species written (for the read-back). Stop-and-report: a failure throws to the
    caller. Silent PUTs — the caller flushes one dex refresh. */
export async function writeMoveDistribution(
  moveName: string,
  rows: readonly MoveDistRow[],
  byId: ReadonlyMap<string, DexEntry>,
): Promise<string[]> {
  const written: string[] = [];
  for (const row of rows) {
    let raw: SpeciesOverride;
    try {
      raw = await api.speciesOverride(row.species);
    } catch (caught: unknown) {
      // Seed a blank Override only when the species genuinely has none. Any
      // other read failure means we cannot see what we are about to overwrite,
      // and a seed's explicit nulls would clear it.
      if (!(caught instanceof ApiError) || caught.status !== 404) throw caught;
      raw = seedOverride(row.species, byId);
    }
    // The merge base: the Override's whole learnset if it already overrides one,
    // else the effective (merged) learnset carried on the dex entry.
    const currentLearnset = raw.learnset ?? byId.get(row.species)?.learnset ?? [];
    await api.putSpecies(
      row.species,
      { ...raw, learnset: mergeLearnset(currentLearnset, moveName, row.level) },
      undefined,
      { silent: true },
    );
    written.push(row.species);
  }
  return written;
}
