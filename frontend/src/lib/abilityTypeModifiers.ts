/* Franchise-mechanic knowledge, not Ruleset data: abilities that change how
   much damage the holder takes from a given attacking type. Keyed lowercase so
   lookups are case-insensitive against whatever casing the Ruleset stores.

   ponytail: covers the common immunity/resist abilities, not every ability in
   the games (Wonder Guard's "only supereffective moves land" and contact-only
   abilities like Fluffy aren't representable as a per-type multiplier). Add a
   new entry here when a species relies on one that's missing. */

export interface AbilityTypeModifier {
  /** Types the holder takes zero damage from, regardless of the type chart. */
  immuneTo?: string[];
  /** Flat multiplier applied on top of the combined type-chart result. */
  multiplier?: Partial<Record<string, number>>;
  /** Multiplier applied whenever the combined result is already supereffective (>1). */
  supereffectiveMultiplier?: number;
}

const ABILITY_TYPE_MODIFIERS: Record<string, AbilityTypeModifier> = {
  levitate: { immuneTo: ["Ground"] },
  "flash fire": { immuneTo: ["Fire"] },
  "water absorb": { immuneTo: ["Water"] },
  "storm drain": { immuneTo: ["Water"] },
  "dry skin": { immuneTo: ["Water"], multiplier: { Fire: 1.25 } },
  "volt absorb": { immuneTo: ["Electric"] },
  "lightning rod": { immuneTo: ["Electric"] },
  "motor drive": { immuneTo: ["Electric"] },
  "sap sipper": { immuneTo: ["Grass"] },
  "earth eater": { immuneTo: ["Ground"] },
  "well-baked body": { immuneTo: ["Fire"] },
  // Custom Ruleset abilities that grant a type immunity (immunity encoded only
  // in the ability's prose description, so it's mirrored here by hand). Add a new
  // one whenever the Ruleset introduces another type-immunity ability.
  aerodynamic: { immuneTo: ["Flying"] }, // "Draws Flying moves"
  flytrap: { immuneTo: ["Bug"] }, // "Bug immune"
  mountaineer: { immuneTo: ["Rock"] }, // "Immune to Rock moves and Stealth Rock"
  updraft: { immuneTo: ["Ground"] }, // "Ground immune"
  "singing sands": { immuneTo: ["Ground"] }, // "Immune to Ground-type moves"
  immunity: { immuneTo: ["Poison"] }, // "Immune to Poison-type moves"
  "pastel veil": { immuneTo: ["Poison"] }, // "Immune to Poison-type moves"
  "poison heal": { immuneTo: ["Poison"] }, // "Immune to Poison-type moves"
  "thermal exchange": { immuneTo: ["Fire"] }, // "Immune to Fire moves"
  "thick fat": { multiplier: { Fire: 0.5, Ice: 0.5 } },
  heatproof: { multiplier: { Fire: 0.5 } },
  "water bubble": { multiplier: { Fire: 0.5 } },
  "purifying salt": { multiplier: { Ghost: 0.5 } },
  permafrost: { supereffectiveMultiplier: 0.75 },
  filter: { supereffectiveMultiplier: 0.75 },
  "solid rock": { supereffectiveMultiplier: 0.75 },
  "prism armor": { supereffectiveMultiplier: 0.75 },
};

/** True iff this ability changes at least one type matchup — drives whether
    the toggle is worth offering at all for a given slot. */
export function hasTypeModifier(ability: string | null): boolean {
  if (!ability) return false;
  return ability.toLowerCase() in ABILITY_TYPE_MODIFIERS;
}

/** Apply the selected ability's effect to a combined (already both-types-
    multiplied) defensive multiplier for one attacking `type`. `ability` null
    or unrecognized is a no-op. */
export function applyAbilityModifier(
  combined: number,
  type: string,
  ability: string | null,
): number {
  if (!ability) return combined;
  const mod = ABILITY_TYPE_MODIFIERS[ability.toLowerCase()];
  if (!mod) return combined;
  if (mod.immuneTo?.includes(type)) return 0;
  let value = combined;
  const flat = mod.multiplier?.[type];
  if (flat !== undefined) value *= flat;
  if (mod.supereffectiveMultiplier !== undefined && value > 1) {
    value *= mod.supereffectiveMultiplier;
  }
  return value;
}
