import { describe, expect, it } from "vitest";
import {
  MAX_SAVED,
  SAVED_FILTERS_KEY,
  deleteExpression,
  expressionsFor,
  loadSavedFilters,
  saveExpression,
} from "./savedFilters";
import type { StorageLike } from "./savedTeams";

function fakeStorage(seed: string | null = null): StorageLike & { value: string | null } {
  return {
    value: seed,
    getItem() {
      return this.value;
    },
    setItem(_key: string, value: string) {
      this.value = value;
    },
  };
}

describe("savedFilters", () => {
  it("round-trips an expression under its entity", () => {
    const storage = fakeStorage();
    saveExpression(storage, "dexc", "Frost line", "ENCODED");
    expect(expressionsFor(storage, "dexc")).toEqual({ "Frost line": "ENCODED" });
  });

  it("keeps entities apart so a dex expression never lands on moves", () => {
    const storage = fakeStorage();
    saveExpression(storage, "dexc", "Mine", "DEX");
    saveExpression(storage, "movesc", "Mine", "MOVES");
    expect(expressionsFor(storage, "dexc")).toEqual({ Mine: "DEX" });
    expect(expressionsFor(storage, "movesc")).toEqual({ Mine: "MOVES" });
  });

  it("overwrites by name rather than duplicating", () => {
    const storage = fakeStorage();
    saveExpression(storage, "dexc", "A", "ONE");
    saveExpression(storage, "dexc", "A", "TWO");
    expect(expressionsFor(storage, "dexc")).toEqual({ A: "TWO" });
  });

  it("rejects a blank name and an empty expression", () => {
    const storage = fakeStorage();
    saveExpression(storage, "dexc", "   ", "ENCODED");
    saveExpression(storage, "dexc", "Named", "");
    expect(expressionsFor(storage, "dexc")).toEqual({});
  });

  it("caps new names but still allows overwriting an existing one", () => {
    const storage = fakeStorage();
    for (let i = 0; i < MAX_SAVED; i += 1) saveExpression(storage, "dexc", `n${i}`, `v${i}`);
    saveExpression(storage, "dexc", "one too many", "X");
    expect(Object.keys(expressionsFor(storage, "dexc"))).toHaveLength(MAX_SAVED);
    saveExpression(storage, "dexc", "n0", "REPLACED");
    expect(expressionsFor(storage, "dexc").n0).toBe("REPLACED");
  });

  it("deletes by name and ignores an absent one", () => {
    const storage = fakeStorage();
    saveExpression(storage, "dexc", "A", "ONE");
    deleteExpression(storage, "dexc", "nope");
    expect(expressionsFor(storage, "dexc")).toEqual({ A: "ONE" });
    deleteExpression(storage, "dexc", "A");
    expect(expressionsFor(storage, "dexc")).toEqual({});
  });

  it("collapses corrupt or foreign data to empty instead of throwing", () => {
    expect(loadSavedFilters(fakeStorage("{not json"))).toEqual({});
    expect(loadSavedFilters(fakeStorage('["array"]'))).toEqual({});
    expect(loadSavedFilters(fakeStorage('{"dexc":{"a":42}}'))).toEqual({});
    expect(loadSavedFilters(fakeStorage('{"dexc":"scalar"}'))).toEqual({});
  });

  it("writes under the versioned key", () => {
    const storage = fakeStorage();
    saveExpression(storage, "dexc", "A", "ONE");
    expect(SAVED_FILTERS_KEY).toBe("chrooked-saved-filters-v1");
    expect(JSON.parse(storage.value ?? "{}")).toEqual({ dexc: { A: "ONE" } });
  });
});
