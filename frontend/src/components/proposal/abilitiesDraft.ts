/* Pure draft logic for the abilities section — no React, so it is unit-tested in
   the project's node test environment. Drives the abilities renderer's edits,
   alternative swaps, and the draft→Override merge. */

import type {
  AbilityDraft,
  AbilitySlots,
  DexEntry,
  ProposalAlternative,
  SpeciesOverride,
} from "../../types";

export const ABILITY_SLOTS = ["primary", "secondary", "hidden"] as const;
export type AbilitySlot = (typeof ABILITY_SLOTS)[number];

/** The proposed value for a slot, or undefined when the draft keeps it as-is. */
export function proposedSlot(
  draft: AbilityDraft | null,
  slot: AbilitySlot,
): string | undefined {
  return draft?.abilities[slot];
}

/** The current (merged) value of a slot for the current-column display. */
export function currentSlot(entry: DexEntry, slot: AbilitySlot): string | null {
  return entry.abilities[slot];
}

/** Whether the proposed slot differs from the current value (drives provisional
    amber). A slot the draft leaves untouched (undefined) is never "changed". */
export function slotChanged(
  entry: DexEntry,
  draft: AbilityDraft | null,
  slot: AbilitySlot,
): boolean {
  const proposed = proposedSlot(draft, slot);
  if (proposed === undefined) return false;
  return proposed !== (currentSlot(entry, slot) ?? "");
}

/** Edit one proposed slot, returning the next draft (immutable). An empty value
    clears that slot back to "untouched". */
export function editSlot(
  draft: AbilityDraft | null,
  slot: AbilitySlot,
  value: string,
): AbilityDraft {
  const next: AbilityDraft = { abilities: { ...(draft?.abilities ?? {}) } };
  if (value.trim() === "") {
    delete next.abilities[slot];
  } else {
    next.abilities[slot] = value;
  }
  return next;
}

/** Swap an alternative into the draft's primary slot. An ability alternative is
    a bare ability name (string); the model offers alternative primary picks. */
export function applyAlternative(
  draft: AbilityDraft | null,
  alt: ProposalAlternative,
): AbilityDraft {
  if (typeof alt.value === "string") {
    return editSlot(draft, "primary", alt.value);
  }
  // Defensive: an object-shaped alternative {slot, value} also works.
  if (alt.value !== null && typeof alt.value === "object") {
    const v = alt.value as { slot?: AbilitySlot; value?: string };
    if (v.slot && typeof v.value === "string") {
      return editSlot(draft, v.slot, v.value);
    }
  }
  return draft ?? { abilities: {} };
}

/** Merge the curated abilities draft into the raw Override (read-merge-write).
    Only the `abilities` field is touched; every other Override field is carried
    through untouched. The proposed block fills each slot from the draft, falling
    back to the current merged value for an untouched slot, so the written block
    is complete (the loader expects all three keys). */
export function mergeDraft(
  raw: SpeciesOverride,
  draft: AbilityDraft,
  entry: DexEntry,
): SpeciesOverride {
  const merged: AbilitySlots = {
    primary: draft.abilities.primary ?? currentSlot(entry, "primary"),
    secondary: draft.abilities.secondary ?? currentSlot(entry, "secondary"),
    hidden: draft.abilities.hidden ?? currentSlot(entry, "hidden"),
  };
  return { ...raw, abilities: merged };
}
