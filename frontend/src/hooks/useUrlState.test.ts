import { describe, expect, it } from "vitest";
import { withTabQuery, type ViewState } from "./useUrlState";

const at = (kind: ViewState["kind"], query: string) => ({ kind, query }) as ViewState;

describe("withTabQuery", () => {
  it("clears on tab switch and restores each tab's last query", () => {
    // Species: "blastoise" → Abilities: clear
    const toAbilities = withTabQuery(at("dex", "blastoise"), { kind: "abilities" });
    expect(toAbilities.query).toBe("");
    // Abilities: "torrent" → Species: "blastoise" comes back
    const toDex = withTabQuery(at("abilities", "torrent"), { kind: "dex" });
    expect(toDex.query).toBe("blastoise");
    // …and Abilities remembers "torrent" too
    expect(withTabQuery(at("dex", "blastoise"), { kind: "abilities" }).query).toBe("torrent");
  });

  it("leaves an explicit query and same-tab patches alone", () => {
    expect(withTabQuery(at("dex", "x"), { kind: "ledger", query: "goodra" }).query).toBe("goodra");
    expect(withTabQuery(at("dex", "x"), { selected: "goodra" })).toEqual({ selected: "goodra" });
  });
});
