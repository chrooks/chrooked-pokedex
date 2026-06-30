import { describe, expect, test } from "vitest";
import type { CanonicalMethod, Evolution } from "../../types";
import { ADVANCED_ID, seedMethodForm, serializeMethod } from "./evolutionMethod";

// A stand-in for GET /api/meta/evolution-methods (subset is enough for tests).
const METHODS: CanonicalMethod[] = [
  { id: "level", label: "Level", value_kind: "level", tokens: ["EVO_LEVEL", "Level"] },
  { id: "friendship", label: "Friendship", value_kind: "none", tokens: ["EVO_FRIENDSHIP", "Happiness"] },
  { id: "item", label: "Use item", value_kind: "item", tokens: ["EVO_ITEM", "Item"] },
  { id: "trade", label: "Trade", value_kind: "none", tokens: ["EVO_TRADE", "Trade"] },
  { id: "knows_move", label: "Knows move", value_kind: "move", tokens: ["EVO_MOVE", "HasMove"] },
];

function evo(method: Evolution["method"], detail?: Evolution["method_detail"]): Evolution {
  return { from: "abc", method, method_detail: detail };
}

describe("seedMethodForm", () => {
  test("seeds a clean { level: 54 } dict", () => {
    const form = seedMethodForm(evo({ level: 54 }), METHODS);
    expect(form.id).toBe("level");
    expect(form.value).toBe("54");
  });

  test("seeds a clean { item } dict", () => {
    const form = seedMethodForm(evo({ item: "FIRESTONE" }), METHODS);
    expect(form.id).toBe("item");
    expect(form.value).toBe("FIRESTONE");
  });

  test("seeds a canonical { method, param } dict", () => {
    const form = seedMethodForm(evo({ method: "knows_move", param: "Mimic" }), METHODS);
    expect(form.id).toBe("knows_move");
    expect(form.value).toBe("Mimic");
  });

  test("seeds a none-kind canonical method from a backdrop token (EVO_TRADE → trade)", () => {
    const form = seedMethodForm(evo("Trade", { kind: "EVO_TRADE", param: "" }), METHODS);
    expect(form.id).toBe("trade");
  });

  test("seeds level from a backdrop string via method_detail (clean integer is safe)", () => {
    const form = seedMethodForm(evo("Level 36", { kind: "EVO_LEVEL", param: "36" }), METHODS);
    expect(form.id).toBe("level");
    expect(form.value).toBe("36");
  });

  test("routes a move/item backdrop detail to Advanced (engine-formatted param is unsafe to seed)", () => {
    const form = seedMethodForm(evo("Knows Mimic", { kind: "EVO_MOVE", param: "MOVE_MIMIC" }), METHODS);
    expect(form.id).toBe(ADVANCED_ID);
    expect(form.rawToken).toBe("EVO_MOVE");
    expect(form.rawParam).toBe("MOVE_MIMIC");
  });

  test("seeds a raw engine-hint dict as Advanced", () => {
    const form = seedMethodForm(evo({ pokeemerald: "EVO_LEVEL_FOG", param: "35" }), METHODS);
    expect(form.id).toBe(ADVANCED_ID);
    expect(form.rawEngine).toBe("pokeemerald");
    expect(form.rawToken).toBe("EVO_LEVEL_FOG");
    expect(form.rawParam).toBe("35");
  });

  test("never char-splits a string method with no detail", () => {
    const form = seedMethodForm(evo("Level 36"), METHODS);
    expect(form.id).toBe("level"); // empty default
    expect(form.value).toBe("");
  });

  test("null evolution seeds an empty Level form", () => {
    const form = seedMethodForm(null, METHODS);
    expect(form.id).toBe("level");
    expect(form.value).toBe("");
  });
});

describe("serializeMethod round-trip", () => {
  test("Level → { level: <int> }", () => {
    const form = seedMethodForm(evo({ level: 54 }), METHODS);
    expect(serializeMethod(form, METHODS)).toEqual({ level: 54 });
  });

  test("Item → { item }", () => {
    const form = seedMethodForm(evo({ item: "FIRESTONE" }), METHODS);
    expect(serializeMethod(form, METHODS)).toEqual({ item: "FIRESTONE" });
  });

  test("none-kind method → { method } (no param)", () => {
    const form = seedMethodForm(evo({ method: "trade" }), METHODS);
    expect(serializeMethod(form, METHODS)).toEqual({ method: "trade" });
  });

  test("move method → { method, param }", () => {
    const form = seedMethodForm(evo({ method: "knows_move", param: "Mimic" }), METHODS);
    expect(serializeMethod(form, METHODS)).toEqual({ method: "knows_move", param: "Mimic" });
  });

  test("Advanced escape round-trips with numeric coercion", () => {
    const form = seedMethodForm(evo({ essentials: "HappinessDay", param: "10" }), METHODS);
    expect(serializeMethod(form, METHODS)).toEqual({ essentials: "HappinessDay", param: 10 });
  });

  test("blank Level value serializes to empty dict", () => {
    expect(
      serializeMethod(
        { id: "level", value: "", rawEngine: "pokeemerald", rawToken: "", rawParam: "" },
        METHODS,
      ),
    ).toEqual({});
  });
});
