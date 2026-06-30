/* Build an overrides-only SpeciesOverride for a single right-click table edit.

   Same discipline as the full SpeciesEditor: the Ruleset stores only fields that
   differ from base. These builders patch ONE field on top of the species' raw
   Override (or a fresh skeleton when none exists), leaving every other field
   verbatim, and drop the patched field back to null when it equals base. */

import type { AbilitySlots, DexEntry, SpeciesOverride } from "../types";
import type { StatKey } from "./format";

export type AbilitySlot = keyof AbilitySlots;

export type InlineEdit =
  | { kind: "stat"; key: StatKey; value: number }
  | { kind: "types"; type1: string; type2: string }
  | { kind: "ability"; slot: AbilitySlot; name: string };

/** The columns a right-click can edit, with the cell each maps to. */
const NULL_OVERRIDE = {
  types: null,
  abilities: null,
  stats: null,
  learnset: null,
  evolution: null,
} as const;

function skeleton(entry: DexEntry, raw: SpeciesOverride | null): SpeciesOverride {
  return (
    raw ?? {
      name: entry.name,
      chrooked_id: entry.chrooked_id,
      aka: entry.dex !== null ? { dex: entry.dex } : {},
      ...NULL_OVERRIDE,
    }
  );
}

// --- base lookups (mirror SpeciesEditor) ------------------------------------ #

function baseStat(entry: DexEntry, key: StatKey): number | undefined {
  return entry.base.stats?.[key] ?? entry.stats[key];
}

function baseTypes(entry: DexEntry): string[] {
  return entry.base.types ?? entry.types;
}

function baseSlot(entry: DexEntry, slot: AbilitySlot): string | null {
  // base.abilities is the full base snapshot only when abilities was overridden;
  // otherwise the merged value IS base.
  if (entry.base.abilities) return entry.base.abilities[slot];
  return entry.abilities[slot];
}

// --- the per-field patch ----------------------------------------------------- #

export function applyInlineEdit(
  entry: DexEntry,
  raw: SpeciesOverride | null,
  edit: InlineEdit,
): SpeciesOverride {
  const ov = skeleton(entry, raw);

  if (edit.kind === "stat") {
    const stats = { ...(ov.stats ?? {}) };
    if (edit.value === baseStat(entry, edit.key)) delete stats[edit.key];
    else stats[edit.key] = edit.value;
    return { ...ov, stats: Object.keys(stats).length ? stats : null };
  }

  if (edit.kind === "types") {
    const list = [edit.type1, edit.type2].map((t) => t.trim()).filter(Boolean);
    const base = baseTypes(entry);
    const same = list.length === base.length && list.every((t, i) => t === base[i]);
    return { ...ov, types: same ? null : list };
  }

  // ability: a whole-block Override; a slot is null when it falls through to base.
  const block: AbilitySlots = ov.abilities ?? { primary: null, secondary: null, hidden: null };
  const value = edit.name.trim();
  const next: AbilitySlots = {
    ...block,
    [edit.slot]: value !== "" && value !== (baseSlot(entry, edit.slot) ?? "") ? value : null,
  };
  const allNull = (["primary", "secondary", "hidden"] as const).every((s) => next[s] == null);
  return { ...ov, abilities: allNull ? null : next };
}
