import { describe, it, expect } from "vitest";
import { isMoveEdited, matchesMoveEditedFilter } from "./format";
import type { Move } from "../types";

/** A minimal move fixture; `overridden_fields`/`base` carry the merge flags. */
function makeMove(overrides: Partial<Move> = {}): Move {
  return {
    name: "Tackle",
    chrooked_id: "tackle",
    aka: {},
    type: "Normal",
    second_type: null,
    category: "physical",
    power: 40,
    accuracy: 100,
    pp: 35,
    description: "A physical attack.",
    effect: "hit",
    argument: null,
    additional_effects: [],
    flags: ["contact"],
    priority: 0,
    target: "selected",
    recoil: null,
    overridden_fields: [],
    base: {},
    ...overrides,
  };
}

describe("isMoveEdited", () => {
  it("is false for a base-only move (no overridden fields)", () => {
    expect(isMoveEdited(makeMove())).toBe(false);
  });

  it("is true for an overridden move (carries base values)", () => {
    const move = makeMove({
      power: 50,
      overridden_fields: ["power"],
      base: { power: 40 },
    });
    expect(isMoveEdited(move)).toBe(true);
  });

  it("is true for a Ruleset-created move (flagged, empty base)", () => {
    const move = makeMove({
      chrooked_id: "obfuscate_strike",
      name: "Obfuscate Strike",
      overridden_fields: ["name", "power", "type"],
      base: {},
    });
    expect(isMoveEdited(move)).toBe(true);
  });
});

describe("matchesMoveEditedFilter", () => {
  const base = makeMove();
  const edited = makeMove({
    power: 60,
    overridden_fields: ["power"],
    base: { power: 40 },
  });

  it("'all' keeps every move", () => {
    expect(matchesMoveEditedFilter(base, "all")).toBe(true);
    expect(matchesMoveEditedFilter(edited, "all")).toBe(true);
  });

  it("'edited' keeps only Ruleset-touched moves", () => {
    expect(matchesMoveEditedFilter(edited, "edited")).toBe(true);
    expect(matchesMoveEditedFilter(base, "edited")).toBe(false);
  });

  it("'base' keeps only untouched base moves", () => {
    expect(matchesMoveEditedFilter(base, "base")).toBe(true);
    expect(matchesMoveEditedFilter(edited, "base")).toBe(false);
  });
});
