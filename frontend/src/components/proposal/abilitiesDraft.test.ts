/* ac3/ac4/ac5/ac7 (logic) — the abilities section's pure draft logic: changed
   detection (provisional amber), slot edit (the select), alternative swap, and
   the entry-aware draft→Override merge (read-merge-write, untouched fields kept). */

import { describe, it, expect } from "vitest";
import type { DexEntry, SpeciesOverride } from "../../types";
import {
  applyAlternative,
  editSlot,
  mergeDraft,
  slotChanged,
} from "./abilitiesDraft";

function entry(): DexEntry {
  return {
    dex: 186,
    chrooked_id: "politoed",
    name: "Politoed",
    types: ["Water"],
    abilities: { primary: "Water Absorb", secondary: "Damp", hidden: "Drizzle" },
    stats: {},
    learnset: [],
    evolution: null,
    evolves_into: [],
    fully_evolved: true,
    overridden_fields: [],
    base: {},
  };
}

describe("abilities draft — changed detection (ac3)", () => {
  it("a proposed slot equal to current is not changed", () => {
    expect(
      slotChanged(entry(), { abilities: { primary: "Water Absorb" } }, "primary"),
    ).toBe(false);
  });

  it("a proposed slot differing from current is changed (provisional amber)", () => {
    expect(
      slotChanged(entry(), { abilities: { primary: "Drizzle" } }, "primary"),
    ).toBe(true);
  });

  it("a slot the draft leaves untouched is never changed", () => {
    expect(slotChanged(entry(), { abilities: {} }, "secondary")).toBe(false);
  });
});

describe("abilities draft — editing (ac4)", () => {
  it("editSlot sets a slot immutably", () => {
    const next = editSlot({ abilities: { primary: "A" } }, "secondary", "B");
    expect(next.abilities).toEqual({ primary: "A", secondary: "B" });
  });

  it("editSlot with an empty value clears the slot back to untouched", () => {
    const next = editSlot({ abilities: { primary: "A", hidden: "H" } }, "hidden", "");
    expect(next.abilities.hidden).toBeUndefined();
    expect(next.abilities.primary).toBe("A");
  });
});

describe("abilities draft — alternative swap (ac3)", () => {
  it("a string alternative swaps into the primary slot", () => {
    const next = applyAlternative(
      { abilities: { primary: "Old" } },
      { value: "Swift Swim", rationale: "rain" },
    );
    expect(next.abilities.primary).toBe("Swift Swim");
  });
});

describe("abilities draft — merge (ac5)", () => {
  function raw(): SpeciesOverride {
    return {
      name: "Politoed",
      chrooked_id: "politoed",
      aka: { dex: 186 },
      types: ["Water"],
      abilities: null,
      stats: { spe: 99 },
      learnset: null,
      evolution: null,
    };
  }

  it("writes a complete abilities block, filling untouched slots from current", () => {
    const merged = mergeDraft(raw(), { abilities: { primary: "Drizzle" } }, entry());
    expect(merged.abilities).toEqual({
      primary: "Drizzle",
      secondary: "Damp",
      hidden: "Drizzle",
    });
  });

  it("never clobbers untouched Override fields (stats/types survive)", () => {
    const merged = mergeDraft(raw(), { abilities: { primary: "Drizzle" } }, entry());
    expect(merged.stats).toEqual({ spe: 99 });
    expect(merged.types).toEqual(["Water"]);
    expect(merged.aka).toEqual({ dex: 186 });
  });
});
