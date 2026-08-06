import { describe, expect, it } from "vitest";
import {
  copyDownLearnset,
  lineMembers,
  mirrorDownPreview,
  mirrorRows,
  postEvos,
  preEvos,
  scaleStats,
  sharedOutsideLine,
} from "./mirrorDown";
import { bst } from "./format";
import type { AbilitySlots, DexEntry } from "../types";

/** A copy of `entry` with a spread — and optionally the canon one the Ruleset
    overrode, which is what the scale must measure against. */
function withStats(
  entry: DexEntry,
  stats: Record<string, number>,
  canon?: Record<string, number>,
): DexEntry {
  return { ...entry, stats, base: canon ? { stats: canon } : {} } as DexEntry;
}

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

  it("keeps a form line on its form — a lone form parent is never collapsed to base", () => {
    // The rejuv target dex shape: goodra--hisuianform's ONLY parent is
    // sliggoo--hisuianform. Collapsing that lone parent to the base stem put
    // regular Sliggoo in Goodra Hisui's mirror list.
    const line = new Map(
      [
        mon("goomy", "Goomy", "sliggoo--hisuianform"),
        mon("sliggoo", "Sliggoo", "goodra"),
        mon("sliggoo--hisuianform", "Sliggoo Hisui", "goodra--hisuianform", "Goomy"),
        mon("goodra", "Goodra", null, "Sliggoo"),
        mon("goodra--hisuianform", "Goodra Hisui", null, "Sliggoo Hisui"),
      ].map((m) => [m.chrooked_id, m]),
    );
    expect(preEvos(line.get("goodra--hisuianform")!, line).map((m) => m.chrooked_id)).toEqual([
      "goomy",
      "sliggoo--hisuianform",
    ]);
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

  it("keeps a form line on its form — a lone form target is never collapsed to base", () => {
    const line = new Map(
      [
        mon("sliggoo", "Sliggoo", "goodra"),
        mon("sliggoo--hisuianform", "Sliggoo Hisui", "goodra--hisuianform"),
        mon("goodra", "Goodra", null, "Sliggoo"),
        mon("goodra--hisuianform", "Goodra Hisui", null, "Sliggoo Hisui"),
      ].map((m) => [m.chrooked_id, m]),
    );
    expect(
      postEvos(line.get("sliggoo--hisuianform")!, line).map((m) => m.chrooked_id),
    ).toEqual(["goodra--hisuianform"]);
  });
});

