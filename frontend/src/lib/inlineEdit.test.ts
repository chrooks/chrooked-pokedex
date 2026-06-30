import { describe, expect, it } from "vitest";
import { applyInlineEdit } from "./inlineEdit";
import type { DexEntry } from "../types";

function entry(over: Partial<DexEntry> = {}): DexEntry {
  return {
    dex: 1,
    chrooked_id: "bulbasaur",
    name: "Bulbasaur",
    types: ["Grass", "Poison"],
    abilities: { primary: "Overgrow", secondary: null, hidden: "Chlorophyll" },
    stats: { hp: 45, atk: 49, def: 49, spa: 65, spd: 65, spe: 45 },
    learnset: [],
    evolution: null,
    evolves_into: [],
    fully_evolved: false,
    overridden_fields: [],
    base: {},
    ...over,
  };
}

describe("applyInlineEdit", () => {
  it("sets a stat override that differs from base", () => {
    const r = applyInlineEdit(entry(), null, { kind: "stat", key: "spe", value: 99 });
    expect(r.stats).toEqual({ spe: 99 });
  });

  it("drops a stat back to null when it matches base", () => {
    // base.stats holds the pre-override value; merged stats already show 99.
    const e = entry({ stats: { ...entry().stats, spe: 99 }, base: { stats: { spe: 45 } } });
    const r = applyInlineEdit(e, { ...skel(), stats: { spe: 99 } }, { kind: "stat", key: "spe", value: 45 });
    expect(r.stats).toBeNull();
  });

  it("writes a types override and clears it when set back to base", () => {
    const changed = applyInlineEdit(entry(), null, { kind: "types", type1: "Grass", type2: "" });
    expect(changed.types).toEqual(["Grass"]);
    const same = applyInlineEdit(entry(), null, { kind: "types", type1: "Grass", type2: "Poison" });
    expect(same.types).toBeNull();
  });

  it("sets one ability slot, leaving the others falling through to base", () => {
    const r = applyInlineEdit(entry(), null, { kind: "ability", slot: "secondary", name: "Sap Sipper" });
    expect(r.abilities).toEqual({ primary: null, secondary: "Sap Sipper", hidden: null });
  });

  it("nulls the abilities block when the only override is reverted", () => {
    const e = entry({ abilities: { primary: "Overgrow", secondary: "Sap Sipper", hidden: "Chlorophyll" }, base: { abilities: { primary: "Overgrow", secondary: null, hidden: "Chlorophyll" } } });
    const r = applyInlineEdit(e, { ...skel(), abilities: { primary: null, secondary: "Sap Sipper", hidden: null } }, { kind: "ability", slot: "secondary", name: "" });
    expect(r.abilities).toBeNull();
  });
});

function skel() {
  return {
    name: "Bulbasaur",
    chrooked_id: "bulbasaur",
    aka: { dex: 1 },
    types: null,
    abilities: null,
    stats: null,
    learnset: null,
    evolution: null,
  };
}
