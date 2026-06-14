import { describe, it, expect } from "vitest";
import type { DexEntry } from "../types";
import {
  applyFilter,
  buildFilterDefs,
  evalEntries,
  type FilterDef,
  type FilterEntry,
} from "./dexFilters";

function makeEntry(overrides: Partial<DexEntry> = {}): DexEntry {
  return {
    dex: 6,
    chrooked_id: "charizard",
    name: "Charizard",
    types: ["Fire", "Flying"],
    abilities: { primary: "Blaze", secondary: null, hidden: "Solar Power" },
    stats: { hp: 78, atk: 84, def: 78, spa: 109, spd: 85, spe: 100 },
    learnset: [],
    evolution: null,
    overridden_fields: [],
    base: {},
    ...overrides,
  };
}

const defs = buildFilterDefs([]);
function defFor(field: string): FilterDef {
  const def = defs.find((entry) => entry.field === field);
  if (!def) throw new Error(`no def for ${field}`);
  return def;
}

let nextId = 0;
function filter(
  field: string,
  value: string,
  connector: "AND" | "OR" = "AND",
  negated = false,
): FilterEntry {
  nextId += 1;
  return { kind: "filter", id: `f${nextId}`, field, value, connector, negated };
}
function paren(p: "(" | ")", connector: "AND" | "OR" = "AND"): FilterEntry {
  nextId += 1;
  return { kind: "paren", id: `p${nextId}`, paren: p, connector };
}

describe("buildFilterDefs", () => {
  it("assigns numeric/select/text methods to the right fields", () => {
    expect(defFor("atk").method).toBe("numeric");
    expect(defFor("bst").method).toBe("numeric");
    expect(defFor("type").method).toBe("select");
    expect(defFor("class").method).toBe("select");
    expect(defFor("name").method).toBe("text");
    expect(defFor("abilities").method).toBe("text");
  });
});

describe("applyFilter — numeric operators (ac2)", () => {
  const entry = makeEntry({ stats: { hp: 78, atk: 100, def: 78, spa: 109, spd: 85, spe: 100 } });
  const atk = defFor("atk");

  it("≥ selects values at or above the threshold", () => {
    expect(applyFilter(atk, entry, "≥|100")).toBe(true);
    expect(applyFilter(atk, entry, "≥|101")).toBe(false);
  });
  it("≤ selects values at or below the threshold", () => {
    expect(applyFilter(atk, entry, "≤|100")).toBe(true);
    expect(applyFilter(atk, entry, "≤|99")).toBe(false);
  });
  it("= selects exact matches", () => {
    expect(applyFilter(atk, entry, "=|100")).toBe(true);
    expect(applyFilter(atk, entry, "=|99")).toBe(false);
  });
  it("> and < are strict", () => {
    expect(applyFilter(atk, entry, ">|99")).toBe(true);
    expect(applyFilter(atk, entry, ">|100")).toBe(false);
    expect(applyFilter(atk, entry, "<|101")).toBe(true);
    expect(applyFilter(atk, entry, "<|100")).toBe(false);
  });
  it("fails a missing stat or unparseable threshold rather than throwing", () => {
    const noBst = makeEntry({ stats: { hp: 1 } });
    expect(applyFilter(defFor("bst"), noBst, "≥|100")).toBe(false);
    expect(applyFilter(atk, entry, "≥|abc")).toBe(false);
  });
});

describe("applyFilter — Type is array-contains (ac3)", () => {
  const type = defFor("type");
  const dual = makeEntry({ types: ["Fire", "Water"] });

  it("matches either type a species has", () => {
    expect(applyFilter(type, dual, "Fire")).toBe(true);
    expect(applyFilter(type, dual, "Water")).toBe(true);
  });
  it("rejects a type the species lacks", () => {
    expect(applyFilter(type, dual, "Grass")).toBe(false);
  });
});

describe("applyFilter — Class by national dex (ac4)", () => {
  const cls = defFor("class");
  it("matches the species' class and nothing else", () => {
    const articuno = makeEntry({ dex: 144 });
    expect(applyFilter(cls, articuno, "Legendary")).toBe(true);
    expect(applyFilter(cls, articuno, "Mythical")).toBe(false);
  });
  it("rejects an unclassed species", () => {
    const pidgey = makeEntry({ dex: 16 });
    expect(applyFilter(cls, pidgey, "Legendary")).toBe(false);
  });
});

describe("applyFilter — text is accent-insensitive substring", () => {
  it("matches name ignoring diacritics and case", () => {
    const flabebe = makeEntry({ name: "Flabébé" });
    expect(applyFilter(defFor("name"), flabebe, "flabebe")).toBe(true);
  });
  it("matches across the three ability slots", () => {
    const entry = makeEntry();
    expect(applyFilter(defFor("abilities"), entry, "solar")).toBe(true);
    expect(applyFilter(defFor("abilities"), entry, "drizzle")).toBe(false);
  });
  it("an empty text value matches everything (an empty pill filters nothing)", () => {
    expect(applyFilter(defFor("name"), makeEntry(), "")).toBe(true);
  });
});

describe("evalEntries — boolean structure (ac1)", () => {
  // A = Type:Fire (true), B = Type:Water (false), C = Atk ≥ 999 (false)
  const entry = makeEntry(); // Fire/Flying, atk 84
  const A = () => filter("type", "Fire");
  const B = () => filter("type", "Water", "OR");
  const C = () => filter("atk", "≥|999", "AND");

  it("passes on an empty filter list", () => {
    expect(evalEntries(entry, [])).toBe(true);
  });

  it("binds OR looser than AND: A OR B AND C == A OR (B AND C)", () => {
    // true OR (false AND false) = true
    expect(evalEntries(entry, [A(), B(), C()])).toBe(true);
  });

  it("respects parentheses: (A OR B) AND C differs from the flat form", () => {
    // (true OR false) AND false = false
    const entries = [paren("("), A(), B(), paren(")"), filter("atk", "≥|999", "AND")];
    expect(evalEntries(entry, entries)).toBe(false);
  });

  it("negates a leaf with NOT", () => {
    expect(evalEntries(entry, [filter("type", "Fire", "AND", true)])).toBe(false); // NOT Fire
    expect(evalEntries(entry, [filter("type", "Water", "AND", true)])).toBe(true); // NOT Water
  });

  it("ignores an unmatched ) at the root instead of dropping the whole filter", () => {
    // A hand-mangled URL could put a stray ")" first; the remaining real filter
    // must still apply (regression: it used to make every entry pass).
    const entries = [paren(")"), filter("atk", "≥|999")]; // atk 84 < 999
    expect(evalEntries(entry, entries)).toBe(false);
  });

  it("evaluates a nested, grouped expression end to end", () => {
    // Atk ≥ 100 AND ( Class:Legendary OR BST ≥ 500 )  on Charizard (atk 84) -> false
    const expr = [
      filter("atk", "≥|100"),
      paren("(", "AND"),
      filter("class", "Legendary"),
      filter("bst", "≥|500", "OR"),
      paren(")"),
    ];
    expect(evalEntries(entry, expr)).toBe(false); // atk 84 < 100 short-circuits the AND
  });
});
