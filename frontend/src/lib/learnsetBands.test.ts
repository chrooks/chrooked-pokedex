import { describe, expect, it } from "vitest";
import { bandForLevel, bandViolation, type LearnsetRubric } from "./learnsetBands";

const RUBRIC: LearnsetRubric = {
  version: 1,
  bands: [
    { level_min: 1, level_max: 19, bp_max: 60, label: "≤60BP" },
    { level_min: 20, level_max: 29, bp_min: 50, bp_max: 70, label: "50–70BP" },
    { level_min: 30, level_max: 39, bp_min: 70, bp_max: 80, label: "70–80BP" },
    { level_min: 40, level_max: 49, bp_min: 80, bp_max: 99, label: "80–99BP" },
    { level_min: 50, level_max: 100, bp_min: 100, label: "100+BP" },
  ],
};

describe("bandForLevel", () => {
  it("finds the band a level sits in", () => {
    expect(bandForLevel(RUBRIC, 8)?.label).toBe("≤60BP");
    expect(bandForLevel(RUBRIC, 25)?.label).toBe("50–70BP");
    expect(bandForLevel(RUBRIC, 60)?.label).toBe("100+BP");
  });
  it("returns null for a null rubric", () => {
    expect(bandForLevel(null, 8)).toBeNull();
  });
});

describe("bandViolation — the documented hard cap", () => {
  it("flags a 75BP move at L8 (the canonical miss)", () => {
    expect(bandViolation(RUBRIC, 8, 75)).toBe("L8 · 75BP · BAND ≤60BP");
  });

  it("passes a 55BP move at L8", () => {
    expect(bandViolation(RUBRIC, 8, 55)).toBeNull();
  });

  it("exempts L0 on-evolution rewards", () => {
    expect(bandViolation(RUBRIC, 0, 120)).toBeNull();
  });

  it("exempts status/utility moves with no power", () => {
    expect(bandViolation(RUBRIC, 8, null)).toBeNull();
    expect(bandViolation(RUBRIC, 8, undefined)).toBeNull();
  });

  it("is null when there is no rubric loaded yet", () => {
    expect(bandViolation(null, 8, 75)).toBeNull();
  });
});
