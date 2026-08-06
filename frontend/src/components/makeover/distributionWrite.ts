/* The shared write for distributing an ability into a slot on each chosen species
   — read-merge-write per species, merging the slot so the other two slots survive.
   Used by the "distribute an existing ability" panel; the ability-create panel
   keeps its own inline version (it writes the new ability first, then distributes).
   Silent so the caller flushes ONE dex refresh. */

import { api, ApiError } from "../../api";
import type { DexEntry, SpeciesOverride } from "../../types";
import type { DistRow } from "./distributionDraft";

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

/** Write `abilityName` into each row's slot on its species. Returns the species
    written (for the read-back). Stop-and-report: a failure throws to the caller. */
export async function writeDistribution(
  abilityName: string,
  rows: readonly DistRow[],
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
    const current = byId.get(row.species)?.abilities ?? {
      primary: null,
      secondary: null,
      hidden: null,
    };
    await api.putSpecies(
      row.species,
      { ...raw, abilities: { ...current, [row.slot]: abilityName } },
      undefined,
      { silent: true },
    );
    written.push(row.species);
  }
  return written;
}
