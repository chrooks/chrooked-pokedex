import { describe, it, expect } from "vitest";
import {
  axisOrder,
  baseOf,
  cellKey,
  cellMap,
  cycle,
  fitCellSize,
  isCellEdited,
  matchups,
  TC_CELL_MAX,
  TC_CELL_MIN,
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

describe("matchups", () => {
  // A synthetic chart over Fire / Water / Grass with every defensive and
  // offensive bucket represented for the selected type, plus a type that appears
  // only as an attacker (Bug) and one only as a defender (Rock).
  //   Defending Water: Grass→Water ×2 (weak), Fire→Water ×0.5 (resist),
  //     Water→Water ×1 (neutral), Bug→Water ×0 (immune).
  //   Attacking from Water: Water→Fire ×2 (strong), Water→Water ×1 (neutral),
  //     Water→Grass ×0.5 (resisted), Water→Rock ×0 (no effect).
  const cells: TypeChartCell[] = [
    // Defense column for Water (X → Water).
    makeCell({ attacker: "Grass", defender: "Water", multiplier: 2 }),
    makeCell({ attacker: "Fire", defender: "Water", multiplier: 0.5 }),
    makeCell({ attacker: "Water", defender: "Water", multiplier: 1 }),
    makeCell({ attacker: "Bug", defender: "Water", multiplier: 0 }),
    // Offense row for Water (Water → Y).
    makeCell({ attacker: "Water", defender: "Fire", multiplier: 2 }),
    makeCell({ attacker: "Water", defender: "Grass", multiplier: 0.5 }),
    makeCell({ attacker: "Water", defender: "Rock", multiplier: 0 }),
  ];
  const valueOf = (cell: TypeChartCell) => cell.multiplier;
  /** Bucket members are {type, edited}; most assertions only care about names. */
  const names = (members: { type: string }[]) => members.map((m) => m.type);

  it("buckets all four defensive matchups", () => {
    const { defense } = matchups("Water", cells, valueOf);
    expect(names(defense.weak)).toEqual(["Grass"]);
    expect(names(defense.neutral)).toEqual(["Water"]);
    expect(names(defense.resist)).toEqual(["Fire"]);
    expect(names(defense.immune)).toEqual(["Bug"]);
  });

  it("buckets all four offensive matchups", () => {
    const { offense } = matchups("Water", cells, valueOf);
    expect(names(offense.strong)).toEqual(["Fire"]);
    expect(names(offense.neutral)).toEqual(["Water"]);
    expect(names(offense.resisted)).toEqual(["Grass"]);
    expect(names(offense.noEffect)).toEqual(["Rock"]);
  });

  it("orders each bucket by the grid axis, not cell insertion order", () => {
    // Two attackers in the same bucket; axis order is Fire before Grass.
    const ordered: TypeChartCell[] = [
      makeCell({ attacker: "Grass", defender: "Water", multiplier: 2 }),
      makeCell({ attacker: "Fire", defender: "Water", multiplier: 2 }),
    ];
    const { defense } = matchups("Water", ordered, valueOf);
    expect(names(defense.weak)).toEqual(["Fire", "Grass"]);
  });

  it("classifies a type present only as an attacker (offense-only)", () => {
    // Bug appears only as an attacker against Water, never as a defender — it
    // lands in Water's defense buckets, and Water's offense list omits it.
    const { defense, offense } = matchups("Water", cells, valueOf);
    expect(names(defense.immune)).toContain("Bug");
    const allOffense = names([
      ...offense.strong,
      ...offense.neutral,
      ...offense.resisted,
      ...offense.noEffect,
    ]);
    expect(allOffense).not.toContain("Bug");
  });

  it("classifies a type present only as a defender (defense-only)", () => {
    // Rock appears only as a defender (Water → Rock), never as an attacker — it
    // lands in Water's offense buckets, and Water's defense list omits it.
    const { defense, offense } = matchups("Water", cells, valueOf);
    expect(names(offense.noEffect)).toContain("Rock");
    const allDefense = names([
      ...defense.weak,
      ...defense.neutral,
      ...defense.resist,
      ...defense.immune,
    ]);
    expect(allDefense).not.toContain("Rock");
  });

  it("reflects working edits through valueOf (canon mode)", () => {
    // A working override flips Fire→Water from ×0.5 to ×2: Fire moves from the
    // resist bucket into the weak bucket.
    const working = new Map<string, number>([
      [cellKey("Fire", "Water"), 2],
    ]);
    const edited = (cell: TypeChartCell) =>
      working.get(cellKey(cell.attacker, cell.defender)) ?? cell.multiplier;
    const { defense } = matchups("Water", cells, edited);
    expect(names(defense.weak)).toContain("Fire");
    expect(names(defense.resist)).not.toContain("Fire");
  });

  it("flags each member edited per the same rule the grid cell uses", () => {
    // A chart where one incoming matchup is a Ruleset override and one is base.
    const editedCells: TypeChartCell[] = [
      // Grass→Water overridden ×2 (base was ×1) → weak + edited.
      makeCell({
        attacker: "Grass",
        defender: "Water",
        multiplier: 2,
        overridden: true,
        base_multiplier: 1,
      }),
      // Fire→Water base ×0.5 (untouched) → resist + not edited.
      makeCell({ attacker: "Fire", defender: "Water", multiplier: 0.5 }),
      // Water→Fire overridden ×2 (base ×1) → strong + edited (offense side).
      makeCell({
        attacker: "Water",
        defender: "Fire",
        multiplier: 2,
        overridden: true,
        base_multiplier: 1,
      }),
    ];
    const { defense, offense } = matchups("Water", editedCells, valueOf);
    expect(defense.weak).toEqual([{ type: "Grass", edited: true }]);
    expect(defense.resist).toEqual([{ type: "Fire", edited: false }]);
    expect(offense.strong).toEqual([{ type: "Fire", edited: true }]);
  });

  it("returns eight empty buckets for a type absent from the chart", () => {
    const { defense, offense } = matchups("Dragon", cells, valueOf);
    expect(defense).toEqual({
      weak: [],
      neutral: [],
      resist: [],
      immune: [],
    });
    expect(offense).toEqual({
      strong: [],
      neutral: [],
      resisted: [],
      noEffect: [],
    });
  });
});

describe("fitCellSize", () => {
  it("fits both axes: cell = floor(min(W,H)/(ratio + N))", () => {
    // 900px wide, 700px tall, 18 types. Height is the binding axis.
    const { cell, overflow } = fitCellSize({ width: 900, height: 700 }, 18);
    // 700 / (1.2 + 18) = 36.4 → 36
    expect(cell).toBe(36);
    expect(overflow).toBe(false);
  });

  it("clamps to the max in a huge container", () => {
    const { cell } = fitCellSize({ width: 4000, height: 4000 }, 18);
    expect(cell).toBe(TC_CELL_MAX);
  });

  it("clamps to the min and reports overflow in a tiny container", () => {
    const { cell, overflow } = fitCellSize({ width: 120, height: 120 }, 18);
    expect(cell).toBe(TC_CELL_MIN);
    expect(overflow).toBe(true);
  });

  it("keeps the header track proportional to the cell", () => {
    const { cell, head } = fitCellSize({ width: 900, height: 700 }, 18);
    expect(head).toBe(Math.round(cell * 1.2));
  });

  it("falls back to the max cell for a degenerate (unmeasured) box", () => {
    const { cell, overflow } = fitCellSize({ width: 0, height: 0 }, 18);
    expect(cell).toBe(TC_CELL_MAX);
    expect(overflow).toBe(false);
  });
});
