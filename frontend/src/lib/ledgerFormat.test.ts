import { describe, expect, test } from "vitest";
import { formatLedgerTs, renderLedgerValue, scopeKind } from "./ledgerFormat";

describe("renderLedgerValue", () => {
  test("renders null/undefined as the empty mark", () => {
    expect(renderLedgerValue(null)).toBe("∅");
    expect(renderLedgerValue(undefined)).toBe("∅");
  });
  test("joins scalar arrays", () => {
    expect(renderLedgerValue(["Bug", "Fighting"])).toBe("Bug, Fighting");
  });
  test("renders a learnset (array of move objects) readably, not [object Object]", () => {
    const learnset = [
      { level: 1, move: "Pound" },
      { level: 5, move: "Ice Beam" },
    ];
    expect(renderLedgerValue(learnset)).toBe("L1 Pound, L5 Ice Beam");
  });
  test("renders ability slots as key: value pairs, skipping nulls", () => {
    expect(
      renderLedgerValue({ primary: "Thick Fat", secondary: "Hydration", hidden: null }),
    ).toBe("primary: Thick Fat, secondary: Hydration");
  });
  test("renders a type-chart cell readably", () => {
    expect(renderLedgerValue({ attacker: "Ice", defender: "Dragon", multiplier: 2 })).toBe(
      "Ice→Dragon ×2",
    );
  });
  test("renders an empty array as the empty mark", () => {
    expect(renderLedgerValue([])).toBe("∅");
  });
  test("renders scalars", () => {
    expect(renderLedgerValue(140)).toBe("140");
  });
});

describe("scopeKind", () => {
  test("classifies target vs base scope", () => {
    expect(scopeKind("target:africanvs")).toBe("target");
    expect(scopeKind("base")).toBe("base");
  });
});

describe("formatLedgerTs", () => {
  test("compacts an ISO-8601 UTC stamp", () => {
    expect(formatLedgerTs("2026-06-23T19:04:00.123456+00:00")).toBe("2026-06-23 19:04:00");
    expect(formatLedgerTs("2026-06-23T19:04:00Z")).toBe("2026-06-23 19:04:00");
  });
});
