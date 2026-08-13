import { describe, it, expect } from "vitest";
import { loreProvenanceLine, sourceLabel } from "./loreProvenance";

describe("loreProvenanceLine", () => {
  it("renders nothing when the lookup never ran", () => {
    expect(loreProvenanceLine({ mode: "off" })).toBeNull();
    expect(loreProvenanceLine(null)).toBeNull();
    expect(loreProvenanceLine(undefined)).toBeNull();
  });

  it("reports the mode, source count and injected characters", () => {
    expect(
      loreProvenanceLine({
        mode: "full",
        found: true,
        sources: ["https://pokeapi.co/x", "https://bulbapedia.bulbagarden.net/y"],
        chars: 3812,
      }),
    ).toBe("lore · full · 2 sources · 3,812 chars");
  });

  it("puts thousands separators on the character count", () => {
    expect(
      loreProvenanceLine({ mode: "condensed", found: true, sources: [], chars: 1234567 }),
    ).toContain("1,234,567 chars");
  });

  it("singularizes a lone source", () => {
    expect(
      loreProvenanceLine({ mode: "full", found: true, sources: ["https://pokeapi.co/x"], chars: 900 }),
    ).toBe("lore · full · 1 source · 900 chars");
  });

  it("says plainly when the lookup found nothing", () => {
    expect(loreProvenanceLine({ mode: "full", found: false, sources: [], chars: 0 })).toBe(
      "lore · full · no lore found",
    );
  });

  it("treats an absent `found` as a miss rather than claiming a hit", () => {
    expect(loreProvenanceLine({ mode: "condensed" })).toBe("lore · condensed · no lore found");
  });

  it("distinguishes a failed lookup from an honest miss", () => {
    expect(
      loreProvenanceLine({ mode: "full", found: false, sources: [], chars: 0, error: "timed out" }),
    ).toBe("lore · full · lookup failed");
  });

  it("names the base species when the lore describes it and not the form", () => {
    expect(
      loreProvenanceLine({
        mode: "full",
        found: true,
        sources: ["https://pokeapi.co/x"],
        chars: 2100,
        base_species: "marowak",
      }),
    ).toBe("lore · full · 1 source · 2,100 chars · base species: marowak");
  });
});

describe("sourceLabel", () => {
  it("shortens a URL to its host without the www prefix", () => {
    expect(sourceLabel("https://www.bulbapedia.bulbagarden.net/w/api.php?x=1")).toBe(
      "bulbapedia.bulbagarden.net",
    );
    expect(sourceLabel("https://pokeapi.co/api/v2/pokemon-species/362")).toBe("pokeapi.co");
  });

  it("falls back to the raw value when it is not a URL", () => {
    expect(sourceLabel("not a url")).toBe("not a url");
  });
});
