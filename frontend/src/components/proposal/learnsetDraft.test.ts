/* ac3/ac4/ac5/ac7 (logic) — the learnset section's pure draft logic: autosort,
   the aligned-by-level diff (added / removed), inline edit + reorder, the
   alternative swap (whole list), and the draft→Override merge (whole-list,
   reasoning stripped, untouched fields kept). */

import { describe, it, expect } from "vitest";
import type { LearnsetMove, SpeciesOverride } from "../../types";
import {
  addRow,
  adjustSelectedLevels,
  applyAlternative,
  classifyProposed,
  editRow,
  learnsetChanged,
  mergeDraft,
  parseAltRow,
  removedRows,
  removeRow,
  removeSelectedMoves,
  sortMoves,
  swapRowLevels,
} from "./learnsetDraft";

describe("learnset draft — bulk edits", () => {
  const draft = {
    learnset: [
      { level: 5, move: "Tackle" },
      { level: 10, move: "Ember" },
      { level: 15, move: "Bite" },
    ],
  };

  it("removes selected moves and keeps the list sorted", () => {
    const next = removeSelectedMoves(draft, new Set(["Tackle", "Bite"]));
    expect(next.learnset).toEqual([{ level: 10, move: "Ember" }]);
  });

  it("removeRow drops one row by index, keeping a same-move sibling", () => {
    const withDup = {
      learnset: [
        { level: 0, move: "Ember" },
        { level: 10, move: "Ember" },
        { level: 5, move: "Tackle" },
      ],
    };
    // Remove the L10 Ember (index 1 after the draft's own order); the L0 Ember stays.
    const next = removeRow(withDup, 1);
    expect(next.learnset).toEqual([
      { level: 0, move: "Ember" },
      { level: 5, move: "Tackle" },
    ]);
  });

  it("removeRow on an empty/null draft is a no-op", () => {
    expect(removeRow(null, 0).learnset).toEqual([]);
  });

  it("nudges selected levels by delta, re-sorting", () => {
    const next = adjustSelectedLevels(draft, new Set(["Bite"]), -12);
    expect(next.learnset).toEqual([
      { level: 3, move: "Bite" },
      { level: 5, move: "Tackle" },
      { level: 10, move: "Ember" },
    ]);
  });

  it("clamps nudged levels to [0, 100]", () => {
    const low = adjustSelectedLevels(draft, new Set(["Tackle"]), -50);
    expect(low.learnset[0]).toEqual({ level: 0, move: "Tackle" });
    const high = adjustSelectedLevels(draft, new Set(["Bite"]), 200);
    expect(high.learnset[high.learnset.length - 1]).toEqual({
      level: 100,
      move: "Bite",
    });
  });
});

describe("learnset draft — autosort (ac4)", () => {
  it("sorts level-ascending, ties by move name", () => {
    const sorted = sortMoves([
      { level: 10, move: "Surf" },
      { level: 1, move: "Tackle" },
      { level: 10, move: "Bubble" },
    ]);
    expect(sorted.map((m) => `${m.level}:${m.move}`)).toEqual([
      "1:Tackle",
      "10:Bubble",
      "10:Surf",
    ]);
  });

  it("editRow changes a row's level then re-sorts (autosort on edit)", () => {
    const draft = {
      learnset: [
        { level: 1, move: "Tackle" },
        { level: 5, move: "Growl" },
      ],
    };
    const next = editRow(draft, 0, { level: 9 });
    expect(next.learnset.map((m) => m.move)).toEqual(["Growl", "Tackle"]);
  });
});

describe("learnset draft — diff (ac3)", () => {
  const current: LearnsetMove[] = [
    { level: 1, move: "Tackle" },
    { level: 7, move: "Bubble" },
  ];

  it("flags a proposed row absent from current as added", () => {
    const classified = classifyProposed(current, [
      { level: 1, move: "Tackle" },
      { level: 12, move: "Hydro Pump" },
    ]);
    const added = classified.filter((c) => c.status === "added").map((c) => c.row.move);
    expect(added).toEqual(["Hydro Pump"]);
  });

  it("flags a current row dropped by the proposal as removed", () => {
    const dropped = removedRows(current, [{ level: 1, move: "Tackle" }]);
    expect(dropped.map((m) => m.move)).toEqual(["Bubble"]);
  });

  it("learnsetChanged is true when the set differs, false when identical", () => {
    expect(learnsetChanged(current, [{ level: 1, move: "Tackle" }])).toBe(true);
    expect(
      learnsetChanged(current, [
        { level: 7, move: "Bubble" },
        { level: 1, move: "Tackle" },
      ]),
    ).toBe(false);
  });
});

