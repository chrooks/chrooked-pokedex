/* The write half of the MIRROR stage: given the preview rows, copy the anchor
   kit onto each recipient through the existing CRUD route (read raw Override →
   merge the selected facets → PUT, silent so the workbench flushes one dex
   refresh). Never touches the anchor — the caller's rows never include it.
   Returns the written ids. */

import { api, ApiError } from "../../api";
import type { SpeciesOverride } from "../../types";
import {
  DEFAULT_MIRROR_FACETS,
  type MirrorFacet,
  type MirrorRow,
} from "../../lib/mirrorDown";

function seedOverride(row: MirrorRow): SpeciesOverride {
  return {
    name: row.name,
    chrooked_id: row.chrooked_id,
    aka: row.dex !== null ? { dex: row.dex } : {},
    types: null,
    abilities: null,
    stats: null,
    learnset: null,
    evolution: null,
  };
}

/** Write each recipient copy, restricted to the selected facets (default: the
    classic types + abilities + learnset mirror-down). Returns the chrooked_ids
    actually written so the read-back tail checks exactly the species this
    session touched. */
export async function writeMirror(
  rows: readonly MirrorRow[],
  facets: ReadonlySet<MirrorFacet> = DEFAULT_MIRROR_FACETS,
): Promise<string[]> {
  const written: string[] = [];
  for (const row of rows) {
    let raw: SpeciesOverride;
    try {
      raw = await api.speciesOverride(row.chrooked_id);
    } catch (caught: unknown) {
      // Seed a blank Override only when the species genuinely has none. Any
      // other read failure means we cannot see what we are about to overwrite,
      // and a seed's explicit nulls would clear it.
      if (!(caught instanceof ApiError) || caught.status !== 404) throw caught;
      raw = seedOverride(row);
    }
    await api.putSpecies(
      row.chrooked_id,
      {
        ...raw,
        ...(facets.has("types") ? { types: row.types } : {}),
        ...(facets.has("abilities") ? { abilities: row.abilities } : {}),
        ...(facets.has("stats") && row.stats ? { stats: row.stats } : {}),
        ...(facets.has("learnset") ? { learnset: row.learnset } : {}),
      },
      undefined,
      { silent: true },
    );
    written.push(row.chrooked_id);
  }
  return written;
}
