import { describe, expect, it } from "vitest";
import { bringsNewType, teamTypeSet } from "./teamTypeGap";

describe("teamTypeSet", () => {
  it("collects every type on the team, slugged", () => {
    const set = teamTypeSet([{ types: ["Fire", "Dragon"] }, { types: ["Water", "Ground"] }]);
    expect([...set].sort()).toEqual(["dragon", "fire", "ground", "water"]);
  });

  it("is empty for an empty team", () => {
    expect(teamTypeSet([]).size).toBe(0);
  });
});

describe("bringsNewType", () => {
  const covered = teamTypeSet([{ types: ["Fire", "Dragon"] }, { types: ["Water", "Ground"] }]);

  it("keeps a species with no shared type", () => {
    expect(bringsNewType(["Psychic", "Dark"], covered)).toBe(true);
  });

  it("drops a species sharing even one of two types", () => {
    expect(bringsNewType(["Fire", "Steel"], covered)).toBe(false);
    expect(bringsNewType(["Steel", "Water"], covered)).toBe(false);
  });

  it("matches case-insensitively", () => {
    expect(bringsNewType(["fire"], covered)).toBe(false);
  });

  it("keeps everything when the team covers nothing", () => {
    expect(bringsNewType(["Fire"], new Set())).toBe(true);
  });
});