describe("learnset draft — add row", () => {
  it("appends a new row and keeps the list sorted", () => {
    const next = addRow({ learnset: [{ level: 10, move: "Ember" }] }, { level: 3, move: "Tackle" });
    expect(next.learnset).toEqual([
      { level: 3, move: "Tackle" },
      { level: 10, move: "Ember" },
    ]);
  });

  it("dedupes an exact (level, move) add (case-insensitive)", () => {
    const next = addRow({ learnset: [{ level: 5, move: "Tackle" }] }, { level: 5, move: "tackle" });
    expect(next.learnset).toEqual([{ level: 5, move: "Tackle" }]);
  });

  it("ignores an empty move name", () => {
    const next = addRow({ learnset: [{ level: 5, move: "Tackle" }] }, { level: 8, move: "  " });
    expect(next.learnset).toEqual([{ level: 5, move: "Tackle" }]);
  });
});

describe("learnset draft — parse free-text alternative", () => {
  const pool = ["Aqua Jet", "Hydro Pump", "Tackle"];

  it("pulls the move name (pinned to the pool) and the @L level", () => {
    expect(parseAltRow("Aqua Jet @ L24 — priority STAB option", pool)).toEqual({
      level: 24,
      move: "Aqua Jet",
    });
  });

  it("prefers the longest pool match, so a substring name doesn't win", () => {
    expect(parseAltRow("add Hydro Pump at level 40", pool)?.move).toBe("Hydro Pump");
  });

  it("falls back to the text head when no pool is given", () => {
    expect(parseAltRow("Bubble @ 12")).toEqual({ level: 12, move: "Bubble" });
  });
});

describe("learnset draft — alternative swap (ac3)", () => {
  it("a list-valued alternative replaces the whole draft, sorted", () => {
    const next = applyAlternative(
      { learnset: [{ level: 1, move: "Old" }] },
      {
        value: [
          { level: 5, move: "B" },
          { level: 1, move: "A" },
        ],
        rationale: "runner-up curve",
      },
    );
    expect(next.learnset.map((m) => m.move)).toEqual(["A", "B"]);
  });

  it("a STRING-valued alternative adds the parsed row (the real Seam shape)", () => {
    // The suggest backend forces alternatives[].value to be a string; a click must
    // still yield a distinct draft the UI re-derives from.
    const before = { learnset: [{ level: 1, move: "Tackle" }] };
    const next = applyAlternative(before, {
      value: "Aqua Jet @ L24 — priority STAB",
      rationale: "coverage",
    }, ["Aqua Jet", "Tackle"]);
    expect(next).not.toBe(before);
    expect(next.learnset).toEqual([
      { level: 1, move: "Tackle" },
      { level: 24, move: "Aqua Jet" },
    ]);
  });
});

describe("learnset draft — merge (ac5)", () => {
  function raw(): SpeciesOverride {
    return {
      name: "Bulbasaur",
      chrooked_id: "bulbasaur",
      aka: { dex: 1 },
      types: ["Grass", "Poison"],
      abilities: { primary: "Overgrow", secondary: null, hidden: "Chlorophyll" },
      stats: null,
      learnset: null,
      evolution: null,
    };
  }

  it("writes a sorted whole list, stripping reasoning", () => {
    const merged = mergeDraft(raw(), {
      learnset: [
        { level: 7, move: "Vine Whip", reasoning: "early STAB" },
        { level: 1, move: "Tackle", reasoning: "filler" },
      ],
    });
    expect(merged.learnset).toEqual([
      { level: 1, move: "Tackle" },
      { level: 7, move: "Vine Whip" },
    ]);
  });

  it("never clobbers untouched Override fields (abilities/types survive)", () => {
    const merged = mergeDraft(raw(), { learnset: [{ level: 1, move: "Tackle" }] });
    expect(merged.abilities).toEqual({
      primary: "Overgrow",
      secondary: null,
      hidden: "Chlorophyll",
    });
    expect(merged.types).toEqual(["Grass", "Poison"]);
  });
});

describe("swapRowLevels", () => {
  const draft = {
    learnset: [
      { level: 5, move: "Fury Cutter" },
      { level: 12, move: "Fell Stinger" },
      { level: 20, move: "Bug Bite" },
    ],
  };

  it("exchanges two rows' levels and re-sorts", () => {
    const out = swapRowLevels(draft, 0, 1);
    expect(out.learnset).toEqual([
      { level: 5, move: "Fell Stinger" },
      { level: 12, move: "Fury Cutter" },
      { level: 20, move: "Bug Bite" },
    ]);
  });

  it("leaves every other row untouched", () => {
    const out = swapRowLevels(draft, 0, 2);
    expect(out.learnset.find((r) => r.move === "Fell Stinger")).toEqual({
      level: 12,
      move: "Fell Stinger",
    });
  });

  it("is a no-op for the same index", () => {
    expect(swapRowLevels(draft, 1, 1).learnset).toEqual(draft.learnset);
  });

  it("is a no-op for an out-of-range index", () => {
    expect(swapRowLevels(draft, 0, 99).learnset).toEqual(draft.learnset);
    expect(swapRowLevels(draft, -1, 0).learnset).toEqual(draft.learnset);
  });

  it("handles a null draft", () => {
    expect(swapRowLevels(null, 0, 1).learnset).toEqual([]);
  });
});
