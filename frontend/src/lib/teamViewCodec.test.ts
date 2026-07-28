import { describe, expect, it } from "vitest";
import { decodeParty, encodeParty, MAX_PARTY, replacePartyMember } from "./teamViewCodec";

describe("team party codec", () => {
  it("round-trips ids and abilities", () => {
    const party = [
      { id: "galvantula", ability: null },
      { id: "gengar", ability: "Levitate" },
    ];
    expect(decodeParty(encodeParty(party))).toEqual(party);
  });

  it("encodes ability names with spaces intact", () => {
    const raw = encodeParty([{ id: "heatran", ability: "Flash Fire" }]);
    expect(decodeParty(raw)).toEqual([{ id: "heatran", ability: "Flash Fire" }]);
  });

  it("caps at six members on encode and decode", () => {
    const seven = Array.from({ length: 7 }, (_, i) => ({ id: `mon${i}`, ability: null }));
    expect(encodeParty(seven).split(",")).toHaveLength(MAX_PARTY);
    const raw = seven.map((m) => m.id).join(",");
    expect(decodeParty(raw)).toHaveLength(MAX_PARTY);
  });

  it("returns empty for blank or null", () => {
    expect(decodeParty(null)).toEqual([]);
    expect(decodeParty("")).toEqual([]);
  });

  it("drops empty tokens", () => {
    expect(decodeParty("galvantula,,gengar")).toEqual([
      { id: "galvantula", ability: null },
      { id: "gengar", ability: null },
    ]);
  });
});

describe("replacePartyMember (full-team swap, ac10)", () => {
  const full = [
    { id: "a", ability: null },
    { id: "b", ability: "Levitate" },
    { id: "c", ability: null },
  ];

  it("swaps the member at the given slot, clearing its ability", () => {
    expect(replacePartyMember(full, 1, "joltik")).toEqual([
      { id: "a", ability: null },
      { id: "joltik", ability: null },
      { id: "c", ability: null },
    ]);
  });

  it("leaves every other slot untouched", () => {
    const next = replacePartyMember(full, 0, "joltik");
    expect(next[1]).toBe(full[1]);
    expect(next[2]).toBe(full[2]);
  });

  it("does not mutate the input party", () => {
    const before = JSON.stringify(full);
    replacePartyMember(full, 2, "joltik");
    expect(JSON.stringify(full)).toBe(before);
  });

  it("is a no-op copy for an out-of-range slot", () => {
    expect(replacePartyMember(full, 9, "joltik")).toEqual(full);
  });
});
