import { describe, expect, it } from "vitest";
import { attackCategory, moveNameProps, type MoveMeta } from "./moveDisplay";

const META: MoveMeta = new Map([
  ["fire punch", { type: "Fire", category: "physical" }],
  ["flamethrower", { type: "Fire", category: "special" }],
  ["quick attack", { type: "Normal", category: "physical" }],
]);

describe("attackCategory", () => {
  it("picks the stronger attacking side, null on a tie", () => {
    expect(attackCategory({ atk: 120, spa: 110 })).toBe("physical");
    expect(attackCategory({ atk: 90, spa: 130 })).toBe("special");
    expect(attackCategory({ atk: 100, spa: 100 })).toBeNull();
  });
});

describe("moveNameProps", () => {
  const stab = new Set(["fire", "fighting"]); // a Fire/Fighting mon

  it("tints typed moves, bolds STAB, italicizes best-offense", () => {
    // Fire + physical, on a physical-attacking Fire type → typed, STAB, offense.
    const p = moveNameProps("Fire Punch", META, stab, "physical");
    expect(p["data-typed"]).toBe(true);
    expect(p["data-stab"]).toBe(true);
    expect(p["data-offense"]).toBe(true);
    expect(p.style).toEqual({ "--type": "var(--type-fire)" });
  });

  it("marks STAB but not offense when the category is the weaker side", () => {
    // Fire + special on a physical attacker → STAB, not offense.
    const p = moveNameProps("Flamethrower", META, stab, "physical");
    expect(p["data-stab"]).toBe(true);
    expect(p["data-offense"]).toBeUndefined();
  });

  it("typed but non-STAB stays untinted-bold", () => {
    const p = moveNameProps("Quick Attack", META, stab, "physical");
    expect(p["data-typed"]).toBe(true);
    expect(p["data-stab"]).toBeUndefined();
    expect(p["data-offense"]).toBe(true); // Normal + physical still italic
  });

  it("returns empty props for an unknown (untyped) move", () => {
    expect(moveNameProps("Mystery Move", META, stab, "physical")).toEqual({});
  });
});
