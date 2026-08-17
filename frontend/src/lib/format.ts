/* Display helpers: stat labels/order, type slugs, dex-number formatting, and
   the base→now diff for overridden stats. Pure functions, no React. */

import type { Ability, DexEntry, Move } from "../types";

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

/** A flag id as its display tag: "contact" -> "Contact", "high_crit" ->
    "High Crit". Display-only — the raw id stays in the data and filters. */
export function flagLabel(flag: string): string {
  return flag
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** Neutral move targets the Ruleset models (mirrors schema.MOVE_TARGETS), ordered
    most-common first for the Move editor's select. */
export const MOVE_TARGETS = [
  "selected",
  "user",
  "both",
  "ally",
  "opponent",
  "foes_and_ally",
  "random",
  "opponents_field",
  "users_field",
  "entire_field",
  "all_battlers",
  "depends",
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

/** True when the Ruleset has touched this ability (overridden a base field or
    created it outright). Same rule as {@link isEdited} for the dex — a single
    edited ⇔ overridden_fields-nonempty contract across both surfaces. */
export function isAbilityEdited(ability: Ability): boolean {
  return ability.overridden_fields.length > 0;
}

/** Short labels for the ability diff annotations. */
export const ABILITY_FIELD_LABEL: Record<string, string> = {
  name: "Name",
  description: "Description",
};

/** The Abilities tab's three-way edited filter, mirroring the dex's edited
    toggle but with an explicit "not edited" option for browsing base-only
    abilities. */
export type AbilityEditedFilter = "all" | "edited" | "base";

/** Whether an ability passes the current edited filter. Pure so the tab can
    `list.filter(...)` and the predicate is unit-tested independently. */
export function matchesAbilityEditedFilter(
  ability: Ability,
  filter: AbilityEditedFilter,
): boolean {
  if (filter === "edited") return isAbilityEdited(ability);
  if (filter === "base") return !isAbilityEdited(ability);
  return true;
}

/** True when the Ruleset has touched this move (overridden a base field or
    created it outright). Same rule as {@link isEdited}/{@link isAbilityEdited} —
    a single edited ⇔ overridden_fields-nonempty contract across all surfaces. */
export function isMoveEdited(move: Move): boolean {
  return move.overridden_fields.length > 0;
}

/** Short labels for the move diff annotations, keyed by {@link MoveField}. */
export const MOVE_FIELD_LABEL: Record<string, string> = {
  name: "Name",
  type: "Type",
  category: "Category",
  power: "Power",
  accuracy: "Accuracy",
  pp: "PP",
  description: "Description",
  effect: "Effect",
  argument: "Argument",
  additional_effects: "Added effects",
  flags: "Flags",
  priority: "Priority",
  target: "Target",
};

/** The Moves tab's three-way edited filter, mirroring the abilities tab's. */
export type MoveEditedFilter = "all" | "edited" | "base";

/** Whether a move passes the current edited filter. Pure so the tab can
    `list.filter(...)` and the predicate is unit-tested independently. */
export function matchesMoveEditedFilter(
  move: Move,
  filter: MoveEditedFilter,
): boolean {
  if (filter === "edited") return isMoveEdited(move);
  if (filter === "base") return !isMoveEdited(move);
  return true;
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
