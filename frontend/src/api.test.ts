import { describe, expect, it } from "vitest";
import { api } from "./api";

/** `useResource` caches on fetcher identity, so a per-Target factory MUST hand
    back the same function object for the same id — otherwise every tab open
    misses the cache and re-fetches. */
describe("per-target fetcher identity", () => {
  it("returns the same fetcher for the same target id", () => {
    expect(api.targetMoves("rejuv")).toBe(api.targetMoves("rejuv"));
    expect(api.targetAbilities("rejuv")).toBe(api.targetAbilities("rejuv"));
    expect(api.targetDex("rejuv")).toBe(api.targetDex("rejuv"));
    expect(api.targetTypeChart("rejuv")).toBe(api.targetTypeChart("rejuv"));
  });

  it("returns a distinct fetcher per target id", () => {
    expect(api.targetMoves("rejuv")).not.toBe(api.targetMoves("soulgold"));
  });
});
