import { describe, expect, it } from "vitest";
import { cellMap } from "./typeChartGrid";
import {
  cellTooltip,
  isUnbalanced,
  memberDefense,
  memberOffense,
  multBucket,
  multGlyph,
  multVerdict,
  teamMatchups,
  type TeamMember,
} from "./teamMatchups";
import type { TypeChartCell } from "../types";

/** A tiny hand-built chart. Only the pairs the tests read are present, so
    axisOrder derives {Fire, Water, Grass, Ground, Flying}. */
function cell(attacker: string, defender: string, multiplier: number): TypeChartCell {
  return { attacker, defender, multiplier, overridden: false, base_multiplier: null };
}

const CELLS: TypeChartCell[] = [
  cell("Ground", "Flying", 0),
  cell("Ground", "Water", 1),
  cell("Ground", "Fire", 2),
  cell("Fire", "Grass", 2),
  cell("Fire", "Water", 0.5),
  cell("Water", "Fire", 2),
  cell("Water", "Grass", 0.5),
];

const BY_KEY = cellMap(CELLS);

const waterFlying: TeamMember = { id: "gyarados", name: "Gyarados", types: ["Water", "Flying"], ability: null };
const waterLevitate: TeamMember = { id: "floater", name: "Floater", types: ["Water"], ability: "Levitate" };
const waterGrass: TeamMember = { id: "ludicolo", name: "Ludicolo", types: ["Water", "Grass"], ability: null };

describe("memberDefense", () => {
  it("multiplies both of a member's types together", () => {
    // Ground → Water(×1) × Flying(×0) = 0: immune by typing.
    expect(memberDefense(waterFlying, "Ground", BY_KEY)).toBe(0);
  });

  it("folds in a Levitate-style ability to zero out a whole column", () => {
    // Ground → Water is ×1 by chart, but Levitate makes the holder immune.
    expect(memberDefense(waterLevitate, "Ground", BY_KEY)).toBe(0);
  });

  it("returns the chart value when no ability applies", () => {
    // Fire → Water(×0.5); Flying has no Fire cell so it is skipped, combined 0.5.
    expect(memberDefense(waterFlying, "Fire", BY_KEY)).toBe(0.5);
  });

  it("folds in Permafrost to halve a super-effective hit", () => {
    // Water → Fire is ×2 by chart; Permafrost cuts super-effective hits in half.
    const permafrost: TeamMember = { id: "p", name: "P", types: ["Fire"], ability: "Permafrost" };
    expect(memberDefense(permafrost, "Water", BY_KEY)).toBe(1);
  });

  it("folds in Thermal Exchange to zero out the Fire column", () => {
    const baxcalibur: TeamMember = { id: "b", name: "B", types: ["Grass"], ability: "Thermal Exchange" };
    expect(memberDefense(baxcalibur, "Fire", BY_KEY)).toBe(0);
  });

  it("returns null when the chart has no data for the member's types", () => {
    expect(memberDefense({ id: "x", name: "X", types: ["Bug"], ability: null }, "Fire", BY_KEY)).toBeNull();
  });
});

describe("memberOffense", () => {
  it("takes the best STAB of a dual-type attacker", () => {
    // Water→Fire(×2), Grass has no Fire cell → best is ×2.
    expect(memberOffense(waterGrass, "Fire", BY_KEY)).toBe(2);
  });

  it("uses the single available type when the other has no cell", () => {
    // Water→Grass(×0.5), Grass→Grass has no cell → best is ×0.5.
    expect(memberOffense(waterGrass, "Grass", BY_KEY)).toBe(0.5);
  });
});

describe("teamMatchups totals", () => {
  it("counts weak/resist/immune per row like tectonic's DefTotalCell", () => {
    const { defense } = teamMatchups([waterGrass, waterLevitate], CELLS);
    const ground = defense.find((r) => r.type === "Ground");
    // Ground: Water/Grass → ×1 (water cell only); Levitate → immune ×0.
    expect(ground?.cells).toEqual([1, 0]);
    expect(ground).toMatchObject({ weak: 0, resist: 0, immune: 1 });
  });

  it("counts super/resist per row like tectonic's AtkTotalCell (no-effect resists)", () => {
    const { offense } = teamMatchups([waterGrass], CELLS);
    const fire = offense.find((r) => r.type === "Fire");
    expect(fire).toMatchObject({ strong: 1, resist: 0 });
    const grass = offense.find((r) => r.type === "Grass");
    expect(grass).toMatchObject({ strong: 0, resist: 1 });
  });
});

describe("cell language", () => {
  it("buckets multipliers on the tectonic color scale", () => {
    expect(multBucket(4)).toBe("hyper");
    expect(multBucket(2)).toBe("super");
    expect(multBucket(1)).toBe("neutral");
    expect(multBucket(0.5)).toBe("not-very");
    expect(multBucket(0.25)).toBe("barely");
    expect(multBucket(0)).toBe("immune");
  });

  it("renders fraction glyphs and blanks neutral", () => {
    expect(multGlyph(1)).toBe("");
    expect(multGlyph(0.5)).toBe("½");
    expect(multGlyph(0.25)).toBe("¼");
    expect(multGlyph(0.125)).toBe("⅛");
    expect(multGlyph(1.5)).toBe("³⁄₂");
    expect(multGlyph(0)).toBe("0");
    expect(multGlyph(4)).toBe("4");
  });

  it("speaks the verdict on the ≥4 / ≥2 tooltip scale", () => {
    expect(multVerdict(4)).toBe("Hyper Effective");
    expect(multVerdict(2)).toBe("Super Effective");
    expect(multVerdict(1)).toBe("Normal Effectiveness");
    expect(multVerdict(0.5)).toBe("Not Very Effective");
    expect(multVerdict(0.25)).toBe("Barely Effective");
    expect(multVerdict(0)).toBe("No Effect");
  });

  it("formats the full tooltip as Atk → Def = verdict", () => {
    expect(cellTooltip("Fire", "Water", 0.5)).toBe("Fire → Water = Not Very Effective");
  });
});

describe("isUnbalanced", () => {
  const row = (weak: number, resist: number, immune: number) => ({
    type: "Fire",
    cells: [],
    weak,
    resist,
    immune,
  });

  it("flags a row when weaknesses outnumber answers", () => {
    expect(isUnbalanced(row(2, 1, 0))).toBe(true);
    expect(isUnbalanced(row(3, 0, 0))).toBe(true);
  });

  it("stays quiet when answers cover the weaknesses", () => {
    expect(isUnbalanced(row(2, 1, 1))).toBe(false);
    expect(isUnbalanced(row(1, 0, 1))).toBe(false);
    expect(isUnbalanced(row(0, 0, 0))).toBe(false);
  });
});
