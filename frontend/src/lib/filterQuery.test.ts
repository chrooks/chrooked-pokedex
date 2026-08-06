import { describe, expect, it } from "vitest";
import { buildFilterDefs } from "./dexFilters";
import { buildMoveFilterDefs } from "./moveRegistry";
import type { FilterEntry } from "./filterEngine";
import { formatQuery, parseQuery, suggest, tokenize } from "./filterQuery";

const DEX = buildFilterDefs([]);
const MOVES = buildMoveFilterDefs();

/** Deterministic ids so a parse is comparable. */
function ids() {
  let n = 0;
  return () => `id${(n += 1)}`;
}

function parse(raw: string, defs = DEX) {
  return parseQuery(raw, defs, ids());
}

/** The entries a round-trip must preserve, ignoring the ids. */
function shape(entries: FilterEntry[]) {
  return entries.map((e) =>
    e.kind === "filter"
      ? { kind: e.kind, field: e.field, value: e.value, negated: e.negated, connector: e.connector }
      : { kind: e.kind, paren: e.paren, connector: e.connector },
  );
}

describe("tokenize", () => {
  it("splits on whitespace", () => {
    expect(tokenize("name:fros bst>=500")).toEqual(["name:fros", "bst>=500"]);
  });

  it("keeps a quoted phrase as one term", () => {
    expect(tokenize('moves:"dragon dance" bst>=500')).toEqual([
      'moves:"dragon dance"',
      "bst>=500",
    ]);
  });

  it("collapses runs of whitespace", () => {
    expect(tokenize("  a:1   b:2  ")).toEqual(["a:1", "b:2"]);
  });
});

describe("parseQuery", () => {
  it("parses a text term", () => {
    expect(shape(parse("name:fros").entries)).toEqual([
      { kind: "filter", field: "name", value: "fros", negated: false, connector: "AND" },
    ]);
  });

  it("reads the leading dash as negation", () => {
    const { entries } = parse("-class:mega");
    expect(shape(entries)).toEqual([
      { kind: "filter", field: "class", value: "Mega", negated: true, connector: "AND" },
    ]);
  });

  it("normalizes value casing to the registry's spelling", () => {
    expect(shape(parse("class:MEGA").entries)[0]).toMatchObject({ value: "Mega" });
    expect(shape(parse("class:mega").entries)[0]).toMatchObject({ value: "Mega" });
  });

  it("maps ascii operators onto the model's typographic ones", () => {
    expect(shape(parse("bst>=500").entries)[0]).toMatchObject({ value: "≥|500" });
    expect(shape(parse("bst<=500").entries)[0]).toMatchObject({ value: "≤|500" });
    expect(shape(parse("bst>500").entries)[0]).toMatchObject({ value: ">|500" });
  });

  it("gives a relation operator its own key", () => {
    expect(shape(parse("type:grass").entries)[0]).toMatchObject({ field: "type", value: "is|Grass" });
    expect(shape(parse("weak:fire").entries)[0]).toMatchObject({ field: "type", value: "weak|Fire" });
    expect(shape(parse("se:water").entries)[0]).toMatchObject({ field: "type", value: "se|Water" });
  });

  it("parses a selectnum with and without its numeric clause", () => {
    expect(shape(parse("evolution:level").entries)[0]).toMatchObject({ value: "Level" });
    expect(shape(parse("evolution:level>=45").entries)[0]).toMatchObject({ value: "Level|≥|45" });
  });

  it("ignores a numeric clause on a kind that takes none", () => {
    expect(shape(parse("evolution:item>=45").entries)[0]).toMatchObject({ value: "Item" });
  });

  it("carries `or` onto the next term and resets after it", () => {
    const { entries } = parse("type:grass or type:fire type:water");
    expect(entries.map((e) => e.connector)).toEqual(["AND", "OR", "AND"]);
  });

  it("parses parentheses as paren entries", () => {
    const { entries } = parse("( type:grass or type:fire ) bst>=500");
    expect(entries.map((e) => e.kind)).toEqual(["paren", "filter", "filter", "paren", "filter"]);
  });

  it("keeps a quoted multi-word value intact", () => {
    expect(shape(parse('moves:"dragon dance"').entries)[0]).toMatchObject({
      field: "moves",
      value: "dragon dance",
    });
  });

  it("reports an unknown field instead of dropping it silently", () => {
    const { entries, problems } = parse("nope:1 name:fros");
    expect(entries).toHaveLength(1);
    expect(problems).toEqual([{ text: "nope:1", reason: 'no field called "nope"' }]);
  });

  it("reports a value the field does not offer", () => {
    const { problems } = parse("class:banana");
    expect(problems[0].reason).toContain('no value "banana"');
  });

  it("reports a non-numeric value on a numeric field", () => {
    const { problems } = parse("bst>=lots");
    expect(problems[0].reason).toContain("not a number");
  });

  it("reports a bare word with no value", () => {
    const { problems } = parse("fros");
    expect(problems[0].reason).toContain("needs a value");
  });

  it("reads the move registry's own fields", () => {
    expect(shape(parse("category:physical", MOVES).entries)[0]).toMatchObject({
      field: "category",
      value: "physical",
    });
    expect(shape(parse("power>=100", MOVES).entries)[0]).toMatchObject({ field: "power" });
  });
});

