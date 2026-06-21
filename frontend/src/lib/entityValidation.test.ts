import { describe, expect, it } from "vitest";
import { canonicalize, collectInvalidFields, isKnown } from "./entityValidation";

describe("canonicalize", () => {
  const species = ["Bulbasaur", "Charmander", "Drizzile"];

  it("resolves a slug to the canonical display option", () => {
    expect(canonicalize("bulbasaur", species)).toBe("Bulbasaur");
  });

  it("resolves a stray-cased value to the canonical option", () => {
    expect(canonicalize("charmander", species)).toBe("Charmander");
  });

  it("passes an already-canonical value through unchanged", () => {
    expect(canonicalize("Drizzile", species)).toBe("Drizzile");
  });

  it("returns the original when no option matches", () => {
    expect(canonicalize("Mewthree", species)).toBe("Mewthree");
  });

  it("leaves an empty value empty", () => {
    expect(canonicalize("", species)).toBe("");
  });

  it("makes a canonicalized seed pass isKnown", () => {
    expect(isKnown(canonicalize("bulbasaur", species), species)).toBe(true);
  });
});

describe("isKnown", () => {
  it("returns true for empty string", () => {
    expect(isKnown("", ["Tackle", "Surf"])).toBe(true);
  });

  it("returns true for blank/whitespace-only string", () => {
    expect(isKnown("  ", ["Tackle"])).toBe(true);
  });

  it("returns true when value is exactly in options", () => {
    expect(isKnown("Tackle", ["Tackle", "Surf"])).toBe(true);
  });

  it("returns false when case does not match", () => {
    expect(isKnown("tackle", ["Tackle"])).toBe(false);
  });

  it("returns false when value is not in options", () => {
    expect(isKnown("flame burst", ["Flamethrower"])).toBe(false);
  });
});

describe("collectInvalidFields", () => {
  it("returns empty set when all values are valid", () => {
    const result = collectInvalidFields([
      { id: "f1", value: "Tackle", options: ["Tackle", "Surf"] },
      { id: "f2", value: "", options: ["Tackle"] },
    ]);
    expect(result.size).toBe(0);
  });

  it("returns id of the invalid field", () => {
    const result = collectInvalidFields([
      { id: "f1", value: "tackle", options: ["Tackle"] },
      { id: "f2", value: "Surf", options: ["Surf"] },
    ]);
    expect(result).toEqual(new Set(["f1"]));
  });

  it("handles mix of known, unknown, and empty", () => {
    const result = collectInvalidFields([
      { id: "known", value: "Surf", options: ["Surf"] },
      { id: "unknown", value: "Foobar", options: ["Tackle"] },
      { id: "empty", value: "", options: ["Tackle"] },
      { id: "blank", value: "   ", options: ["Tackle"] },
    ]);
    expect(result).toEqual(new Set(["unknown"]));
  });
});
