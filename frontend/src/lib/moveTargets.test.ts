import { describe, expect, it } from "vitest";
import { MOVE_TARGETS } from "./format";
import { TARGET_LABEL, TARGET_PATTERNS, patternOf, snapTarget } from "./moveTargets";

describe("TARGET_PATTERNS", () => {
  it("covers every schema target key", () => {
    for (const key of MOVE_TARGETS) {
      expect(TARGET_PATTERNS[key], key).toBeDefined();
      expect(TARGET_LABEL[key], key).toBeDefined();
    }
  });

  it("falls back to depends for unknown keys", () => {
    expect(patternOf("nonsense")).toBe(TARGET_PATTERNS.depends);
  });
});

describe("snapTarget", () => {
  it("adding the far foe to both lands on opponent (exact set match)", () => {
    expect(snapTarget("both", "f2")).toBe("opponent");
  });

  it("building all adjacent from both lands on foes_and_ally, not selected", () => {
    // {f0,f1,a1} matches both patterns exactly; priority picks the each-kind.
    expect(snapTarget("both", "a1")).toBe("foes_and_ally");
  });

  it("only the ally clicked = ally", () => {
    expect(snapTarget("depends", "a1")).toBe("ally");
  });

  it("a slotless result still moves off the current preset", () => {
    expect(snapTarget("all_battlers", "f2")).toBe("foes_and_ally");
    expect(snapTarget("user", "a1")).toBe("ally");
  });

  it("battler-shaped presets outrank same-set field twins", () => {
    expect(snapTarget("both", "f2")).not.toBe("opponents_field");
    expect(snapTarget("opponents_field", "u")).not.toBe("random");
  });

  it("is deterministic and always returns a legal preset", () => {
    for (const key of MOVE_TARGETS) {
      for (const slot of ["f0", "f1", "f2", "u", "a1", "a2"] as const) {
        const result = snapTarget(key, slot);
        expect(MOVE_TARGETS).toContain(result);
        expect(snapTarget(key, slot)).toBe(result);
      }
    }
  });
});
