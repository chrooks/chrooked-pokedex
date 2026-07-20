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

  it("resolves a target-scheme form id (`base--formwords`) to its form sprite", () => {
    // Rejuv slugs Galarian Ponyta `ponyta--galarianform`; the baked map keys it
    // `ponytagalar` (10162). Without the bridge this fell back to base dex 77.
    expect(spriteUrl("ponyta--galarianform", 77)).toBe(
      "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/10162.png",
    );
    expect(spriteUrl("rapidash--galarianform", 78)).toBe(
      "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/10163.png",
    );
  });

  it("supports name-suffixed sprite paths for PokeAPI form-only variants", () => {
    // Cherrim Sunshine has no distinct /pokemon id — its sprite is 421-sunshine.png.
    expect(spriteUrl("cherrimsunshine", 421)).toBe(
      "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/421-sunshine.png",
    );
    expect(spriteUrl("cherrim--sunshineform", 421)).toBe(
      "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/421-sunshine.png",
    );
  });

  it("distinguishes the seasonal Deerling/Sawsbuck forms", () => {
    // All four seasons share dex 585/586, so without the form map every season
    // rendered the same Spring art in the target projection.
    expect(spriteUrl("deerling--summerform", 585)).toContain("585-summer.png");
    expect(spriteUrl("deerling--winterform", 585)).toContain("585-winter.png");
    expect(spriteUrl("sawsbuck--autumnform", 586)).toContain("586-autumn.png");
    // Spring is form 0 and keeps the plain base sprite.
    expect(spriteUrl("sawsbuckspring", 586)).toContain("/586.png");
  });

  it("falls back to the base species when the form has no baked sprite id", () => {
    // № 133 — Eevee has no `eeveesomethingform` key, so it lands on base art.
    expect(spriteUrl("eevee--madeupform", 999)).toBe(
      "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/133.png",
    );
  });

  it("returns null when neither a national nor a positive passed dex exists", () => {
    expect(spriteUrl("not-a-real-mon", null)).toBeNull();
    expect(spriteUrl("not-a-real-mon", 0)).toBeNull();
  });
});
