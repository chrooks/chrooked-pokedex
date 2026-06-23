import { describe, expect, test } from "vitest";
import { formatLedgerTs, renderLedgerValue, scopeKind } from "./ledgerFormat";

describe("renderLedgerValue", () => {
  test("renders null/undefined as the empty mark", () => {
    expect(renderLedgerValue(null)).toBe("∅");
    expect(renderLedgerValue(undefined)).toBe("∅");
  });
  test("joins arrays", () => {
    expect(renderLedgerValue(["Bug", "Fighting"])).toBe("Bug, Fighting");
  });
  test("stringifies objects and scalars", () => {
    expect(renderLedgerValue({ hp: 200 })).toBe('{"hp":200}');
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
