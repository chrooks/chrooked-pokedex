/* The write half of mirror-down: given the whole-line preview rows (pre-evos),
   copy the anchor kit onto each pre-evo through the existing CRUD route
   (read raw Override → merge types + abilities + learnset − L0 → PUT, silent so
   the workbench flushes one dex refresh). Shared by the learnset lock's
   extraWrites and the standalone mirror-only stage. Never touches the anchor —
   `mirrorDownPreview` only ever returns pre-evos. Returns the written ids. */

import { api } from "../../api";
import type { SpeciesOverride } from "../../types";
import type { MirrorRow } from "../../lib/mirrorDown";

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

/** Write each pre-evo copy; returns the chrooked_ids actually written so the
    read-back tail checks exactly the species this session touched. */
export async function writeMirror(rows: readonly MirrorRow[]): Promise<string[]> {
  const written: string[] = [];
  for (const row of rows) {
    let raw: SpeciesOverride;
    try {
      raw = await api.speciesOverride(row.chrooked_id);
    } catch {
      raw = seedOverride(row);
    }
    await api.putSpecies(
      row.chrooked_id,
      { ...raw, types: row.types, abilities: row.abilities, learnset: row.learnset },
      undefined,
      { silent: true },
    );
    written.push(row.chrooked_id);
  }
  return written;
}
