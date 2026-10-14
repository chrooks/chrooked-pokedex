import { describe, expect, it } from "vitest";
import { teamHoles } from "./teamFit";
import type { DefenseRow } from "./teamMatchups";

function row(type: string, cells: number[]): DefenseRow {
  return {
    type,
    cells,
    weak: cells.filter((m) => m > 1).length,
    resist: cells.filter((m) => m > 0 && m < 1).length,
    immune: cells.filter((m) => m === 0).length,
  };
}

describe("teamHoles", () => {
  const defense = [
    row("Fire", [2, 0.5, 1]), // 1 weak, 1 answer — listed, balanced
    row("Water", [1, 1, 0.5]), // nobody weak — absent
    row("Ice", [4, 1, 1]), // 1 weak, 0 answers — unbalanced, ×4
    row("Ghost", [2, 2, 1]), // 2 weak, 0 answers — unbalanced, widest gap
  ];

  it("lists only rows with a weak member, unbalanced first, widest gap first", () => {
    expect(teamHoles(defense).map((h) => h.type)).toEqual(["Ghost", "Ice", "Fire"]);
  });

  it("carries the counts and the hardest hit with its member", () => {
    const [ghost, ice, fire] = teamHoles(defense);
    expect(ghost).toMatchObject({ weak: 2, answers: 0, isUnbalanced: true, worst: 2, worstIndex: 0 });
    expect(ice).toMatchObject({ worst: 4, worstIndex: 0 });
    expect(fire).toMatchObject({ weak: 1, answers: 1, isUnbalanced: false });
  });

  it("returns nothing for a team with no weaknesses", () => {
    expect(teamHoles([row("Water", [1, 0.5])])).toEqual([]);
  });
});
