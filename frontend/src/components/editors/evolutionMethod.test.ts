import { describe, expect, test } from "vitest";
import type { Evolution } from "../../types";
import { seedMethodForm, serializeMethod } from "./evolutionMethod";

function evo(method: Evolution["method"], detail?: Evolution["method_detail"]): Evolution {
  return { from: "abc", method, method_detail: detail };
}

describe("seedMethodForm", () => {
  test("seeds from a display string via method_detail (Level)", () => {
    const form = seedMethodForm(evo("Level 36", { kind: "Level", param: "36" }));
    expect(form.kind).toBe("level");
    expect(form.param).toBe("36");
  });

  test("seeds from a pokeemerald raw token (EVO_LEVEL → level)", () => {
    const form = seedMethodForm(evo("Level 36", { kind: "EVO_LEVEL", param: "36" }));
    expect(form.kind).toBe("level");
    expect(form.param).toBe("36");
  });

  test("seeds from a dict { level: 54 }", () => {
    const form = seedMethodForm(evo({ level: 54 }));
    expect(form.kind).toBe("level");
    expect(form.param).toBe("54");
  });

  test("seeds from a dict { item: 'FIRESTONE' }", () => {
    const form = seedMethodForm(evo({ item: "FIRESTONE" }));
    expect(form.kind).toBe("item");
    expect(form.param).toBe("FIRESTONE");
  });

  test("seeds an unknown string kind as Other carrying token + param", () => {
    const form = seedMethodForm(evo("Happiness", { kind: "HappinessDay", param: "" }));
    expect(form.kind).toBe("other");
    expect(form.rows[0].key).toBe("HappinessDay");
  });

  test("seeds an Other dict from Object.entries, not char-split", () => {
    const form = seedMethodForm(evo({ essentials: "HappinessDay", param: "Sun" }));
    expect(form.kind).toBe("other");
    const keys = form.rows.map((r) => r.key).sort();
    expect(keys).toEqual(["essentials", "param"]);
  });

  test("NEVER char-splits a string method (no 8 rows from 'Level 36')", () => {
    const form = seedMethodForm(evo("Level 36", { kind: "Level", param: "36" }));
    expect(form.rows.length).toBeLessThanOrEqual(1);
    // Crucially, no single-character keys leaked from the string.
    expect(form.rows.every((r) => r.key.length !== 1)).toBe(true);
  });

  test("falls back to Other (no char-split) when method_detail is absent", () => {
    const form = seedMethodForm(evo("Level 36"));
    expect(form.kind).toBe("other");
    expect(form.rows.length).toBe(1);
    expect(form.rows[0].key).toBe("");
  });

  test("null evolution seeds an empty Other form", () => {
    const form = seedMethodForm(null);
    expect(form.kind).toBe("other");
    expect(form.rows.length).toBe(1);
  });
});

describe("serializeMethod round-trip", () => {
  test("Level → { level: <int> }", () => {
    const form = seedMethodForm(evo({ level: 54 }));
    expect(serializeMethod(form)).toEqual({ level: 54 });
  });

  test("Level from string detail → { level: 36 }", () => {
    const form = seedMethodForm(evo("Level 36", { kind: "Level", param: "36" }));
    expect(serializeMethod(form)).toEqual({ level: 36 });
  });

  test("Item → { item: <string> }", () => {
    const form = seedMethodForm(evo({ item: "FIRESTONE" }));
    expect(serializeMethod(form)).toEqual({ item: "FIRESTONE" });
  });

  test("Other engine-hint shape round-trips with numeric coercion", () => {
    const form = seedMethodForm(evo({ essentials: "HappinessDay", param: "10" }));
    expect(serializeMethod(form)).toEqual({ essentials: "HappinessDay", param: 10 });
  });

  test("blank Level param serializes to empty dict", () => {
    expect(serializeMethod({ kind: "level", param: "", rows: [] })).toEqual({});
  });
});
