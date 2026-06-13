/* Display helpers: stat labels/order, type slugs, dex-number formatting, and
   the base→now diff for overridden stats. Pure functions, no React. */

import type { DexEntry } from "../types";

/** The six base stats in canonical display order, with short uppercase labels. */
export const STAT_ORDER = ["hp", "atk", "def", "spa", "spd", "spe"] as const;
export type StatKey = (typeof STAT_ORDER)[number];

export const STAT_LABEL: Record<StatKey, string> = {
  hp: "HP",
  atk: "ATK",
  def: "DEF",
  spa: "SPA",
  spd: "SPD",
  spe: "SPE",
};

/** A type name lowercased to its CSS token slug, e.g. "Water" -> "water". */
export function typeSlug(type: string): string {
  return type.trim().toLowerCase();
}

/** The 18 franchise types, in canonical order, as display names. Suggestion
    source for the type comboboxes (species editor + type chart). */
export const TYPES = [
  "Normal",
  "Fire",
  "Water",
  "Electric",
  "Grass",
  "Ice",
  "Fighting",
  "Poison",
  "Ground",
  "Flying",
  "Psychic",
  "Bug",
  "Rock",
  "Ghost",
  "Dragon",
  "Dark",
  "Steel",
  "Fairy",
] as const;

/** Neutral move flags the Ruleset models (mirrors schema.MOVE_FLAGS). The tag
    vocabulary the Moves tab filters by. */
export const MOVE_FLAGS = [
  "contact",
  "punching",
  "biting",
  "sound",
  "slicing",
  "wind",
  "wing",
  "kicking",
  "piercing",
  "bone",
  "hammer",
  "ballistic",
] as const;

/** A three-letter uppercase code for the dense grid, e.g. "Dragon" -> "DRA". */
export function typeCode(type: string): string {
  return type.trim().slice(0, 3).toUpperCase();
}

/** "№ 706", or "№ ---" when a species has no national dex number. */
export function dexLabel(dex: number | null): string {
  if (dex === null) {
    return "№ ---";
  }
  return `№ ${dex.toString().padStart(3, "0")}`;
}

export function isEdited(entry: DexEntry): boolean {
  return entry.overridden_fields.length > 0;
}

/** Base stat total: the sum of the six stats, or undefined if any is missing
    (some cosmetic forms carry no stat block — a partial total would mislead). */
export function bst(stats: Record<string, number>): number | undefined {
  const values = STAT_ORDER.map((key) => stats[key]);
  if (values.some((value) => value === undefined)) {
    return undefined;
  }
  return values.reduce((total, value) => total + value, 0);
}

/** A short human label for the kind of an override, for the diff annotations. */
export const FIELD_LABEL: Record<string, string> = {
  types: "Types",
  abilities: "Abilities",
  stats: "Stats",
  learnset: "Learnset",
  evolution: "Evolution",
};
