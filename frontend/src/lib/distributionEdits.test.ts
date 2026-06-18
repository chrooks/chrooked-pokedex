import { describe, expect, test } from "vitest";
import type { DexEntry, SpeciesOverride } from "../types";
import {
  abilityOverridePayload,
  buildAbilitiesOverride,
  buildLearnsetOverride,
  currentLevel,
  currentSlot,
  moveOverridePayload,
  nameEq,
  replacementInSlot,
} from "./distributionEdits";

function makeEntry(over: Partial<DexEntry> = {}): DexEntry {
  return {
    dex: 25,
    chrooked_id: "pikachu",
    name: "Pikachu",
    types: ["Electric"],
    abilities: { primary: "Static", secondary: null, hidden: "Lightning Rod" },
    stats: {},
    learnset: [
      { level: 1, move: "Thunder Shock" },
      { level: 5, move: "Growl" },
      { level: 0, move: "Thunder Shock" },
    ],
    evolution: null,
    evolves_into: [],
    fully_evolved: false,
    overridden_fields: [],
    base: {},
    ...over,
  };
}

describe("nameEq", () => {
  test("matches case- and whitespace-insensitively", () => {
    expect(nameEq("Ice Punch", "  ice punch ")).toBe(true);
    expect(nameEq("Ice Punch", "Ice Beam")).toBe(false);
  });
});

describe("currentLevel", () => {
  test("returns the lowest level when the move is learned at several", () => {
    expect(currentLevel(makeEntry(), "Thunder Shock")).toBe(0);
  });

  test("returns null when the species does not learn the move", () => {
    expect(currentLevel(makeEntry(), "Surf")).toBeNull();
  });
});

describe("currentSlot", () => {
  test("finds the occupied slot", () => {
    expect(currentSlot(makeEntry(), "Static")).toBe("primary");
    expect(currentSlot(makeEntry(), "Lightning Rod")).toBe("hidden");
  });

  test("returns null when no slot holds the ability", () => {
    expect(currentSlot(makeEntry(), "Levitate")).toBeNull();
  });
});

describe("buildLearnsetOverride", () => {
  test("changing a level drops all existing entries and re-adds one", () => {
    const result = buildLearnsetOverride(makeEntry(), "Thunder Shock", {
      type: "level",
      level: 12,
    });
    // Growl preserved; both Thunder Shock rows collapse into one at level 12.
    expect(result).toEqual([
      { level: 5, move: "Growl" },
      { level: 12, move: "Thunder Shock" },
    ]);
  });

  test("adding a move to a species that lacks it appends one entry", () => {
    const result = buildLearnsetOverride(makeEntry(), "Surf", {
      type: "level",
      level: 30,
    });
    expect(result).toContainEqual({ level: 30, move: "Surf" });
    expect(result).toHaveLength(4);
  });

  test("removing drops every entry for the move and keeps the rest", () => {
    const result = buildLearnsetOverride(makeEntry(), "Thunder Shock", {
      type: "remove",
    });
    expect(result).toEqual([{ level: 5, move: "Growl" }]);
  });

  test("does not mutate the source learnset (immutability)", () => {
    const entry = makeEntry();
    const before = JSON.stringify(entry.learnset);
    buildLearnsetOverride(entry, "Thunder Shock", { type: "remove" });
    expect(JSON.stringify(entry.learnset)).toBe(before);
  });
});

describe("buildAbilitiesOverride", () => {
  test("assigning a free slot keeps the others", () => {
    const result = buildAbilitiesOverride(makeEntry(), "Levitate", {
      type: "slot",
      slot: "secondary",
    });
    expect(result).toEqual({
      primary: "Static",
      secondary: "Levitate",
      hidden: "Lightning Rod",
    });
  });

  test("moving to a new slot clears the old one (no duplication)", () => {
    const result = buildAbilitiesOverride(makeEntry(), "Static", {
      type: "slot",
      slot: "secondary",
    });
    expect(result).toEqual({
      primary: null,
      secondary: "Static",
      hidden: "Lightning Rod",
    });
  });

  test("assigning an occupied slot replaces its occupant", () => {
    const result = buildAbilitiesOverride(makeEntry(), "Levitate", {
      type: "slot",
      slot: "primary",
    });
    expect(result.primary).toBe("Levitate");
  });

  test("remove clears the occupied slot", () => {
    const result = buildAbilitiesOverride(makeEntry(), "Static", {
      type: "remove",
    });
    expect(result).toEqual({
      primary: null,
      secondary: null,
      hidden: "Lightning Rod",
    });
  });

  test("does not mutate the source abilities (immutability)", () => {
    const entry = makeEntry();
    buildAbilitiesOverride(entry, "Static", { type: "slot", slot: "hidden" });
    expect(entry.abilities.primary).toBe("Static");
  });
});

describe("replacementInSlot", () => {
  test("reports the occupant of an occupied target slot", () => {
    expect(replacementInSlot(makeEntry(), "Levitate", "primary")).toBe("Static");
  });

  test("is null for an empty slot", () => {
    expect(replacementInSlot(makeEntry(), "Levitate", "secondary")).toBeNull();
  });

  test("is null when the slot already holds the ability being granted", () => {
    expect(replacementInSlot(makeEntry(), "Static", "primary")).toBeNull();
  });
});

describe("override payloads (D6 passthrough)", () => {
  test("move payload carries raw aka + passthrough fields and the new learnset", () => {
    const raw: SpeciesOverride = {
      name: "Pikachu",
      chrooked_id: "pikachu",
      aka: { dex: 25, symbol: "SPECIES_PIKACHU" },
      types: ["Electric"],
      abilities: null,
      stats: { spe: 99 },
      learnset: null,
      evolution: null,
    };
    const learnset = buildLearnsetOverride(makeEntry(), "Surf", {
      type: "level",
      level: 30,
    });
    const payload = moveOverridePayload(makeEntry(), raw, learnset);
    expect(payload.aka).toEqual({ dex: 25, symbol: "SPECIES_PIKACHU" });
    expect(payload.stats).toEqual({ spe: 99 });
    expect(payload.types).toEqual(["Electric"]);
    expect(payload.learnset).toBe(learnset);
  });

  test("ability payload synthesizes aka from dex when there is no raw Override", () => {
    const abilities = buildAbilitiesOverride(makeEntry(), "Levitate", {
      type: "slot",
      slot: "secondary",
    });
    const payload = abilityOverridePayload(makeEntry(), null, abilities);
    expect(payload.aka).toEqual({ dex: 25 });
    expect(payload.abilities).toBe(abilities);
    expect(payload.learnset).toBeNull();
  });
});
