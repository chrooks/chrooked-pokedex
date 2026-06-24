/* Pure logic for inline distribution editing in the Learned-by / Used-by tab
   (issue #30). Two entity kinds share one staged-edit model:

   - MOVE: a species' relationship to the move is a learn LEVEL. Editing =
     changing the level; adding = inserting a learnset entry; removing = dropping
     every learnset entry for that move.
   - ABILITY: a species' relationship to the ability is a SLOT (primary /
     secondary / hidden). Editing = moving it to another slot; adding = assigning
     a slot; removing = clearing the slot it occupies.

   D6 — the write wrinkle: `SpeciesOverride.learnset` / `.abilities` are FULL
   replacements (null = "use base"). To change one entry we start from the
   species' MERGED values (`DexEntry.learnset` / `.abilities`), apply the single
   change, and emit the whole array / slots as the Override. The base values for
   the untouched fields are passed through unchanged. This module owns that build
   so it can be unit-tested without React. */

import type {
  AbilitySlots,
  DexEntry,
  LearnsetMove,
  SpeciesOverride,
} from "../types";

export const ABILITY_SLOTS = ["primary", "secondary", "hidden"] as const;
export type AbilitySlot = (typeof ABILITY_SLOTS)[number];

/** A single staged change against one species, keyed by chrooked_id in the tab.
    `kind: "add"` is just a level/slot assignment for a species not currently in
    the list — the build logic treats add and edit identically (both end in a
    present value); only the UI distinguishes them for the dirty/new affordance. */
export type MovePending =
  | { type: "level"; level: number }
  | { type: "remove" };

export type AbilityPending =
  | { type: "slot"; slot: AbilitySlot }
  | { type: "remove" };

/** A name comparison that ignores case + surrounding whitespace. Learnset and
    ability-slot values store DISPLAY names; the viewed entity is identified by
    its display name, so matches must be tolerant of casing drift. */
export function nameEq(a: string, b: string): boolean {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

/** The species' current learn level for `moveName`, or null if it does not
    learn it. When a species lists the move at several levels we surface the
    lowest (the earliest it is learnable), matching the reverse index's
    "appears once" rule. */
export function currentLevel(entry: DexEntry, moveName: string): number | null {
  const levels = entry.learnset
    .filter((m) => nameEq(m.move, moveName))
    .map((m) => m.level);
  if (levels.length === 0) return null;
  return Math.min(...levels);
}

/** The slot holding `abilityName` on this species, or null if none does. */
export function currentSlot(
  entry: DexEntry,
  abilityName: string,
): AbilitySlot | null {
  for (const slot of ABILITY_SLOTS) {
    const value = entry.abilities[slot];
    if (value !== null && nameEq(value, abilityName)) return slot;
  }
  return null;
}

/** Build the learnset Override after applying one pending change for `moveName`.
    Starts from the merged learnset (D6), drops every existing entry for the move,
    then re-adds a single entry at the new level unless the change is a removal.
    The `displayName` is written verbatim so the round-trip keeps the casing the
    rest of the dex shows. */
export function buildLearnsetOverride(
  entry: DexEntry,
  moveName: string,
  pending: MovePending,
): LearnsetMove[] {
  const withoutMove = entry.learnset.filter((m) => !nameEq(m.move, moveName));
  if (pending.type === "remove") return withoutMove;
  // Insert at the new level and keep the list ascending by level. A stable sort
  // mirrors the backend invariant (crud._species_from_payload) so the optimistic
  // UI matches the saved data without waiting for a refetch.
  const next = [...withoutMove, { level: pending.level, move: moveName }];
  return next.sort((a, b) => a.level - b.level);
}

/** Build the abilities Override after applying one pending change for
    `abilityName`. Clears the ability from whatever slot it currently holds, then
    (for a slot assignment) writes it into the chosen slot — which may overwrite
    a different ability already there (the replacement the UI surfaces, D4). */
export function buildAbilitiesOverride(
  entry: DexEntry,
  abilityName: string,
  pending: AbilityPending,
): AbilitySlots {
  // Start from merged slots, immutably.
  const next: AbilitySlots = {
    primary: entry.abilities.primary,
    secondary: entry.abilities.secondary,
    hidden: entry.abilities.hidden,
  };
  // Clear the ability from its existing slot so a slot move never duplicates it.
  for (const slot of ABILITY_SLOTS) {
    if (next[slot] !== null && nameEq(next[slot] as string, abilityName)) {
      next[slot] = null;
    }
  }
  if (pending.type === "slot") {
    next[pending.slot] = abilityName;
  }
  return next;
}

/** The ability a slot assignment would REPLACE on this species, or null if the
    slot is empty or already holds the ability being granted (D4). Used by the UI
    to warn before commit. */
export function replacementInSlot(
  entry: DexEntry,
  abilityName: string,
  slot: AbilitySlot,
): string | null {
  const occupant = entry.abilities[slot];
  if (occupant === null) return null;
  if (nameEq(occupant, abilityName)) return null;
  return occupant;
}

/** Assemble the full move-distribution Override payload for one species (D6):
    base passthrough for stats/types/abilities/evolution, the learnset replaced
    by the edited list. `raw` (if loaded) carries `aka` we must keep. */
export function moveOverridePayload(
  entry: DexEntry,
  raw: SpeciesOverride | null,
  learnset: LearnsetMove[],
): SpeciesOverride {
  return {
    ...passthrough(entry, raw),
    learnset,
  };
}

/** Assemble the full ability-distribution Override payload for one species. */
export function abilityOverridePayload(
  entry: DexEntry,
  raw: SpeciesOverride | null,
  abilities: AbilitySlots,
): SpeciesOverride {
  return {
    ...passthrough(entry, raw),
    abilities,
  };
}

/** The Override fields we carry through UNCHANGED when editing distribution: the
    species keeps whatever it already had for everything but the one list we
    touch. Prefer the raw Override's value (so an existing Override is preserved),
    falling back to the merged value when there is no Override yet. `aka` survives
    the round-trip from the raw Override. */
function passthrough(
  entry: DexEntry,
  raw: SpeciesOverride | null,
): SpeciesOverride {
  return {
    name: entry.name,
    chrooked_id: entry.chrooked_id,
    aka: raw?.aka ?? (entry.dex !== null ? { dex: entry.dex } : {}),
    types: raw?.types ?? null,
    abilities: raw?.abilities ?? null,
    stats: raw?.stats ?? null,
    learnset: raw?.learnset ?? null,
    evolution: raw?.evolution ?? null,
  };
}
