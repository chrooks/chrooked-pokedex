import { describe, expect, it } from "vitest";
import { optionDirection } from "./DirectionStage";

describe("optionDirection", () => {
  it("carries the whole option, not just the role line", () => {
    const text = optionDirection({
      types: ["Ghost", "Ice"],
      role: "bulky trapper",
      flavor_types: ["Ground", "Water"],
      rationale: "A frozen sandcastle that swallows what steps on it.",
    });
    expect(text).toContain("bulky trapper");
    expect(text).toContain("Ghost/Ice");
    expect(text).toContain("Ground, Water");
    expect(text).toContain("swallows what steps on it");
  });

  it("omits the empty parts rather than emitting dangling labels", () => {
    const text = optionDirection({
      types: ["Ice"],
      role: "fast special attacker",
      rationale: "",
    });
    expect(text).toBe("fast special attacker — typing Ice.");
  });
});
