import { describe, expect, it } from "vitest";
import { evoMethodText } from "./dexColumns";
import type { CanonicalMethod, Evolution } from "../types";

const METHODS = [
  { id: "knows_move", label: "Knows move", value_kind: "move" },
] as unknown as CanonicalMethod[];

function evo(method: Evolution["method"]): Evolution {
  return { from: "rufflet", method } as unknown as Evolution;
}

describe("evoMethodText", () => {
  it("humanizes a canonical override method via the fetched methods", () => {
    // Regression: the table showed the raw id "knows_move Future Sight".
    expect(evoMethodText(evo({ method: "knows_move", param: "Future Sight" }), METHODS)).toBe(
      "Knows move Future Sight",
    );
  });

  it("falls back to the raw id when no methods list is supplied", () => {
    expect(evoMethodText(evo({ method: "knows_move", param: "Future Sight" }))).toBe(
      "knows_move Future Sight",
    );
  });

  it("passes a base display string through unchanged", () => {
    expect(evoMethodText(evo("Level 36"), METHODS)).toBe("Level 36");
  });
});
