/* The Origin and Regional Dex filters' data source. Origin is the region a
   species was introduced in: derived from the national dex number's generation
   range, except a regional form ("Raichu Alola") belongs to the region in its
   name. Regional Dex membership comes from `regions.json` (baked by
   scripts/build_regions.py), keyed by national dex number. A regional form
   lists only in its own region's dex (Raichu Alola: Alola, not Sinnoh); every
   other form inherits its species' row. Pure. */

import rawRegions from "../data/regions.json";

/** Every region, in generation order. The filter value set for both fields. */
export const REGIONS = [
  "Kanto",
  "Johto",
  "Hoenn",
  "Sinnoh",
  "Unova",
  "Kalos",
  "Alola",
  "Galar",
  "Hisui",
  "Paldea",
  "Aevium",
] as const;

export type Region = (typeof REGIONS)[number];

// The first national dex number of each generation, plus the Hisui-original
// species (899 Wyrdeer – 905 Enamorus) which debuted in Legends: Arceus.
const ORIGIN_STARTS: [number, Region][] = [
  [906, "Paldea"],
  [899, "Hisui"],
  [810, "Galar"],
  [722, "Alola"],
  [650, "Kalos"],
  [494, "Unova"],
  [387, "Sinnoh"],
  [252, "Hoenn"],
  [152, "Johto"],
  [1, "Kanto"],
];

// A regional form carries its region as a word in its display name. Aevian is
// Rejuvenation's own region (Aevium).
const FORM_REGION = /\b(Alola|Galar|Hisui|Paldea|Aevian)\b/;
const FORM_TO_REGION: Record<string, Region> = {
  Alola: "Alola",
  Galar: "Galar",
  Hisui: "Hisui",
  Paldea: "Paldea",
  Aevian: "Aevium",
};

const REGIONAL_DEXES = rawRegions as Record<string, string[]>;

/** The region named by a regional form's display name, or null for a base or
    cosmetic form ("Pikachu Sinnoh" is a cap, not a regional form). */
function formRegion(name: string): Region | null {
  const hit = FORM_REGION.exec(name);
  return hit ? FORM_TO_REGION[hit[1]] : null;
}

/** The region a species (or regional form) was introduced in, or null when it
    has no dex number and no regional form name. */
export function originOf(entry: { dex: number | null; name: string }): Region | null {
  const form = formRegion(entry.name);
  if (form) {
    return form;
  }
  if (entry.dex === null || entry.dex < 1) {
    return null;
  }
  const hit = ORIGIN_STARTS.find(([start]) => entry.dex! >= start);
  return hit ? hit[1] : null;
}

/** Every regional Pokédex that lists this entry. A regional form lists only in
    its own region; any other entry takes its species' row. Empty for no dex
    number.
    ponytail: PokeAPI has no per-form dex data, so an Alolan form carried into a
    later dex (Alolan Vulpix in Hisui) reads as Alola only. Hand-curate a
    form -> regions table in regions.json if that gap matters. */
export function regionalDexesOf(entry: { dex: number | null; name: string }): string[] {
  const form = formRegion(entry.name);
  if (form) {
    return [form];
  }
  if (entry.dex === null) {
    return [];
  }
  return REGIONAL_DEXES[String(entry.dex)] ?? [];
}
