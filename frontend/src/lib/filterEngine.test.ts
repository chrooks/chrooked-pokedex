import { describe, it, expect } from "vitest";
import type { Ability, Move } from "../types";
import {
  appendNameFilter,
  applyFilter,
  evalEntries,
  type FilterEntry,
} from "./filterEngine";
import { MOVE_REGISTRY, buildMoveFilterDefs } from "./moveRegistry";
import { ABILITY_REGISTRY, buildAbilityFilterDefs } from "./abilityRegistry";

// --- fixtures ---------------------------------------------------------------

function makeMove(overrides: Partial<Move> = {}): Move {
  return {
    name: "Flamethrower",
    chrooked_id: "flamethrower",
    aka: {},
    type: "Fire",
    category: "special",
    power: 90,
    accuracy: 100,
    pp: 15,
    description: "A powerful fire attack that may burn.",
    effect: "",
    argument: null,
    additional_effects: [],
    flags: [],
    priority: 0,
    target: "Normal",
    overridden_fields: [],
    base: {},
    ...overrides,
  };
}

function makeAbility(overrides: Partial<Ability> = {}): Ability {
  return {
    name: "Blaze",
    chrooked_id: "blaze",
    description: "Powers up Fire moves in a pinch.",
    aka: {},
    overridden_fields: [],
    base: {},
    ...overrides,
  };
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

const moveDefs = buildMoveFilterDefs();
const abilityDefs = buildAbilityFilterDefs();
const moveDef = (f: string) => moveDefs.find((d) => d.field === f)!;
const abilityDef = (f: string) => abilityDefs.find((d) => d.field === f)!;

// --- move registry through the SAME evaluator (ac2) -------------------------

describe("move registry — numeric pow/acc/pp", () => {
  const move = makeMove({ power: 120, accuracy: 90, pp: 5 });
  it("compares power with the numeric operators", () => {
    expect(applyFilter(MOVE_REGISTRY, moveDef("power"), move, "≥|100")).toBe(true);
    expect(applyFilter(MOVE_REGISTRY, moveDef("power"), move, "<|100")).toBe(false);
  });
  it("compares accuracy and pp", () => {
    expect(applyFilter(MOVE_REGISTRY, moveDef("accuracy"), move, "=|90")).toBe(true);
    expect(applyFilter(MOVE_REGISTRY, moveDef("pp"), move, "≤|5")).toBe(true);
  });
  it("fails a null numeric cell rather than matching", () => {
    const status = makeMove({ power: null });
    expect(applyFilter(MOVE_REGISTRY, moveDef("power"), status, "≥|1")).toBe(false);
  });
});

describe("move registry — select type/category/flags/edited", () => {
  it("matches type and category exactly", () => {
    const move = makeMove({ type: "Water", category: "physical" });
    expect(applyFilter(MOVE_REGISTRY, moveDef("type"), move, "Water")).toBe(true);
    expect(applyFilter(MOVE_REGISTRY, moveDef("type"), move, "Fire")).toBe(false);
    expect(applyFilter(MOVE_REGISTRY, moveDef("category"), move, "physical")).toBe(true);
  });
  it("matches a flag the move carries", () => {
    const move = makeMove({ flags: ["contact", "punching"] });
    expect(applyFilter(MOVE_REGISTRY, moveDef("flags"), move, "punching")).toBe(true);
    expect(applyFilter(MOVE_REGISTRY, moveDef("flags"), move, "sound")).toBe(false);
  });
  it("matches edited state by overridden_fields", () => {
    const edited = makeMove({ overridden_fields: ["power"] });
    expect(applyFilter(MOVE_REGISTRY, moveDef("edited"), edited, "Edited")).toBe(true);
    expect(applyFilter(MOVE_REGISTRY, moveDef("edited"), edited, "Not edited")).toBe(false);
  });
});

describe("move registry — text name/description", () => {
  it("matches name accent- and case-insensitively", () => {
    const move = makeMove({ name: "Flabébé Beam" });
    expect(applyFilter(MOVE_REGISTRY, moveDef("name"), move, "flabebe")).toBe(true);
  });
  it("searches the description", () => {
    const move = makeMove({ description: "May lower the target's Speed." });
    expect(applyFilter(MOVE_REGISTRY, moveDef("description"), move, "speed")).toBe(true);
    expect(applyFilter(MOVE_REGISTRY, moveDef("description"), move, "freeze")).toBe(false);
  });
});

describe("move registry — boolean structure through evalEntries", () => {
  const move = makeMove({ type: "Fire", power: 90 });
  it("honors AND/OR precedence and parens", () => {
    // Type:Water OR Type:Fire AND Power≥200  ==  Water OR (Fire AND false) = false
    const flat = [filter("type", "Water"), filter("type", "Fire", "OR"), filter("power", "≥|200", "AND")];
    expect(evalEntries(MOVE_REGISTRY, move, flat)).toBe(false);
    // (Water OR Fire) AND Power≥50  ==  true AND true = true
    const grouped = [
      paren("("),
      filter("type", "Water"),
      filter("type", "Fire", "OR"),
      paren(")"),
      filter("power", "≥|50", "AND"),
    ];
    expect(evalEntries(MOVE_REGISTRY, move, grouped)).toBe(true);
  });
  it("negates a leaf with NOT", () => {
    expect(evalEntries(MOVE_REGISTRY, move, [filter("type", "Fire", "AND", true)])).toBe(false);
  });
  it("passes on an empty filter list", () => {
    expect(evalEntries(MOVE_REGISTRY, move, [])).toBe(true);
  });
  it("treats an empty text pill as a no-op even when negated", () => {
    // Regression: `NOT <empty text>` must not invert the "matches everything"
    // pass into "matches nothing" — an inert leaf stays inert.
    expect(evalEntries(MOVE_REGISTRY, move, [filter("name", "")])).toBe(true);
    expect(evalEntries(MOVE_REGISTRY, move, [filter("name", "", "AND", true)])).toBe(true);
  });
});

// --- ability registry through the SAME evaluator (ac2) ----------------------

describe("ability registry — select edited, text name/description", () => {
  it("matches edited state", () => {
    const edited = makeAbility({ overridden_fields: ["description"] });
    expect(applyFilter(ABILITY_REGISTRY, abilityDef("edited"), edited, "Edited")).toBe(true);
    const base = makeAbility();
    expect(applyFilter(ABILITY_REGISTRY, abilityDef("edited"), base, "Not edited")).toBe(true);
  });
  it("searches name and description", () => {
    const ability = makeAbility({ name: "Drizzle", description: "Summons rain on entry." });
    expect(applyFilter(ABILITY_REGISTRY, abilityDef("name"), ability, "drizzle")).toBe(true);
    expect(applyFilter(ABILITY_REGISTRY, abilityDef("description"), ability, "rain")).toBe(true);
    expect(applyFilter(ABILITY_REGISTRY, abilityDef("description"), ability, "sand")).toBe(false);
  });
  it("composes through evalEntries with NOT", () => {
    const ability = makeAbility({ description: "Summons rain on entry." });
    const expr = [filter("description", "rain"), filter("name", "torrent", "AND", true)];
    expect(evalEntries(ABILITY_REGISTRY, ability, expr)).toBe(true); // rain AND NOT(name~torrent)
  });
});

describe("appendNameFilter — shared across registries", () => {
  it("appends a Name pill carrying the trimmed query", () => {
    const next = appendNameFilter([], "  fla  ", "id1");
    expect(next).toHaveLength(1);
    expect(next[0]).toMatchObject({ kind: "filter", field: "name", value: "fla" });
  });
  it("no-ops (same reference) on a blank query", () => {
    const tree = [filter("name", "Blaze")];
    expect(appendNameFilter(tree, "   ", "id1")).toBe(tree);
  });
});
