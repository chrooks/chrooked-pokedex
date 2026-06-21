/* ac8 (logic) — the ledger auto-expands when any section has an active proposal,
   honours a manual collapse, and restores when every proposal clears. Pure set
   logic, so the invariant is provable without a DOM. */

import { describe, it, expect } from "vitest";
import { shouldExpandLedger, updateActiveSet } from "./activeProposals";

describe("updateActiveSet", () => {
  it("adds an id when a section becomes active (no mutation)", () => {
    const before = new Set<string>();
    const after = updateActiveSet(before, "abilities", true);
    expect(after.has("abilities")).toBe(true);
    expect(before.size).toBe(0); // immutable — original untouched
  });

  it("removes an id when a section goes idle again", () => {
    const before = new Set(["abilities", "learnset"]);
    const after = updateActiveSet(before, "abilities", false);
    expect(after.has("abilities")).toBe(false);
    expect(after.has("learnset")).toBe(true);
  });

  it("is idempotent (re-adding / removing-absent is a no-op clone)", () => {
    const set = new Set(["learnset"]);
    expect([...updateActiveSet(set, "learnset", true)]).toEqual(["learnset"]);
    expect([...updateActiveSet(set, "abilities", false)]).toEqual(["learnset"]);
  });
});

describe("shouldExpandLedger", () => {
  it("stays narrow when no section is active (idle restores width)", () => {
    expect(shouldExpandLedger(new Set(), false)).toBe(false);
  });

  it("widens when at least one section is active", () => {
    expect(shouldExpandLedger(new Set(["learnset"]), false)).toBe(true);
  });

  it("manual collapse wins over an active proposal", () => {
    expect(shouldExpandLedger(new Set(["learnset"]), true)).toBe(false);
  });

  it("restores narrow once every proposal clears, even if never collapsed", () => {
    const cleared = updateActiveSet(new Set(["learnset"]), "learnset", false);
    expect(shouldExpandLedger(cleared, false)).toBe(false);
  });
});
