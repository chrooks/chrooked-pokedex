import { describe, expect, it } from "vitest";
import { candidateMember, teamFit, teamHoles } from "./teamFit";
import { teamMatchups, type DefenseRow, type TeamMember } from "./teamMatchups";
import { cellMap } from "./typeChartGrid";
import type { DexEntry, TypeChartCell } from "../types";

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

describe("teamFit", () => {
  const cell = (attacker: string, defender: string, multiplier: number): TypeChartCell => ({
    attacker,
    defender,
    multiplier,
    overridden: false,
    base_multiplier: null,
  });
  // Ghost hits Ghost ×2; Ghost and Normal can't touch each other.
  const cells = [cell("Ghost", "Ghost", 2), cell("Ghost", "Normal", 0), cell("Normal", "Ghost", 0)];
  const byKey = cellMap(cells);
  const mon = (id: string, types: string[]): TeamMember => ({ id, name: id, types, ability: null });
  const team = [mon("gengar", ["Ghost"])];
  const before = teamMatchups(team, cells);

  it("scores a Ghost-immune pick: fixed +3, patched +1, covered +1", () => {
    const fit = teamFit(before, mon("snorlax", ["Normal"]), byKey);
    expect(fit).toMatchObject({ score: 5, fixed: ["Ghost"], patched: ["Ghost"], covered: ["Ghost"], opened: [] });
  });

  it("charges a pick that doubles the hole: opened and still unbalanced, −5", () => {
    const fit = teamFit(before, mon("haunter", ["Ghost"]), byKey);
    expect(fit).toMatchObject({ score: -5, opened: ["Ghost"], patched: [], offense: [] });
  });

  it("matches rebuilding the whole matrix with the candidate in it", () => {
    const candidate = mon("snorlax", ["Normal"]);
    const after = teamMatchups([...team, candidate], cells);
    const ghost = after.defense.find((row) => row.type === "Ghost");
    expect(ghost).toMatchObject({ weak: 1, immune: 1 });
    expect(teamFit(before, candidate, byKey).fixed).toEqual(["Ghost"]);
  });
});

describe("candidateMember", () => {
  const entry = {
    chrooked_id: "cofagrigus",
    name: "Cofagrigus",
    types: ["Ghost", "Steel"],
    abilities: { primary: "Mummy", secondary: "Nocturnal", hidden: null },
  } as unknown as DexEntry;

  it("Redux mode counts every ability", () => {
    expect(candidateMember(entry, true).ability).toEqual(["Mummy", "Nocturnal"]);
  });

  it("otherwise uses base typing, as a fresh party slot does", () => {
    expect(candidateMember(entry, false).ability).toBeNull();
  });
});
