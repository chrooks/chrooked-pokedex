import { describe, expect, it } from "vitest";
import { applyAbilityModifier, effectiveTypes, hasTypeModifier } from "./abilityTypeModifiers";

describe("effectiveTypes", () => {
  it("adds Phantom's Ghost on top of the species' two types", () => {
    expect(effectiveTypes(["Electric", "Water"], "Phantom")).toEqual(["Electric", "Water", "Ghost"]);
  });

  it("does not duplicate a type the species already has (case-insensitive)", () => {
    expect(effectiveTypes(["ghost", "Poison"], "phantom")).toEqual(["ghost", "Poison"]);
  });

  it("returns the species' types for a null or non-type-adding ability", () => {
    expect(effectiveTypes(["Electric", "Water"], null)).toEqual(["Electric", "Water"]);
    expect(effectiveTypes(["Electric", "Water"], "Levitate")).toEqual(["Electric", "Water"]);
  });

  it("returns a new array and never mutates the input", () => {
    const types = ["Electric", "Water"];
    expect(effectiveTypes(types, null)).not.toBe(types);
    effectiveTypes(types, "Phantom");
    expect(types).toEqual(["Electric", "Water"]);
  });

  it("offers Phantom as a matchup-altering ability toggle", () => {
    expect(hasTypeModifier("Phantom")).toBe(true);
  });
});

describe("applyAbilityModifier", () => {
  it("makes Nocturnal and Witching Hour Dark-immune", () => {
    expect(applyAbilityModifier(2, "Dark", "Nocturnal")).toBe(0);
    expect(applyAbilityModifier(1, "Ground", "Witching Hour")).toBe(0);
  });

  it("Redux mode folds every listed ability in at once", () => {
    const all = ["Nocturnal", "Levitate", "Thick Fat"];
    expect(applyAbilityModifier(2, "Dark", all)).toBe(0);
    expect(applyAbilityModifier(2, "Ground", all)).toBe(0);
    expect(applyAbilityModifier(2, "Fire", all)).toBe(1);
    expect(applyAbilityModifier(1, "Water", all)).toBe(1);
  });
});
