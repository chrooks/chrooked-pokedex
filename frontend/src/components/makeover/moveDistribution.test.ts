/* The move-distribution draft ops: level edit, row removal, and dedupe-on-add
   (re-add replaces). Pure, node env. Mirrors distributionDraft.test.ts. */

import { describe, it, expect } from "vitest";
import {
  addRow,
  deriveCurrentLevel,
  removeRow,
  setLevel,
  type MoveDistRow,
} from "./moveDistribution";
import type { DexEntry } from "../../types";

function mon(id: string, learnset: { level: number; move: string }[]): DexEntry {
  return { chrooked_id: id, learnset } as unknown as DexEntry;
}

describe("move distribution draft — level edit", () => {
  it("setLevel changes one row's level immutably", () => {
    const rows: MoveDistRow[] = [
      { species: "goodra", level: 1 },
      { species: "sliggoo", level: 20 },
    ];
    const next = setLevel(rows, 0, 40);
    expect(next[0]).toEqual({ species: "goodra", level: 40 });
    expect(next[1]).toEqual({ species: "sliggoo", level: 20 });
    expect(rows[0].level).toBe(1); // original untouched
  });

  it("setLevel out of range is a no-op copy", () => {
    const rows: MoveDistRow[] = [{ species: "goodra", level: 1 }];
    expect(setLevel(rows, 5, 30)).toEqual(rows);
  });
});

describe("move distribution draft — remove", () => {
  it("removeRow drops the row at index", () => {
    const rows: MoveDistRow[] = [
      { species: "goodra", level: 1 },
      { species: "sliggoo", level: 20 },
    ];
    expect(removeRow(rows, 0)).toEqual([{ species: "sliggoo", level: 20 }]);
  });
});

describe("move distribution draft — add + dedupe", () => {
  it("addRow appends a new species", () => {
    const rows: MoveDistRow[] = [{ species: "goodra", level: 1 }];
    const next = addRow(rows, { species: "sliggoo", level: 20 });
    expect(next).toEqual([
      { species: "goodra", level: 1 },
      { species: "sliggoo", level: 20 },
    ]);
  });

  it("re-adding a species REPLACES its existing row (dedupe by species)", () => {
    const rows: MoveDistRow[] = [
      { species: "goodra", level: 1 },
      { species: "sliggoo", level: 20 },
    ];
    const next = addRow(rows, { species: "goodra", level: 50 });
    expect(next).toEqual([
      { species: "sliggoo", level: 20 },
      { species: "goodra", level: 50 },
    ]);
    expect(next.filter((r) => r.species === "goodra")).toHaveLength(1);
  });
});

describe("deriveCurrentLevel", () => {
  const byId = new Map<string, DexEntry>([
    ["goodra", mon("goodra", [{ level: 1, move: "Tackle" }, { level: 20, move: "Ice Beam" }])],
    ["ditto", mon("ditto", [])],
  ]);

  it("returns the level when the species already learns the move", () => {
    expect(deriveCurrentLevel(byId, "goodra", "Ice Beam")).toBe(20);
  });

  it("returns null when the species does not learn the move", () => {
    expect(deriveCurrentLevel(byId, "goodra", "Surf")).toBeNull();
  });

  it("returns null for an unknown species", () => {
    expect(deriveCurrentLevel(byId, "mew", "Tackle")).toBeNull();
  });

  it("finds an L0 move (0 is a real level, not falsy-null)", () => {
    const b = new Map<string, DexEntry>([
      ["x", mon("x", [{ level: 0, move: "Evo Move" }])],
    ]);
    expect(deriveCurrentLevel(b, "x", "Evo Move")).toBe(0);
  });
});
