import { describe, it, expect } from "vitest";
import { CLASS_VALUES, classOf } from "./dexTags";

describe("classOf", () => {
  it("maps a legendary dex number to Legendary", () => {
    expect(classOf(144)).toBe("Legendary"); // Articuno
    expect(classOf(150)).toBe("Legendary"); // Mewtwo
  });

  it("maps a mythical dex number to Mythical", () => {
    expect(classOf(151)).toBe("Mythical"); // Mew
  });

  it("maps a starter dex number to Starter", () => {
    expect(classOf(1)).toBe("Starter"); // Bulbasaur
  });

  it("returns null for a species with no class", () => {
    expect(classOf(16)).toBeNull(); // Pidgey
  });

  it("returns null for a species with no dex number", () => {
    expect(classOf(null)).toBeNull();
  });
});

describe("CLASS_VALUES", () => {
  it("lists the three filterable classes", () => {
    expect(CLASS_VALUES).toEqual(["Legendary", "Mythical", "Starter"]);
  });
});
