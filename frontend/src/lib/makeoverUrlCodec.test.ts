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
    expect(decodeMakeover(params)).toEqual({
      species: "goodra",
      stage: "stats",
      selected: null,
    });
  });

  it("returns closed when there is no species", () => {
    expect(decodeMakeover(new URLSearchParams("mkstage=stats"))).toEqual({
      species: null,
      stage: null,
      selected: null,
    });
  });

  it("drops an invalid stage but keeps the species", () => {
    const params = new URLSearchParams("mk=goodra&mkstage=bogus");
    expect(decodeMakeover(params)).toEqual({
      species: "goodra",
      stage: null,
      selected: null,
    });
  });

  it("reads a single-stage mksel seed (the suggest deep link)", () => {
    const params = new URLSearchParams("mk=goodra&mksel=abilities");
    expect(decodeMakeover(params).selected).toEqual(["abilities"]);
  });

  it("reads a multi-stage mksel seed, dropping junk and duplicates", () => {
    const params = new URLSearchParams(
      "mk=goodra&mksel=stats,bogus,learnset,stats",
    );
    expect(decodeMakeover(params).selected).toEqual(["stats", "learnset"]);
  });

  it("treats an all-junk mksel as no seed", () => {
    const params = new URLSearchParams("mk=goodra&mksel=bogus,apply");
    expect(decodeMakeover(params).selected).toBeNull();
  });

  it("reads mksel=mirror as the EMPTY seed (mirror-only journey)", () => {
    const params = new URLSearchParams("mk=goodra&mksel=mirror");
    expect(decodeMakeover(params).selected).toEqual([]);
  });
});

describe("encodeMakeover", () => {
  it("writes all params when open", () => {
    const params = new URLSearchParams();
    encodeMakeover(params, {
      species: "goodra",
      stage: "typing",
      selected: ["typing"],
    });
    expect(params.get("mk")).toBe("goodra");
    expect(params.get("mkstage")).toBe("typing");
    expect(params.get("mksel")).toBe("typing");
  });

  it("omits mksel when there is no seed", () => {
    const params = new URLSearchParams();
    encodeMakeover(params, { species: "goodra", stage: null, selected: null });
    expect(params.get("mksel")).toBeNull();
  });

  it("encodes the EMPTY seed as mksel=mirror", () => {
    const params = new URLSearchParams();
    encodeMakeover(params, { species: "goodra", stage: null, selected: [] });
    expect(params.get("mksel")).toBe("mirror");
  });

  it("clears every param when closed", () => {
    const params = new URLSearchParams(
      "mk=goodra&mkstage=typing&mksel=abilities&q=keep",
    );
    encodeMakeover(params, { species: null, stage: null, selected: null });
    expect(params.get("mk")).toBeNull();
    expect(params.get("mkstage")).toBeNull();
    expect(params.get("mksel")).toBeNull();
    // Foreign params survive.
    expect(params.get("q")).toBe("keep");
  });

  it("round-trips through decode", () => {
    const params = new URLSearchParams();
    encodeMakeover(params, {
      species: "sawsbuck",
      stage: "learnset",
      selected: ["learnset"],
    });
    expect(decodeMakeover(params)).toEqual({
      species: "sawsbuck",
      stage: "learnset",
      selected: ["learnset"],
    });
  });

  it("round-trips the mirror-only seed", () => {
    const params = new URLSearchParams();
    encodeMakeover(params, { species: "deerling", stage: null, selected: [] });
    expect(decodeMakeover(params).selected).toEqual([]);
  });
});