describe("formatQuery / parseQuery round-trip", () => {
  const CASES = [
    "name:fros",
    "-class:mega",
    "name:fros -class:mega -class:legendary",
    "bst>=500",
    "bst<=500 atk>120 spe<50",
    "type:grass",
    "weak:fire",
    "resists:water",
    "evolution:level",
    "evolution:level>=45",
    "type:grass or type:fire",
    "type:grass or type:fire or type:water",
    "( type:grass or type:fire ) bst>=500",
    'moves:"dragon dance"',
    "edited:edited",
  ];

  for (const query of CASES) {
    it(`survives a round-trip: ${query}`, () => {
      const { entries, problems } = parse(query);
      expect(problems).toEqual([]);
      expect(formatQuery(entries, DEX)).toBe(query);
    });
  }

  it("round-trips entries built by the query line, not just typed text", () => {
    const built: FilterEntry[] = [
      { kind: "filter", id: "a", field: "name", value: "fros", connector: "AND", negated: false },
      { kind: "filter", id: "b", field: "class", value: "Mega", connector: "AND", negated: true },
      { kind: "filter", id: "c", field: "bst", value: "≥|500", connector: "OR", negated: false },
    ];
    const text = formatQuery(built, DEX);
    expect(text).toBe("name:fros -class:mega or bst>=500");
    expect(shape(parse(text).entries)).toEqual(shape(built));
  });
});

describe("suggest", () => {
  it("completes field keys from a fragment", () => {
    const codes = suggest("cl", DEX).map((s) => s.code);
    expect(codes.some((c) => c.startsWith("class:"))).toBe(true);
  });

  it("keeps the exclusion dash through a completion", () => {
    const rows = suggest("-cla", DEX);
    expect(rows[0].code.startsWith("-class")).toBe(true);
    expect(rows[0].complete.startsWith("-class")).toBe(true);
  });

  it("completes values once the key is separated", () => {
    const codes = suggest("class:", DEX).map((s) => s.code);
    expect(codes).toContain("class:mega");
    expect(codes).toContain("class:legendary");
  });

  it("narrows values by the typed fragment", () => {
    expect(suggest("class:meg", DEX).map((s) => s.code)).toEqual(["class:mega"]);
  });

  it("offers a numeric field its operator shape rather than a value list", () => {
    const rows = suggest("bst>=", DEX);
    expect(rows).toHaveLength(1);
    expect(rows[0].hint).toContain("number");
  });

  it("offers `or` once typing has started, never on an empty caret", () => {
    expect(suggest("o", DEX).some((s) => s.code === "or")).toBe(true);
    expect(suggest("", DEX).some((s) => s.code === "or")).toBe(false);
  });

  it("leads with text fields, not the stat columns the registry lists first", () => {
    const codes = suggest("", DEX).map((s) => s.code);
    expect(codes[0]).toBe("name:fros");
    // every text key outranks every numeric one
    expect(codes.indexOf("abilities:fros")).toBeLessThan(codes.indexOf("bst>=100"));
    expect(codes.indexOf("class:mega")).toBeLessThan(codes.indexOf("bst>=100"));
  });

  it("returns nothing for an unknown key", () => {
    expect(suggest("nope:", DEX)).toEqual([]);
  });

  it("flags the selectnum kinds that accept a number", () => {
    const level = suggest("evolution:lev", DEX)[0];
    expect(level.hint).toContain("accepts a number");
  });
});
