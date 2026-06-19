import { describe, it, expect } from "vitest";
import {
  ENGINES,
  engineLabel,
  isAddDraftReady,
  isDirtyTreeStatus,
  normalizeDraft,
} from "./targets";

describe("engine options (ac9)", () => {
  it("offers pokeemerald first, essentials second", () => {
    expect(ENGINES).toEqual(["pokeemerald", "essentials"]);
  });

  it("labels both engines plainly (version shows in the readout, not the label)", () => {
    expect(engineLabel("pokeemerald")).toBe("pokeemerald");
    expect(engineLabel("essentials")).toBe("Essentials");
  });
});

describe("add-draft readiness (ac9)", () => {
  it("requires a non-blank label and path", () => {
    expect(
      isAddDraftReady({ label: "Dreamstone", path: "/forks/ds", engine: "pokeemerald" }),
    ).toBe(true);
    expect(isAddDraftReady({ label: "  ", path: "/forks/ds", engine: "pokeemerald" })).toBe(
      false,
    );
    expect(isAddDraftReady({ label: "DS", path: "   ", engine: "pokeemerald" })).toBe(false);
  });

  it("trims label and path for the wire", () => {
    expect(
      normalizeDraft({ label: "  DS  ", path: "  /forks/ds  ", engine: "pokeemerald" }),
    ).toEqual({ label: "DS", path: "/forks/ds", engine: "pokeemerald" });
  });
});

describe("dirty-tree detection (ac11)", () => {
  it("recognizes a 409 as the dirty-working-tree refusal", () => {
    expect(isDirtyTreeStatus(409)).toBe(true);
    expect(isDirtyTreeStatus(422)).toBe(false);
    expect(isDirtyTreeStatus(null)).toBe(false);
  });
});
