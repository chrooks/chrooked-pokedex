/* ac12 — the line strip before→after diff: changed/unchanged per facet, the
   learnset added/removed/moved split, facts-over-entry precedence, and the
   all-unchanged case. Pure, node env. */

import { describe, it, expect } from "vitest";
import type { DexEntry } from "../types";
import { diffLearnset, diffProfile, snapshotProfile } from "./profileDiff";

function entry(over: Partial<DexEntry> = {}): DexEntry {
  return {
    dex: 706,
    chrooked_id: "goodra",
    name: "Goodra",
    types: ["Dragon"],
    abilities: { primary: "Sap Sipper", secondary: "Hydration", hidden: "Gooey" },
    stats: { hp: 90, atk: 100, def: 70, spa: 110, spd: 150, spe: 80 },
    learnset: [
      { level: 0, move: "Dragon Breath" },
      { level: 5, move: "Bubble" },
      { level: 15, move: "Rain Dance" },
    ],
    evolution: null,
    evolves_into: [],
    fully_evolved: true,
    overridden_fields: [],
    base: {},
    ...over,
  };
}

describe("snapshotProfile", () => {
  it("copies arrays/objects so a later entry mutation cannot rewrite the baseline", () => {
    const e = entry();
    const snap = snapshotProfile(e);
    e.types.push("Steel");
    e.stats.hp = 1;
    e.learnset.push({ level: 99, move: "Boom" });
    expect(snap.types).toEqual(["Dragon"]);
    expect(snap.stats.hp).toBe(90);
    expect(snap.learnset).toHaveLength(3);
  });
});

describe("diffProfile — per-facet changed flags", () => {
  it("flags no change when the entry matches the baseline", () => {
    const before = snapshotProfile(entry());
    const diff = diffProfile(before, entry(), {});
    expect(diff.types.changed).toBe(false);
    expect(diff.stats.changed).toBe(false);
    expect(diff.abilities.changed).toBe(false);
    expect(diff.learnset.added).toHaveLength(0);
    expect(diff.learnset.removed).toHaveLength(0);
    expect(diff.learnset.moved).toHaveLength(0);
  });

  it("flags a typing change from facts", () => {
    const before = snapshotProfile(entry());
    const diff = diffProfile(before, entry(), { types: ["Dragon", "Steel"] });
    expect(diff.types.changed).toBe(true);
    expect(diff.types.before).toEqual(["Dragon"]);
    expect(diff.types.after).toEqual(["Dragon", "Steel"]);
  });

  it("flags a stat change and carries before/after spreads", () => {
    const before = snapshotProfile(entry());
    const diff = diffProfile(before, entry(), {
      stats: { hp: 90, atk: 130, def: 70, spa: 110, spd: 150, spe: 90 },
    });
    expect(diff.stats.changed).toBe(true);
    expect(diff.stats.after.atk).toBe(130);
    expect(diff.stats.before.atk).toBe(100);
  });

  it("flags an ability change", () => {
    const before = snapshotProfile(entry());
    const diff = diffProfile(before, entry(), {
      abilities: { primary: "Water Absorb", secondary: "Hydration", hidden: "Gooey" },
    });
    expect(diff.abilities.changed).toBe(true);
  });
});

describe("diffProfile — facts win over entry", () => {
  it("uses facts for a facet locked this session even when the entry disagrees", () => {
    const before = snapshotProfile(entry());
    // entry still shows the old typing, but facts recorded the session's lock.
    const diff = diffProfile(before, entry({ types: ["Dragon"] }), { types: ["Water"] });
    expect(diff.types.after).toEqual(["Water"]);
    expect(diff.types.changed).toBe(true);
  });

  it("falls back to the entry for a facet not locked this session", () => {
    const before = snapshotProfile(entry());
    // a stat change already committed (entry differs), no facts entry for stats.
    const diff = diffProfile(before, entry({ stats: { ...entry().stats, spe: 120 } }), {});
    expect(diff.stats.after.spe).toBe(120);
    expect(diff.stats.changed).toBe(true);
  });
});

describe("diffLearnset", () => {
  it("splits added, removed, and moved", () => {
    const before = [
      { level: 0, move: "Dragon Breath" },
      { level: 5, move: "Bubble" },
      { level: 15, move: "Rain Dance" },
    ];
    const after = [
      { level: 0, move: "Dragon Breath" }, // kept
      { level: 9, move: "Bubble" }, // moved 5 -> 9
      { level: 20, move: "Muddy Water" }, // added
      // Rain Dance dropped
    ];
    const diff = diffLearnset(before, after);
    expect(diff.added).toEqual([{ level: 20, move: "Muddy Water" }]);
    expect(diff.removed).toEqual([{ level: 15, move: "Rain Dance" }]);
    expect(diff.moved).toEqual([{ move: "Bubble", from: 5, to: 9 }]);
  });

  it("is empty when the lists match", () => {
    const rows = [
      { level: 1, move: "Tackle" },
      { level: 7, move: "Bubble" },
    ];
    const diff = diffLearnset(rows, [...rows]);
    expect(diff.added).toHaveLength(0);
    expect(diff.removed).toHaveLength(0);
    expect(diff.moved).toHaveLength(0);
  });

  it("treats a pure addition as added, a pure drop as removed", () => {
    const diff = diffLearnset(
      [{ level: 1, move: "Tackle" }],
      [
        { level: 1, move: "Tackle" },
        { level: 3, move: "Growl" },
      ],
    );
    expect(diff.added).toEqual([{ level: 3, move: "Growl" }]);
    expect(diff.removed).toHaveLength(0);

    const diff2 = diffLearnset(
      [
        { level: 1, move: "Tackle" },
        { level: 3, move: "Growl" },
      ],
      [{ level: 1, move: "Tackle" }],
    );
    expect(diff2.removed).toEqual([{ level: 3, move: "Growl" }]);
    expect(diff2.added).toHaveLength(0);
  });
});
