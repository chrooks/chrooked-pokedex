import { describe, expect, it } from "vitest";
import { decodeMakeover, encodeMakeover, isValidStage } from "./makeoverUrlCodec";

describe("isValidStage", () => {
  it("accepts a real stage", () => {
    expect(isValidStage("typing")).toBe(true);
    expect(isValidStage("apply")).toBe(true);
  });
  it("rejects junk and null", () => {
    expect(isValidStage("nonsense")).toBe(false);
    expect(isValidStage(null)).toBe(false);
  });
});

describe("decodeMakeover", () => {
  it("reads species + stage", () => {
    const params = new URLSearchParams("mk=goodra&mkstage=stats");
    expect(decodeMakeover(params)).toEqual({ species: "goodra", stage: "stats" });
  });

  it("returns closed when there is no species", () => {
    expect(decodeMakeover(new URLSearchParams("mkstage=stats"))).toEqual({
      species: null,
      stage: null,
    });
  });

  it("drops an invalid stage but keeps the species", () => {
    const params = new URLSearchParams("mk=goodra&mkstage=bogus");
    expect(decodeMakeover(params)).toEqual({ species: "goodra", stage: null });
  });
});

describe("encodeMakeover", () => {
  it("writes both params when open", () => {
    const params = new URLSearchParams();
    encodeMakeover(params, { species: "goodra", stage: "typing" });
    expect(params.get("mk")).toBe("goodra");
    expect(params.get("mkstage")).toBe("typing");
  });

  it("clears both params when closed", () => {
    const params = new URLSearchParams("mk=goodra&mkstage=typing&q=keep");
    encodeMakeover(params, { species: null, stage: null });
    expect(params.get("mk")).toBeNull();
    expect(params.get("mkstage")).toBeNull();
    // Foreign params survive.
    expect(params.get("q")).toBe("keep");
  });

  it("round-trips through decode", () => {
    const params = new URLSearchParams();
    encodeMakeover(params, { species: "sawsbuck", stage: "learnset" });
    expect(decodeMakeover(params)).toEqual({ species: "sawsbuck", stage: "learnset" });
  });
});
