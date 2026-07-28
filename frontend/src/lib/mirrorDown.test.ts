import { describe, expect, it } from "vitest";
import {
  copyDownLearnset,
  lineMembers,
  mirrorDownPreview,
  mirrorRows,
  postEvos,
  preEvos,
} from "./mirrorDown";
import type { AbilitySlots, DexEntry } from "../types";

const ABILITIES: AbilitySlots = { primary: "Sap Sipper", secondary: null, hidden: "Gooey" };

// `into` is the chrooked_id this species evolves INTO (the reliable forward edge).
// `evolution.from` is deliberately set to a DISPLAY NAME (capitalized) to prove
// preEvos resolves the line from forward edges, not that unreliable field.
function mon(id: string, name: string, into: string | null, fromName?: string): DexEntry {
  return {
    chrooked_id: id,
    name,
    dex: null,
    types: ["Dragon"],
    abilities: ABILITIES,
    stats: {},
    learnset: [],
    evolution: fromName ? { from: fromName, method: { level: 40 } } : null,
    evolves_into: into
      ? [{ to: into, to_name: into, to_dex: null, method: "Level 40" }]
      : [],
    fully_evolved: into === null,
    overridden_fields: [],
    base: {},
  } as unknown as DexEntry;
}

const goomy = mon("goomy", "Goomy", "sliggoo");
const sliggoo = mon("sliggoo", "Sliggoo", "goodra", "Goomy");
const goodra = mon("goodra", "Goodra", null, "Sliggoo");
const byId = new Map([goomy, sliggoo, goodra].map((m) => [m.chrooked_id, m]));

describe("preEvos", () => {
  it("walks backward to the base in order", () => {
    expect(preEvos(goodra, byId).map((m) => m.chrooked_id)).toEqual(["goomy", "sliggoo"]);
  });

  it("is empty for a base species", () => {
    expect(preEvos(goomy, byId)).toEqual([]);
  });

  it("treats a form variant of the pre-evo as the same parent, not a branch", () => {
    // joltik AND joltik--riftform both evolve into galvantula. That is one
    // logical pre-evo (a base + its form), not a two-species branch — the line
    // must resolve to the BASE form joltik, not bail as if it were ambiguous.
    const joltik = mon("joltik", "Joltik", "galvantula");
    const joltikRift = mon("joltik--riftform", "Joltik (Rift)", "galvantula");
    const galvantula = mon("galvantula", "Galvantula", null, "Joltik");
    const line = new Map(
      [joltik, joltikRift, galvantula].map((m) => [m.chrooked_id, m]),
    );
    expect(preEvos(galvantula, line).map((m) => m.chrooked_id)).toEqual(["joltik"]);
  });
});

describe("postEvos", () => {
  it("walks forward to the tip in order", () => {
    expect(postEvos(goomy, byId).map((m) => m.chrooked_id)).toEqual([
      "sliggoo",
      "goodra",
    ]);
  });

  it("is empty for a fully-evolved species", () => {
    expect(postEvos(goodra, byId)).toEqual([]);
  });
});

describe("lineMembers", () => {
  it("returns the whole line base→tip from any member", () => {
    for (const member of [goomy, sliggoo, goodra]) {
      expect(lineMembers(member, byId).map((m) => m.chrooked_id)).toEqual([
        "goomy",
        "sliggoo",
        "goodra",
      ]);
    }
  });
});

describe("copyDownLearnset — anchor minus L0", () => {
  it("drops L0 on-evolution rows and sorts by level", () => {
    const anchor = [
      { level: 0, move: "Dragon Pulse" },
      { level: 20, move: "Dragon Breath" },
      { level: 1, move: "Tackle" },
    ];
    expect(copyDownLearnset(anchor)).toEqual([
      { level: 1, move: "Tackle" },
      { level: 20, move: "Dragon Breath" },
    ]);
  });
});

describe("mirrorDownPreview — the whole-line write plan", () => {
  it("gives each pre-evo the anchor kit and the copy-down learnset", () => {
    const kit = {
      types: ["Water", "Dragon"],
      abilities: ABILITIES,
      learnset: [
        { level: 0, move: "Dragon Pulse" },
        { level: 1, move: "Tackle" },
        { level: 20, move: "Dragon Breath" },
      ],
    };
    const rows = mirrorDownPreview(goodra, byId, kit);
    expect(rows.map((r) => r.chrooked_id)).toEqual(["goomy", "sliggoo"]);
    expect(rows[0].types).toEqual(["Water", "Dragon"]);
    expect(rows[0].learnset).toEqual([
      { level: 1, move: "Tackle" },
      { level: 20, move: "Dragon Breath" },
    ]);
    // The stripped L0 is surfaced for the "minus L0" annotation.
    expect(rows[0].strippedL0).toEqual(["Dragon Pulse"]);
  });

  it("mirror-only journey: copies the anchor's CURRENT kit and never touches the anchor", () => {
    // No design stage ran — the kit is the final evo's current types/abilities/
    // learnset. The preview must yield only pre-evo copies (the anchor's own
    // fields are left untouched — it is absent from the write plan).
    const anchor = { ...goodra, types: ["Dragon"], learnset: [
      { level: 0, move: "Dragon Pulse" },
      { level: 30, move: "Dragon Breath" },
    ] } as typeof goodra;
    const rows = mirrorDownPreview(anchor, byId, {
      types: anchor.types,
      abilities: anchor.abilities,
      learnset: anchor.learnset,
    });
    expect(rows.map((r) => r.chrooked_id)).toEqual(["goomy", "sliggoo"]);
    expect(rows.map((r) => r.chrooked_id)).not.toContain("goodra");
    expect(rows[0].learnset).toEqual([{ level: 30, move: "Dragon Breath" }]);
  });
});

describe("mirrorRows — arbitrary recipients (the mirror wizard)", () => {
  it("carries the kit (stats included) to any recipient set", () => {
    const stats = { hp: 90, atk: 100, def: 70, spa: 110, spd: 150, spe: 80 };
    const rows = mirrorRows(
      {
        types: ["Dragon"],
        abilities: ABILITIES,
        stats,
        learnset: [{ level: 5, move: "Rain Dance" }],
      },
      [goomy, goodra],
    );
    expect(rows.map((r) => r.chrooked_id)).toEqual(["goomy", "goodra"]);
    expect(rows[0].stats).toEqual(stats);
    expect(rows[1].learnset).toEqual([{ level: 5, move: "Rain Dance" }]);
  });
});
