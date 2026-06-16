import { describe, it, expect } from "vitest";
import {
  axisOrder,
  baseOf,
  cellKey,
  cellMap,
  cycle,
  isCellEdited,
  toOverrides,
} from "./typeChartGrid";
import type { TypeChartCell } from "../types";

/** A cell fixture; defaults to a not-overridden neutral pair. */
function makeCell(overrides: Partial<TypeChartCell> = {}): TypeChartCell {
  return {
    attacker: "Water",
    defender: "Fire",
    multiplier: 1,
    overridden: false,
    base_multiplier: null,
    ...overrides,
  };
}

describe("cycle", () => {
  it("walks 0 → 0.5 → 1 → 2 → 0", () => {
    expect(cycle(0)).toBe(0.5);
    expect(cycle(0.5)).toBe(1);
    expect(cycle(1)).toBe(2);
    expect(cycle(2)).toBe(0);
  });

  it("restarts the cycle for an unknown value (defensive)", () => {
    expect(cycle(4)).toBe(0);
    expect(cycle(0.25)).toBe(0);
  });
});

describe("baseOf", () => {
  it("returns the cell's own multiplier when not overridden", () => {
    expect(baseOf(makeCell({ multiplier: 2 }))).toBe(2);
  });

  it("returns the recorded base when overridden", () => {
    const cell = makeCell({
      multiplier: 2,
      overridden: true,
      base_multiplier: 0.5,
    });
    expect(baseOf(cell)).toBe(0.5);
  });

  it("falls back to the multiplier when overridden but base is null", () => {
    expect(baseOf(makeCell({ overridden: true, base_multiplier: null }))).toBe(
      1,
    );
  });
});

describe("isCellEdited", () => {
  it("is false when the working value equals base", () => {
    expect(isCellEdited(1, makeCell({ multiplier: 1 }))).toBe(false);
  });

  it("is true when the working value differs from base", () => {
    expect(isCellEdited(2, makeCell({ multiplier: 1 }))).toBe(true);
  });

  it("compares against the recorded base, not the current multiplier", () => {
    const cell = makeCell({
      multiplier: 2,
      overridden: true,
      base_multiplier: 0.5,
    });
    // working === base ⇒ not edited, even though the merged multiplier is 2.
    expect(isCellEdited(0.5, cell)).toBe(false);
    expect(isCellEdited(2, cell)).toBe(true);
  });
});

describe("axisOrder", () => {
  it("keeps canonical TYPES order, restricted to present types", () => {
    const cells = [
      makeCell({ attacker: "Water", defender: "Fire" }),
      makeCell({ attacker: "Grass", defender: "Water" }),
    ];
    // Fire, Water, Grass appear in canonical order regardless of cell order.
    expect(axisOrder(cells)).toEqual(["Fire", "Water", "Grass"]);
  });

  it("omits types not present in any cell", () => {
    const cells = [makeCell({ attacker: "Dragon", defender: "Dragon" })];
    expect(axisOrder(cells)).toEqual(["Dragon"]);
  });

  it("appends present-but-unknown types after known ones, sorted (never dropped)", () => {
    const cells = [
      makeCell({ attacker: "Fire", defender: "Stellar" }),
      makeCell({ attacker: "Mystery", defender: "Water" }),
    ];
    // Known types keep canonical order; unknowns (Mystery, Stellar) trail in
    // sorted order — and crucially are NOT dropped.
    expect(axisOrder(cells)).toEqual([
      "Fire",
      "Water",
      "Mystery",
      "Stellar",
    ]);
  });
});

describe("cellMap / cellKey", () => {
  it("indexes cells by attacker|defender", () => {
    const cell = makeCell({ attacker: "Water", defender: "Fire" });
    const map = cellMap([cell]);
    expect(map.get(cellKey("Water", "Fire"))).toBe(cell);
    expect(map.get(cellKey("Fire", "Water"))).toBeUndefined();
  });
});

describe("toOverrides", () => {
  const cells = [
    makeCell({ attacker: "Water", defender: "Fire", multiplier: 2 }),
    makeCell({ attacker: "Fire", defender: "Water", multiplier: 0.5 }),
    makeCell({ attacker: "Normal", defender: "Normal", multiplier: 1 }),
  ];

  it("emits only cells whose working value differs from base", () => {
    const working = new Map<string, number>([
      [cellKey("Water", "Fire"), 0], // base 2 → now 0 (edited)
    ]);
    expect(toOverrides(working, cells)).toEqual([
      { attacker: "Water", defender: "Fire", multiplier: 0 },
    ]);
  });

  it("uses the cell's own multiplier when working has no entry", () => {
    // An already-overridden cell (base differs) is in the payload even with no
    // working edit, because its merged multiplier already differs from base.
    const overriddenCells = [
      makeCell({
        attacker: "Water",
        defender: "Fire",
        multiplier: 0,
        overridden: true,
        base_multiplier: 2,
      }),
    ];
    expect(toOverrides(new Map(), overriddenCells)).toEqual([
      { attacker: "Water", defender: "Fire", multiplier: 0 },
    ]);
  });

  it("drops a cell cycled back to its base (revert ⇒ absent)", () => {
    const overriddenCells = [
      makeCell({
        attacker: "Water",
        defender: "Fire",
        multiplier: 0,
        overridden: true,
        base_multiplier: 2,
      }),
    ];
    const working = new Map<string, number>([
      [cellKey("Water", "Fire"), 2], // back to base ⇒ dropped from payload
    ]);
    expect(toOverrides(working, overriddenCells)).toEqual([]);
  });

  it("returns an empty payload when nothing differs from base", () => {
    expect(toOverrides(new Map(), cells)).toEqual([]);
  });
});
