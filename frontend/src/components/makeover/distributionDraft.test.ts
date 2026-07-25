/* ac10 — the CREATE NEW distribution draft ops: slot edit, row removal, dedupe-on-
   add (re-add replaces), and the derived replaces clobber preview. Pure, node env. */

import { describe, it, expect } from "vitest";
import type { DexEntry } from "../../types";
import { addRow, deriveReplaces, removeRow, setSlot, type DistRow } from "./distributionDraft";

function entry(chrooked_id: string, abilities: DexEntry["abilities"]): DexEntry {
  return {
    dex: null,
    chrooked_id,
    name: chrooked_id,
    types: [],
    abilities,
    stats: {},
    learnset: [],
    evolution: null,
    evolves_into: [],
    fully_evolved: false,
    overridden_fields: [],
    base: {},
  };
}

const byId = new Map<string, DexEntry>([
  ["goodra", entry("goodra", { primary: "Sap Sipper", secondary: "Hydration", hidden: "Gooey" })],
  ["sliggoo", entry("sliggoo", { primary: "Sap Sipper", secondary: null, hidden: "Gooey" })],
]);

describe("distribution draft — slot edit", () => {
  it("setSlot changes one row's slot immutably", () => {
    const rows: DistRow[] = [
      { species: "goodra", slot: "primary" },
      { species: "sliggoo", slot: "hidden" },
    ];
    const next = setSlot(rows, 0, "secondary");
    expect(next[0]).toEqual({ species: "goodra", slot: "secondary" });
    expect(next[1]).toEqual({ species: "sliggoo", slot: "hidden" });
    expect(rows[0].slot).toBe("primary"); // original untouched
  });

  it("setSlot out of range is a no-op copy", () => {
    const rows: DistRow[] = [{ species: "goodra", slot: "primary" }];
    expect(setSlot(rows, 5, "hidden")).toEqual(rows);
  });
});

describe("distribution draft — remove", () => {
  it("removeRow drops the row at index", () => {
    const rows: DistRow[] = [
      { species: "goodra", slot: "primary" },
      { species: "sliggoo", slot: "hidden" },
    ];
    expect(removeRow(rows, 0)).toEqual([{ species: "sliggoo", slot: "hidden" }]);
  });
});

describe("distribution draft — add + dedupe", () => {
  it("addRow appends a new species", () => {
    const rows: DistRow[] = [{ species: "goodra", slot: "primary" }];
    const next = addRow(rows, { species: "sliggoo", slot: "hidden" });
    expect(next).toEqual([
      { species: "goodra", slot: "primary" },
      { species: "sliggoo", slot: "hidden" },
    ]);
  });

  it("re-adding a species REPLACES its existing row (dedupe by species)", () => {
    const rows: DistRow[] = [
      { species: "goodra", slot: "primary" },
      { species: "sliggoo", slot: "hidden" },
    ];
    const next = addRow(rows, { species: "goodra", slot: "secondary" });
    expect(next).toEqual([
      { species: "sliggoo", slot: "hidden" },
      { species: "goodra", slot: "secondary" },
    ]);
    expect(next.filter((r) => r.species === "goodra")).toHaveLength(1);
  });
});

describe("distribution draft — deriveReplaces", () => {
  it("returns the species' current ability at that slot", () => {
    expect(deriveReplaces(byId, "goodra", "primary")).toBe("Sap Sipper");
    expect(deriveReplaces(byId, "goodra", "hidden")).toBe("Gooey");
  });

  it("returns null for an empty slot", () => {
    expect(deriveReplaces(byId, "sliggoo", "secondary")).toBeNull();
  });

  it("returns null for an unknown species", () => {
    expect(deriveReplaces(byId, "ghost-mon", "primary")).toBeNull();
  });
});
