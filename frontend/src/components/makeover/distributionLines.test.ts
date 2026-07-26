/* The by-evo-line grouping + include-set ops: fold members into families, rank by
   first appearance, slider top-K, and the toggle/all/none set ops that keep
   included.size in sync with the slider K. Pure, node env. Mirrors
   distributionDraft.test.ts. */

import { describe, it, expect } from "vitest";
import type { DexEntry } from "../../types";
import {
  allLineIds,
  groupByLine,
  includedMemberCount,
  lineIdOf,
  toggleIncluded,
  topLineIds,
} from "./distributionLines";

/** A minimal dex entry carrying only the fields expandEvoLines walks. */
function mon(
  chrooked_id: string,
  edges: { from?: string; into?: string[] } = {},
): DexEntry {
  return {
    chrooked_id,
    name: chrooked_id,
    evolution: edges.from ? { from: edges.from, method: "Level 16" } : null,
    evolves_into: (edges.into ?? []).map((to) => ({
      to,
      to_name: to,
      to_dex: null,
      method: "Level 16",
    })),
  } as unknown as DexEntry;
}

// diglett -> dugtrio (two-stage), bulbasaur -> ivysaur -> venusaur (three-stage),
// tauros (single-stage). Dex order is the map insertion order below.
const byId = new Map<string, DexEntry>([
  ["diglett", mon("diglett", { into: ["dugtrio"] })],
  ["dugtrio", mon("dugtrio", { from: "diglett" })],
  ["bulbasaur", mon("bulbasaur", { into: ["ivysaur"] })],
  ["ivysaur", mon("ivysaur", { from: "bulbasaur", into: ["venusaur"] })],
  ["venusaur", mon("venusaur", { from: "ivysaur" })],
  ["tauros", mon("tauros")],
]);

const rows = (...ids: string[]) => ids.map((species) => ({ species }));

describe("lineIdOf", () => {
  it("folds every family member to one stable key", () => {
    expect(lineIdOf("diglett", byId)).toBe(lineIdOf("dugtrio", byId));
    expect(lineIdOf("bulbasaur", byId)).toBe(lineIdOf("venusaur", byId));
  });

  it("gives distinct families distinct keys", () => {
    expect(lineIdOf("diglett", byId)).not.toBe(lineIdOf("bulbasaur", byId));
  });

  it("treats an unknown species as its own line", () => {
    expect(lineIdOf("missingno", byId)).toBe("missingno");
  });
});

describe("groupByLine", () => {
  it("folds members of the same family into one group", () => {
    const groups = groupByLine(rows("diglett", "dugtrio", "tauros"), byId);
    expect(groups).toHaveLength(2);
    expect(groups[0].members).toEqual(["diglett", "dugtrio"]);
    expect(groups[1].members).toEqual(["tauros"]);
  });

  it("ranks lines by first appearance (min member index)", () => {
    // tauros appears first, then the diglett line — rank follows first sight.
    const groups = groupByLine(rows("tauros", "dugtrio", "diglett"), byId);
    expect(groups.map((g) => g.rank)).toEqual([0, 1]);
    expect(groups[0].members).toEqual(["tauros"]);
    // members re-ordered to dex order for the label even though dugtrio came first.
    expect(groups[1].members).toEqual(["diglett", "dugtrio"]);
    expect(groups[1].lineId).toBe(lineIdOf("diglett", byId));
  });

  it("keeps the family id when only some members are present", () => {
    const partial = groupByLine(rows("venusaur"), byId);
    expect(partial).toHaveLength(1);
    expect(partial[0].members).toEqual(["venusaur"]);
    // same stable id as the whole family would produce
    expect(partial[0].lineId).toBe(lineIdOf("bulbasaur", byId));
  });

  it("dedupes a species listed twice", () => {
    const groups = groupByLine(rows("diglett", "diglett"), byId);
    expect(groups[0].members).toEqual(["diglett"]);
  });
});

describe("topLineIds (slider top-K)", () => {
  const groups = groupByLine(rows("tauros", "diglett", "bulbasaur"), byId);

  it("returns the first k line ids by rank", () => {
    expect(topLineIds(groups, 2)).toEqual([groups[0].lineId, groups[1].lineId]);
  });

  it("clamps k to [0, length]", () => {
    expect(topLineIds(groups, 0)).toEqual([]);
    expect(topLineIds(groups, 99)).toEqual(allLineIds(groups));
    expect(topLineIds(groups, -5)).toEqual([]);
  });
});

describe("include-set ops keep K in sync with the slider", () => {
  const groups = groupByLine(rows("tauros", "diglett", "bulbasaur"), byId);

  it("a slider move sets included to exactly the top-K (size === K)", () => {
    const included = new Set(topLineIds(groups, 2));
    expect(included.size).toBe(2);
  });

  it("toggleIncluded adds and removes immutably, changing size by one", () => {
    const start = new Set(topLineIds(groups, 1)); // size 1
    const added = toggleIncluded(start, groups[2].lineId);
    expect(added.size).toBe(2);
    expect(start.size).toBe(1); // original untouched
    const removed = toggleIncluded(added, groups[2].lineId);
    expect(removed.size).toBe(1);
  });

  it("all/none map to every / no line id", () => {
    expect(new Set(allLineIds(groups)).size).toBe(3);
    expect(new Set<string>().size).toBe(0);
  });
});

describe("includedMemberCount", () => {
  const groups = groupByLine(rows("diglett", "dugtrio", "bulbasaur", "tauros"), byId);

  it("counts mons of included lines only", () => {
    const all = new Set(allLineIds(groups));
    expect(includedMemberCount(groups, all)).toBe(4); // diglett+dugtrio+bulbasaur+tauros
    const digOnly = new Set([lineIdOf("diglett", byId)]);
    expect(includedMemberCount(groups, digOnly)).toBe(2);
    expect(includedMemberCount(groups, new Set())).toBe(0);
  });
});
