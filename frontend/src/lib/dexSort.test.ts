import { describe, it, expect } from "vitest";
import type { DexEntry } from "../types";
import { compareVals, stableMultiSort, type SortKey } from "./dexSort";

function makeEntry(
  name: string,
  types: string[],
  stats: Record<string, number>,
): DexEntry {
  return {
    dex: null,
    chrooked_id: name.toLowerCase(),
    name,
    types,
    abilities: { primary: null, secondary: null, hidden: null },
    stats,
    learnset: [],
    evolution: null,
    evolves_into: [],
    fully_evolved: false,
    overridden_fields: [],
    base: {},
  };
}

const full = (n: number) => ({ hp: n, atk: n, def: n, spa: n, spd: n, spe: n });
const names = (rows: DexEntry[]) => rows.map((row) => row.name);

describe("compareVals", () => {
  it("orders numbers ascending", () => {
    expect(compareVals(1, 2, "number")).toBeLessThan(0);
    expect(compareVals(2, 1, "number")).toBeGreaterThan(0);
    expect(compareVals(2, 2, "number")).toBe(0);
  });
  it("orders strings with natural numeric collation", () => {
    expect(compareVals("a", "b", "string")).toBeLessThan(0);
    expect(compareVals("Item2", "Item10", "string")).toBeLessThan(0);
  });
  it("sends undefined and NaN to the end, never collapsing to 0", () => {
    expect(compareVals(undefined, 5, "number")).toBeGreaterThan(0);
    expect(compareVals(5, undefined, "number")).toBeLessThan(0);
    expect(compareVals(undefined, undefined, "number")).toBe(0);
    expect(compareVals(Number.NaN, 5, "number")).toBeGreaterThan(0);
  });
});

describe("stableMultiSort (ac5)", () => {
  it("sorts by a single numeric key in each direction", () => {
    const rows = [makeEntry("A", ["Fire"], full(100)), makeEntry("B", ["Fire"], full(300)), makeEntry("C", ["Fire"], full(200))];
    const asc: SortKey[] = [{ field: "bst", direction: "asc" }];
    const desc: SortKey[] = [{ field: "bst", direction: "desc" }];
    expect(names(stableMultiSort(rows, asc))).toEqual(["A", "C", "B"]);
    expect(names(stableMultiSort(rows, desc))).toEqual(["B", "C", "A"]);
  });

  it("breaks ties by a secondary key (type asc, then bst desc) and lands missing BST last", () => {
    const e1 = makeEntry("E1", ["Fire"], full(500 / 6)); // bst ~500
    const e2 = makeEntry("E2", ["Fire"], full(600 / 6)); // bst ~600
    const e3 = makeEntry("E3", ["Water"], full(400 / 6)); // bst ~400
    const e4 = makeEntry("E4", ["Fire"], { hp: 50 }); // missing stats -> bst undefined
    const keys: SortKey[] = [
      { field: "types", direction: "asc" },
      { field: "bst", direction: "desc" },
    ];
    // Fire group first (Fire < Water); within Fire by bst desc with missing last.
    expect(names(stableMultiSort([e3, e1, e4, e2], keys))).toEqual(["E2", "E1", "E4", "E3"]);
  });

  it("sends missing values to the end when they are the PRIMARY key, in both directions", () => {
    // abilities sortValue is primary ?? undefined; a null primary is "missing".
    const withAbility = (name: string, primary: string | null): DexEntry => {
      const entry = makeEntry(name, ["Normal"], full(100));
      return { ...entry, abilities: { primary, secondary: null, hidden: null } };
    };
    const rows = [withAbility("none", null), withAbility("blaze", "Blaze"), withAbility("torrent", "Torrent")];
    const asc = stableMultiSort(rows, [{ field: "abilities", direction: "asc" }]);
    const desc = stableMultiSort(rows, [{ field: "abilities", direction: "desc" }]);
    expect(names(asc)).toEqual(["blaze", "torrent", "none"]); // Blaze < Torrent, missing last
    expect(names(desc)).toEqual(["torrent", "blaze", "none"]); // reversed, missing STILL last
  });

  it("is stable: equal rows keep their original order", () => {
    const rows = [makeEntry("first", ["Fire"], full(100)), makeEntry("second", ["Fire"], full(100))];
    const keys: SortKey[] = [{ field: "bst", direction: "asc" }];
    expect(names(stableMultiSort(rows, keys))).toEqual(["first", "second"]);
  });

  it("returns a copy and leaves the input untouched", () => {
    const rows = [makeEntry("A", ["Fire"], full(300)), makeEntry("B", ["Fire"], full(100))];
    const before = names(rows);
    stableMultiSort(rows, [{ field: "bst", direction: "asc" }]);
    expect(names(rows)).toEqual(before);
  });
});

describe("evolution sort", () => {
  const withEvo = (name: string, evolution: DexEntry["evolution"]): DexEntry => ({
    ...makeEntry(name, ["normal"], full(50)),
    evolution,
  });

  it("sorts by evolution level across all method shapes, base mons last", () => {
    const rows = [
      withEvo("Base", null),
      withEvo("Dict", { from: "a", method: { level: 30 } }),
      withEvo("Stone", { from: "b", method: "Fire Stone" }),
      withEvo("Str", { from: "c", method: "Level 9" }),
      withEvo("Detail", {
        from: "d",
        method: {},
        method_detail: { kind: "EVO_LEVEL", param: "16" },
      }),
    ];
    const keys: SortKey[] = [{ field: "evolution", direction: "asc" }];
    expect(names(stableMultiSort(rows, keys))).toEqual([
      "Str",
      "Detail",
      "Dict",
      "Base",
      "Stone",
    ]);
  });
});
