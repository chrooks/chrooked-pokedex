import { describe, it, expect } from "vitest";
import {
  isAbilityEdited,
  matchesAbilityEditedFilter,
} from "./format";
import type { Ability } from "../types";

/** A minimal ability fixture; `overridden_fields`/`base` carry the merge flags. */
function makeAbility(overrides: Partial<Ability> = {}): Ability {
  return {
    name: "Static",
    chrooked_id: "static",
    description: "May paralyze on contact.",
    aka: {},
    behaviors: [],
    overridden_fields: [],
    base: {},
    ...overrides,
  };
}

describe("isAbilityEdited", () => {
  it("is false for a base-only ability (no overridden fields)", () => {
    expect(isAbilityEdited(makeAbility())).toBe(false);
  });

  it("is true for an overridden ability (carries base values)", () => {
    const ability = makeAbility({
      overridden_fields: ["description"],
      base: { description: "Old text." },
    });
    expect(isAbilityEdited(ability)).toBe(true);
  });

  it("is true for a Ruleset-created ability (flagged, empty base)", () => {
    const ability = makeAbility({
      chrooked_id: "obfuscate",
      name: "Obfuscate",
      overridden_fields: ["name", "description"],
      base: {},
    });
    expect(isAbilityEdited(ability)).toBe(true);
  });
});

describe("matchesAbilityEditedFilter", () => {
  const base = makeAbility();
  const edited = makeAbility({
    overridden_fields: ["description"],
    base: { description: "Old." },
  });

  it("'all' keeps every ability", () => {
    expect(matchesAbilityEditedFilter(base, "all")).toBe(true);
    expect(matchesAbilityEditedFilter(edited, "all")).toBe(true);
  });

  it("'edited' keeps only Ruleset-touched abilities", () => {
    expect(matchesAbilityEditedFilter(edited, "edited")).toBe(true);
    expect(matchesAbilityEditedFilter(base, "edited")).toBe(false);
  });

  it("'base' keeps only untouched base abilities", () => {
    expect(matchesAbilityEditedFilter(base, "base")).toBe(true);
    expect(matchesAbilityEditedFilter(edited, "base")).toBe(false);
  });
});
