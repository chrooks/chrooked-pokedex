import { afterEach, describe, expect, it, vi } from "vitest";
import { uid } from "./uid";

const UUID_SHAPE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("uid", () => {
  it("returns a v4 uuid when the platform provides one", () => {
    expect(uid()).toMatch(UUID_SHAPE);
  });

  /* The handheld reaches the dex over plain HTTP, so `crypto.randomUUID` is
     undefined there. Without the fallback every filter click threw. */
  it("still returns a distinct v4 uuid without crypto.randomUUID", () => {
    vi.stubGlobal("crypto", { getRandomValues: crypto.getRandomValues.bind(crypto) });

    const ids = new Set(Array.from({ length: 200 }, uid));
    expect(ids.size).toBe(200);
    for (const id of ids) expect(id).toMatch(UUID_SHAPE);
  });
});
