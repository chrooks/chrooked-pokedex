import { describe, expect, it } from "vitest";
import {
  composeDirection,
  deriveConstraints,
  rerollDirection,
  type StatsDraft,
  type TypingDraft,
} from "./makeoverTweak";
import type { AbilityDraft, LearnsetDraft } from "../types";

describe("deriveConstraints — typing", () => {
  it("emits a keep-typing constraint when the author changed the types", () => {
    const base: TypingDraft = { types: ["Dragon"] };
    const edited: TypingDraft = { types: ["Water", "Dragon"] };
    expect(deriveConstraints("typing", base, edited)).toEqual(["the typing Water/Dragon"]);
  });

  it("is empty when the typing is unchanged", () => {
    const base: TypingDraft = { types: ["Water", "Dragon"] };
    expect(deriveConstraints("typing", base, { types: ["Water", "Dragon"] })).toEqual([]);
  });
});

describe("deriveConstraints — stats", () => {
  it("names each hand-changed stat", () => {
    const base: StatsDraft = { stats: { hp: 90, atk: 80, def: 70, spa: 130, spd: 150, spe: 60 } };
    const edited: StatsDraft = { stats: { hp: 90, atk: 80, def: 70, spa: 130, spd: 150, spe: 80 } };
    expect(deriveConstraints("stats", base, edited)).toEqual(["SPE at 80"]);
  });
});

describe("deriveConstraints — abilities", () => {
  it("names a changed slot", () => {
    const base: AbilityDraft = { abilities: { hidden: "Gooey" } };
    const edited: AbilityDraft = { abilities: { hidden: "Rough Skin" } };
    expect(deriveConstraints("abilities", base, edited)).toEqual(["the hidden ability Rough Skin"]);
  });
});

describe("deriveConstraints — learnset", () => {
  it("keeps an author-placed row and forbids a removed one", () => {
    const base: LearnsetDraft = {
      learnset: [
        { level: 1, move: "Tackle" },
        { level: 20, move: "Iron Tail" },
      ],
    };
    const edited: LearnsetDraft = {
      learnset: [
        { level: 1, move: "Tackle" },
        { level: 14, move: "Mach Punch" },
      ],
    };
    const constraints = deriveConstraints("learnset", base, edited);
    expect(constraints).toContain("Mach Punch at L14");
    expect(constraints).toContain("do not include Iron Tail");
  });

  it("flags an L0 add as an on-evolution reward", () => {
    const base: LearnsetDraft = { learnset: [] };
    const edited: LearnsetDraft = { learnset: [{ level: 0, move: "Dragon Pulse" }] };
    expect(deriveConstraints("learnset", base, edited)).toEqual([
      "Dragon Pulse at L0 (on evolution)",
    ]);
  });
});

describe("composeDirection", () => {
  it("appends a keep-fixed block after the base steer", () => {
    const out = composeDirection("faster attacker", ["SPE at 80"]);
    expect(out).toContain("faster attacker");
    expect(out).toContain("Keep these author edits fixed");
    expect(out).toContain("- SPE at 80");
  });

  it("returns the base unchanged when there are no edits", () => {
    expect(composeDirection("faster attacker", [])).toBe("faster attacker");
  });
});

describe("rerollDirection — the full re-roll steer preserves edits", () => {
  it("carries a hand edit into the re-roll direction", () => {
    const base: StatsDraft = { stats: { hp: 90, atk: 80, def: 70, spa: 130, spd: 150, spe: 60 } };
    const edited: StatsDraft = { stats: { hp: 90, atk: 80, def: 70, spa: 130, spd: 150, spe: 80 } };
    const out = rerollDirection("stats", "bulkier", base, edited);
    expect(out).toContain("bulkier");
    expect(out).toContain("SPE at 80");
  });
});
