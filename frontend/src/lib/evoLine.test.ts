import { describe, expect, it } from "vitest";
import { expandEvoLines } from "./evoLine";
import type { DexEntry } from "../types";

function mon(id: string, from: string | null, into: string[]): DexEntry {
  return {
    chrooked_id: id,
    evolution: from ? { from, method: "Level 16" } : null,
    evolves_into: into.map((to) => ({ to, to_name: to, to_dex: null, method: "Level 16" })),
  } as unknown as DexEntry;
}

const all = [
  mon("bulbasaur", null, ["ivysaur"]),
  mon("ivysaur", "bulbasaur", ["venusaur"]),
  mon("venusaur", "ivysaur", []),
  mon("eevee", null, ["vaporeon", "jolteon"]),
  mon("vaporeon", "eevee", []),
  mon("jolteon", "eevee", []),
  mon("ditto", null, []),
];

describe("expandEvoLines", () => {
  it("pulls in pre-evos and evos from a middle-stage match", () => {
    const got = expandEvoLines([all[1]], all).map((e) => e.chrooked_id);
    expect(got).toEqual(["bulbasaur", "ivysaur", "venusaur"]);
  });

  it("pulls every branch of a branching line", () => {
    const got = expandEvoLines([all[4]], all).map((e) => e.chrooked_id);
    expect(got).toEqual(["eevee", "vaporeon", "jolteon"]);
  });

  it("leaves a lineless mon alone", () => {
    expect(expandEvoLines([all[6]], all).map((e) => e.chrooked_id)).toEqual(["ditto"]);
  });
});
