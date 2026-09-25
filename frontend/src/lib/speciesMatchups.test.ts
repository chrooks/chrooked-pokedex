import { describe, expect, it } from "vitest";
import { speciesMatchups } from "./speciesMatchups";
import type { TypeChartCell } from "../types";

function cell(attacker: string, defender: string, multiplier: number): TypeChartCell {
  return { attacker, defender, multiplier, overridden: false, base_multiplier: null };
}

const CELLS: TypeChartCell[] = [
  cell("Normal", "Electric", 1), cell("Normal", "Water", 1), cell("Normal", "Ghost", 0),
  cell("Dark", "Electric", 1), cell("Dark", "Water", 1), cell("Dark", "Ghost", 2),
  cell("Electric", "Ghost", 1), cell("Water", "Ghost", 1), cell("Ghost", "Ghost", 2),
];

const types = (members: { type: string }[]) => members.map((m) => m.type);

describe("speciesMatchups with a type-adding ability", () => {
  it("folds Phantom's Ghost into both defense and STAB offense", () => {
    const { defense, offense } = speciesMatchups(["Electric", "Water"], CELLS, "Phantom");
    expect(types(defense.immune)).toContain("Normal");
    expect(types(defense.weak)).toContain("Dark");
    expect(types(offense.strong)).toContain("Ghost");
  });

  it("leaves base typing unchanged without it", () => {
    const { defense, offense } = speciesMatchups(["Electric", "Water"], CELLS, "Levitate");
    expect(types(defense.immune)).not.toContain("Normal");
    expect(types(defense.weak)).not.toContain("Dark");
    expect(types(offense.strong)).not.toContain("Ghost");
  });
});