describe("sharedOutsideLine", () => {
  it("flags a pre-evo that also feeds a line outside this one", () => {
    // Goomy feeds both Sliggoo forms; the Hisui line only contains one of them.
    const branchedGoomy = {
      ...mon("goomy", "Goomy", "sliggoo--hisuianform"),
      evolves_into: [
        { to: "sliggoo--hisuianform", to_name: "Sliggoo Hisui", to_dex: null, method: "Level 40" },
        { to: "sliggoo", to_name: "Sliggoo", to_dex: null, method: "Level 40" },
      ],
    } as DexEntry;
    const hisuiLine = new Set(["goomy", "sliggoo--hisuianform", "goodra--hisuianform"]);
    expect(sharedOutsideLine(branchedGoomy, hisuiLine)).toBe(true);
  });

  it("does not flag a member whose every edge stays in the line", () => {
    expect(
      sharedOutsideLine(goomy, new Set(["goomy", "sliggoo", "goodra"])),
    ).toBe(false);
    expect(sharedOutsideLine(goodra, new Set(["goodra"]))).toBe(false);
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
  it("carries the kit to any recipient set", () => {
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
    expect(rows[0].types).toEqual(["Dragon"]);
    expect(rows[1].learnset).toEqual([{ level: 5, move: "Rain Dance" }]);
  });

  it("scales stats to each recipient rather than copying the anchor's", () => {
    // Anchor: canon 400 BST reworked to 600 (+200), shape 2:1:1:1:1:1.
    const shape = { hp: 200, atk: 80, def: 80, spa: 80, spd: 80, spe: 80 };
    const anchorCanon = { hp: 100, atk: 60, def: 60, spa: 60, spd: 60, spe: 60 };
    const [row] = mirrorRows(
      {
        types: ["Dragon"],
        abilities: ABILITIES,
        stats: shape,
        baseStats: anchorCanon,
        learnset: [],
      },
      [withStats(goomy, { hp: 60, atk: 40, def: 40, spa: 40, spd: 40, spe: 40 })],
    );
    // 260 canon + 200 delta = 460, split in the anchor's 2:1:1:1:1:1 shape
    // (hp 1/3 of 460 = 153, +2 rounding drift; the five others 61 each). Every
    // stat clears its canon floor here, so the plain proportions stand.
    expect(bst(row.stats!)).toBe(460);
    expect(row.stats).not.toEqual(shape);
    expect(row.stats!.hp).toBe(154);
    expect(row.stats!.atk).toBe(62);
  });

  it("measures the delta against canon, so re-mirroring is idempotent", () => {
    const shape = { hp: 120, atk: 100, def: 80, spa: 80, spd: 60, spe: 60 };
    const anchorCanon = { hp: 100, atk: 90, def: 70, spa: 70, spd: 50, spe: 50 };
    const canon = { hp: 50, atk: 45, def: 35, spa: 35, spd: 25, spe: 25 };
    const kit = {
      types: ["Dragon"],
      abilities: ABILITIES,
      stats: shape,
      baseStats: anchorCanon,
      learnset: [],
    };
    const first = mirrorRows(kit, [withStats(goomy, canon)])[0].stats!;
    // Second pass: the recipient now CARRIES the scaled spread as an override,
    // but `base.stats` still holds canon — so the delta must not compound.
    const again = mirrorRows(kit, [withStats(goomy, first, canon)])[0].stats!;
    expect(again).toEqual(first);
  });

  it("leaves stats off the row when the kit carries none", () => {
    const rows = mirrorRows(
      { types: ["Dragon"], abilities: ABILITIES, learnset: [] },
      [goomy],
    );
    expect(rows[0].stats).toBeUndefined();
  });
});

describe("scaleStats", () => {
  const shape = { hp: 100, atk: 50, def: 50, spa: 50, spd: 50, spe: 50 };

  it("hits the target BST exactly after rounding drift", () => {
    const canon = { hp: 20, atk: 20, def: 20, spa: 20, spd: 20, spe: 20 };
    expect(bst(scaleStats(canon, 30, shape))).toBe(150);
  });

  it("carries the shape's role emphasis onto the recipient", () => {
    const canon = { hp: 20, atk: 20, def: 20, spa: 20, spd: 20, spe: 20 };
    const scaled = scaleStats(canon, 60, shape);
    expect(scaled.hp).toBe(Math.max(...Object.values(scaled)));
  });

  it("lets a canon floor outrank the shape's emphasis", () => {
    // A pre-evo already strong where the anchor is weak keeps that stat, even
    // though the anchor's shape ranks it low.
    const canon = { hp: 20, atk: 90, def: 20, spa: 20, spd: 20, spe: 20 };
    expect(scaleStats(canon, 0, shape).atk).toBe(90);
  });

  it("is a no-op when the shape already IS the canon spread and delta is 0", () => {
    expect(scaleStats(shape, 0, shape)).toEqual(shape);
  });

  it("floors every stat at canon — a fast pre-evo keeps its speed", () => {
    // The Whiscash/Barboach case: a slow bulky final evo would otherwise drag
    // Barboach's 60 speed down to 20.
    const whiscash = { hp: 120, atk: 85, def: 80, spa: 105, spd: 95, spe: 30 };
    const barboach: Record<string, number> = {
      hp: 50, atk: 48, def: 43, spa: 46, spd: 41, spe: 60,
    };
    const scaled = scaleStats(barboach, 47, whiscash);
    for (const key of Object.keys(barboach)) {
      expect(scaled[key]).toBeGreaterThanOrEqual(barboach[key]);
    }
    expect(bst(scaled)).toBe(bst(barboach)! + 47);
    // The exact spread `scripts/preevo_stats.py plan whiscash` produces — this
    // assertion is what keeps the two implementations from drifting apart.
    expect(scaled).toEqual({ hp: 68, atk: 48, def: 45, spa: 60, spd: 54, spe: 60 });
  });

  it("degrades to canon when the floors already spend the whole budget", () => {
    const slow = { hp: 120, atk: 85, def: 80, spa: 105, spd: 95, spe: 30 };
    const fast = { hp: 50, atk: 48, def: 43, spa: 46, spd: 41, spe: 60 };
    expect(scaleStats(fast, 0, slow)).toEqual(fast);
  });
});
