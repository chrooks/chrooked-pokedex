import { describe, it, expect } from "vitest";
import type { FilterEntry } from "./dexFilters";
import type { SortKey } from "./dexSort";
import {
  decodeFilter,
  decodeHidden,
  decodeSort,
  encodeFilter,
  encodeHidden,
  encodeSort,
} from "./dexViewCodec";

describe("filter codec (ac6)", () => {
  it("round-trips a valid filter tree", () => {
    const entries: FilterEntry[] = [
      { kind: "filter", id: "a", field: "atk", value: "≥|100", connector: "AND", negated: false },
      { kind: "paren", id: "b", paren: "(", connector: "AND" },
      { kind: "filter", id: "c", field: "type", value: "Fire", connector: "AND", negated: true },
      { kind: "filter", id: "d", field: "class", value: "Legendary", connector: "OR", negated: false },
      { kind: "paren", id: "e", paren: ")", connector: "AND" },
    ];
    expect(decodeFilter(encodeFilter(entries))).toEqual(entries);
  });

  it("returns [] for a corrupt payload instead of throwing", () => {
    expect(decodeFilter("%7Bbroken")).toEqual([]);
    expect(decodeFilter(null)).toEqual([]);
    expect(decodeFilter(encodeURIComponent('"not-an-array"'))).toEqual([]);
  });

  it("drops entries with an unknown field or malformed shape", () => {
    const dirty = encodeURIComponent(
      JSON.stringify([
        { kind: "filter", id: "ok", field: "atk", value: "≥|100", connector: "AND", negated: false },
        { kind: "filter", id: "bad", field: "nonsense", value: "x", connector: "AND", negated: false },
        { kind: "filter", id: "shape", field: "atk", connector: "AND" }, // missing value/negated
      ]),
    );
    const decoded = decodeFilter(dirty);
    expect(decoded).toHaveLength(1);
    expect(decoded[0].id).toBe("ok");
  });

  it("caps the number of filter pills at 10 (parens excepted)", () => {
    const many: FilterEntry[] = Array.from({ length: 14 }, (_unused, index) => ({
      kind: "filter" as const,
      id: `f${index}`,
      field: "atk",
      value: "≥|1",
      connector: "AND" as const,
      negated: false,
    }));
    expect(decodeFilter(encodeFilter(many))).toHaveLength(10);
  });
});

describe("sort codec (ac6)", () => {
  it("round-trips ordered sort keys", () => {
    const keys: SortKey[] = [
      { field: "atk", direction: "desc" },
      { field: "bst", direction: "asc" },
    ];
    expect(encodeSort(keys)).toBe("atk:desc,bst:asc");
    expect(decodeSort("atk:desc,bst:asc")).toEqual(keys);
  });

  it("drops unknown fields and bad directions", () => {
    expect(decodeSort("atk:sideways,bogus:asc")).toEqual([]);
    expect(decodeSort("dex:asc")).toEqual([]); // dex is locked, not sortable
  });

  it("de-duplicates fields and caps at three keys", () => {
    expect(decodeSort("atk:asc,atk:desc")).toEqual([{ field: "atk", direction: "asc" }]);
    expect(decodeSort("hp:asc,atk:asc,def:asc,spa:asc")).toHaveLength(3);
  });
});

describe("hidden-column codec (ac6)", () => {
  it("round-trips hideable columns", () => {
    expect(encodeHidden(["spa", "spd"])).toBe("spa,spd");
    expect(decodeHidden("spa,spd")).toEqual(["spa", "spd"]);
  });

  it("drops locked and unknown columns", () => {
    expect(decodeHidden("name,spa")).toEqual(["spa"]); // name is locked
    expect(decodeHidden("dex,led,bogus")).toEqual([]);
  });
});
