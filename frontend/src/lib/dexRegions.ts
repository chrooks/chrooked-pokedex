/* The Origin and Regional Dex filters' data source. Origin is the region a
   species was introduced in: derived from the national dex number's generation
   range, except a regional form ("Raichu Alola") belongs to the region in its
   name. Regional Dex membership comes from `regions.json` (baked by
   scripts/build_regions.py), keyed by national dex number; forms inherit it.
   Pure. */

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

/** The region a species (or regional form) was introduced in, or null when it
    has no dex number and no regional form name. */
export function originOf(entry: { dex: number | null; name: string }): Region | null {
  const form = FORM_REGION.exec(entry.name);
  if (form) {
    return FORM_TO_REGION[form[1]];
  }
  if (entry.dex === null || entry.dex < 1) {
    return null;
  }
  const hit = ORIGIN_STARTS.find(([start]) => entry.dex! >= start);
  return hit ? hit[1] : null;
}

/** Every regional Pokédex that lists the species. Empty for no dex number. */
export function regionalDexesOf(dex: number | null): string[] {
  if (dex === null) {
    return [];
  }
  return REGIONAL_DEXES[String(dex)] ?? [];
}
