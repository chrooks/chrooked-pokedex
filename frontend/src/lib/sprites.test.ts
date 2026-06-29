import { describe, expect, it } from "vitest";
import { spriteUrl } from "./sprites";

describe("spriteUrl", () => {
  it("keys the CDN sprite on national dex, not the passed (target-local) dex", () => {
    // abra is national № 63. A Target may list it at a different local order
    // (Essentials uses PBS file position) — the CDN url must still be 63.
    expect(spriteUrl("abra", 999)).toBe(
      "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/63.png",
    );
  });

  it("falls back to the passed dex for ids absent from the canon map", () => {
    expect(spriteUrl("not-a-real-mon", 42)).toBe(
      "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/42.png",
    );
  });

  it("returns null when neither a national nor a positive passed dex exists", () => {
    expect(spriteUrl("not-a-real-mon", null)).toBeNull();
    expect(spriteUrl("not-a-real-mon", 0)).toBeNull();
  });
});
