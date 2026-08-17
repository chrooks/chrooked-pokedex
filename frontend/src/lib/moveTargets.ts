/* The battlefield semantics of the 12 neutral move targets (schema.MOVE_TARGETS).

   One pattern per preset: which of the six battler slots it involves, and HOW
   (`each` hits them all, `choose` picks one, `random` rolls one, `field` covers
   a side, `varies` is move-dependent). The interactive TargetGrid, the table
   glyph, and the detail row all derive from this table so they cannot drift.

   The grid mirrors the standard triple-battle diagram: three foes across the
   top, the user bottom-left with two allies beside it. "Adjacent" from that
   corner = the two near foes plus the near ally. Pure, no React. */

import { MOVE_TARGETS } from "./format";

export type TargetSlot = "f0" | "f1" | "f2" | "u" | "a1" | "a2";

/** Render order: top row (foes) then bottom row (user + allies). */
export const TARGET_SLOTS: readonly TargetSlot[] = ["f0", "f1", "f2", "u", "a1", "a2"];

export const SLOT_ROLE: Record<TargetSlot, "foe" | "user" | "ally"> = {
  f0: "foe",
  f1: "foe",
  f2: "foe",
  u: "user",
  a1: "ally",
  a2: "ally",
};

export type TargetKind = "each" | "choose" | "random" | "field" | "varies";

export interface TargetPattern {
  kind: TargetKind;
  slots: readonly TargetSlot[];
  /** Short caption, e.g. "all adjacent battlers". */
  caption: string;
}

/** Display names for the preset dropdown, detail rows, and glyph tooltips.
    The raw snake_case ids stay in the data and the filter query language. */
export const TARGET_LABEL: Record<string, string> = {
  selected: "Chosen Target",
  user: "Self",
  both: "Adjacent Foes",
  ally: "An Ally",
  foes_and_ally: "All Adjacent",
  opponent: "Any Foe",
  random: "Random Foe",
  opponents_field: "Foes' Side",
  users_field: "User's Side",
  entire_field: "Entire Field",
  all_battlers: "All Battlers",
  depends: "Varies",
};

export function targetLabel(target: string): string {
  return TARGET_LABEL[target] ?? target;
}

export const TARGET_PATTERNS: Record<string, TargetPattern> = {
  selected: { kind: "choose", slots: ["f0", "f1", "a1"], caption: "one chosen adjacent battler" },
  user: { kind: "each", slots: ["u"], caption: "the user itself" },
  both: { kind: "each", slots: ["f0", "f1"], caption: "each adjacent foe" },
  ally: { kind: "choose", slots: ["a1"], caption: "an adjacent ally" },
  foes_and_ally: { kind: "each", slots: ["f0", "f1", "a1"], caption: "all adjacent battlers" },
  opponent: { kind: "choose", slots: ["f0", "f1", "f2"], caption: "one chosen foe" },
  random: { kind: "random", slots: ["f0", "f1", "f2"], caption: "one random foe" },
  opponents_field: { kind: "field", slots: ["f0", "f1", "f2"], caption: "the foes' side of the field" },
  users_field: { kind: "field", slots: ["u", "a1", "a2"], caption: "the user's side of the field" },
  entire_field: { kind: "field", slots: ["f0", "f1", "f2", "u", "a1", "a2"], caption: "the whole field" },
  all_battlers: { kind: "each", slots: ["f0", "f1", "f2", "u", "a1", "a2"], caption: "every battler, user included" },
  depends: { kind: "varies", slots: [], caption: "varies by the move's effect" },
};

/** Presets a battler click can land on, in tie-break order. Battler-shaped
    presets outrank field/random twins with the same slot set (opponent over
    opponents_field, all_battlers over entire_field); `depends` is dropdown-only
    since no slot set describes it. */
const SNAP_PRIORITY: readonly string[] = [
  "user",
  "ally",
  "both",
  "foes_and_ally",
  "selected",
  "opponent",
  "all_battlers",
  "users_field",
  "opponents_field",
  "entire_field",
  "random",
];

function toggled(pattern: TargetPattern, slot: TargetSlot): Set<TargetSlot> {
  const next = new Set(pattern.slots);
  if (next.has(slot)) next.delete(slot);
  else next.add(slot);
  return next;
}

function distance(slots: readonly TargetSlot[], want: Set<TargetSlot>): number {
  const set = new Set(slots);
  let d = 0;
  for (const s of set) if (!want.has(s)) d += 1;
  for (const s of want) if (!set.has(s)) d += 1;
  return d;
}

/** The preset a click lands on: toggle `slot` in the current preset's pattern,
    then snap to the legal preset whose slot set matches exactly — or, when no
    exact match exists, the nearest OTHER preset by symmetric difference (ties
    broken by SNAP_PRIORITY). Excluding the current preset from the fallback
    keeps every click moving somewhere instead of no-opping back. The Ruleset
    stores targets as a closed enum, so a click can never produce a free-form
    combination — only another legal preset. */
export function snapTarget(current: string, slot: TargetSlot): string {
  const pattern = TARGET_PATTERNS[current] ?? TARGET_PATTERNS.selected;
  const want = toggled(pattern, slot);
  for (const preset of SNAP_PRIORITY) {
    if (distance(TARGET_PATTERNS[preset].slots, want) === 0) return preset;
  }
  // No exact match: land on the nearest preset that LOOKS different from the
  // current one — skipping same-set twins (entire_field vs all_battlers) so the
  // click visibly moves instead of dissolving into an identical pattern.
  const currentSet = new Set(pattern.slots);
  let best = current;
  let bestDistance = Infinity;
  for (const preset of SNAP_PRIORITY) {
    if (distance(TARGET_PATTERNS[preset].slots, currentSet) === 0) continue;
    const d = distance(TARGET_PATTERNS[preset].slots, want);
    if (d < bestDistance) {
      best = preset;
      bestDistance = d;
    }
  }
  return best;
}

/** Every schema target key has a pattern (guarded by the test suite). */
export function patternOf(target: string): TargetPattern {
  return TARGET_PATTERNS[target] ?? TARGET_PATTERNS.depends;
}

export { MOVE_TARGETS };
