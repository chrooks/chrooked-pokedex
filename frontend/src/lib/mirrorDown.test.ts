import { describe, expect, it } from "vitest";
import { copyDownLearnset, mirrorDownPreview, preEvos } from "./mirrorDown";
import type { AbilitySlots, DexEntry } from "../types";

const ABILITIES: AbilitySlots = { primary: "Sap Sipper", secondary: null, hidden: "Gooey" };

function mon(id: string, name: string, from: string | null): DexEntry {
  return {
    chrooked_id: id,
    name,
    dex: null,
    types: ["Dragon"],
    abilities: ABILITIES,
    stats: {},
    learnset: [],
    evolution: from ? { from, method: "Level 40" } : null,
    evolves_into: [],
    fully_evolved: from !== null,
    overridden_fields: [],
    base: {},
  } as unknown as DexEntry;
}

const goomy = mon("goomy", "Goomy", null);
const sliggoo = mon("sliggoo", "Sliggoo", "goomy");
const goodra = mon("goodra", "Goodra", "sliggoo");
const byId = new Map([goomy, sliggoo, goodra].map((m) => [m.chrooked_id, m]));

describe("preEvos", () => {
  it("walks backward to the base in order", () => {
    expect(preEvos(goodra, byId).map((m) => m.chrooked_id)).toEqual(["goomy", "sliggoo"]);
  });

  it("is empty for a base species", () => {
    expect(preEvos(goomy, byId)).toEqual([]);
  });
});

describe("copyDownLearnset — anchor minus L0", () => {
  it("drops L0 on-evolution rows and sorts by level", () => {
    const anchor = [
      { level: 0, move: "Dragon Pulse" },
      { level: 20, move: "Dragon Breath" },
      { level: 1, move: "Tackle" },
    ];
    expect(copyDownLearnset(anchor)).toEqual([
      { level: 1, move: "Tackle" },
      { level: 20, move: "Dragon Breath" },
    ]);
  });
});

describe("mirrorDownPreview — the whole-line write plan", () => {
  it("gives each pre-evo the anchor kit and the copy-down learnset", () => {
    const kit = {
      types: ["Water", "Dragon"],
      abilities: ABILITIES,
      learnset: [
        { level: 0, move: "Dragon Pulse" },
        { level: 1, move: "Tackle" },
        { level: 20, move: "Dragon Breath" },
      ],
    };
    const rows = mirrorDownPreview(goodra, byId, kit);
    expect(rows.map((r) => r.chrooked_id)).toEqual(["goomy", "sliggoo"]);
    expect(rows[0].types).toEqual(["Water", "Dragon"]);
    expect(rows[0].learnset).toEqual([
      { level: 1, move: "Tackle" },
      { level: 20, move: "Dragon Breath" },
    ]);
    // The stripped L0 is surfaced for the "minus L0" annotation.
    expect(rows[0].strippedL0).toEqual(["Dragon Pulse"]);
  });
});
