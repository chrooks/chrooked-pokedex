/* ac2 (partial) — the api `/suggest/*` client shape.

   Proves suggestAbility / suggestLearnset POST to the right endpoint with the
   right body, parse the typed proposal response, and pass the server's verbatim
   error message through on 503/422 (honest error states — nothing written).

   Node-env, mocked globalThis.fetch — same style as targetDialect.test.ts: no
   jsdom, no testing-library, no Playwright. */

import { describe, it, expect, vi, afterEach } from "vitest";
import { api, ApiError } from "../api";
import { makeoverApi } from "./makeoverApi";

function mockFetch(body: unknown, status = 200): void {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: () => Promise.resolve(body),
  } as unknown as Response);
}

function lastCall() {
  const spy = globalThis.fetch as ReturnType<typeof vi.fn>;
  const [url, init] = spy.mock.calls[0] as [string, RequestInit];
  return { url, init, body: JSON.parse(String(init.body)) };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("api.suggestAbility (ac2)", () => {
  it("POSTs to the ability suggest endpoint with the direction", async () => {
    mockFetch({
      draft: { abilities: { primary: "Drizzle" } },
      rationale: { primary: "rain synergy" },
      alternatives: [],
    });
    const result = await api.suggestAbility("politoed", {
      direction: "make it rain-focused",
    });
    const { url, init, body } = lastCall();
    expect(url).toBe("/api/species/politoed/suggest/ability");
    expect(init.method).toBe("POST");
    expect(body.direction).toBe("make it rain-focused");
    expect(result.draft.abilities.primary).toBe("Drizzle");
    expect(result.rationale.primary).toBe("rain synergy");
  });

  it("passes a 503 (missing key) message through as an ApiError", async () => {
    mockFetch({ detail: "Set OPENAI_API_KEY or run the snapshot" }, 503);
    await expect(api.suggestAbility("x")).rejects.toMatchObject({
      status: 503,
      message: "Set OPENAI_API_KEY or run the snapshot",
    });
  });

  it("surfaces a 422 loader message verbatim", async () => {
    mockFetch({ detail: "unknown ability 'Flurb'" }, 422);
    const error = await api.suggestAbility("x").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toBe("unknown ability 'Flurb'");
  });
});

describe("api.suggestLearnset (ac2)", () => {
  it("POSTs to the learnset endpoint with direction + mode full", async () => {
    mockFetch({
      draft: { learnset: [{ level: 1, move: "Tackle", reasoning: "early" }] },
      rationale: { learnset: "leveled curve" },
      alternatives: [],
    });
    const result = await api.suggestLearnset("bulbasaur", {
      direction: "more special moves",
    });
    const { url, body } = lastCall();
    expect(url).toBe("/api/species/bulbasaur/suggest/learnset");
    expect(body.direction).toBe("more special moves");
    expect(body.mode).toBe("full");
    expect(result.draft.learnset[0].move).toBe("Tackle");
  });

  it("sends the anchor moves the author named (#89)", async () => {
    mockFetch({ draft: { learnset: [] }, rationale: {}, alternatives: [] });
    await api.suggestLearnset("goodra", { anchors: ["Bite", "U-turn"] });
    expect(lastCall().body.anchors).toEqual(["Bite", "U-turn"]);
  });

  it("omits the anchors key when no anchor was named", async () => {
    mockFetch({ draft: { learnset: [] }, rationale: {}, alternatives: [] });
    await api.suggestLearnset("goodra", { anchors: [] });
    expect("anchors" in lastCall().body).toBe(false);
  });
});

describe("backdrop target on suggest calls (Rejuv-original forms)", () => {
  it("sends the backdrop target with a learnset proposal", async () => {
    mockFetch({ draft: { learnset: [] }, rationale: {}, alternatives: [] });
    await api.suggestLearnset("breloom--aevianform", { target: "t-rejuv" });
    expect(lastCall().body.target).toBe("t-rejuv");
  });

  it("sends the backdrop target with an ability proposal", async () => {
    mockFetch({ draft: { abilities: {} }, rationale: {}, alternatives: [] });
    await api.suggestAbility("breloom--aevianform", { target: "t-rejuv" });
    expect(lastCall().body.target).toBe("t-rejuv");
  });

  it("omits the target key on a canon-launched suggest", async () => {
    mockFetch({ draft: { learnset: [] }, rationale: {}, alternatives: [] });
    await api.suggestLearnset("goodra", {});
    expect("target" in lastCall().body).toBe(false);
  });
});

describe("lore sourcing on suggest calls (#92)", () => {
  it("sends the blind lore mode with a learnset proposal", async () => {
    mockFetch({ draft: { learnset: [] }, rationale: {}, alternatives: [] });
    await api.suggestLearnset("goodra", { lore: "blind" });
    expect(lastCall().body.lore).toBe("blind");
  });

  it("sends off when the author has not asked for blind", async () => {
    mockFetch({ draft: { learnset: [] }, rationale: {}, alternatives: [] });
    await api.suggestLearnset("goodra", { lore: "off" });
    expect(lastCall().body.lore).toBe("off");
  });
});

describe("makeoverApi.createAbility — anchor-species lore (#79)", () => {
  it("sends the anchor species and lore mode in the request body", async () => {
    mockFetch({
      draft: { ability: { chrooked_id: "x", name: "X", description: "" }, behavior: { effects: [] }, distribution: [] },
      rationale: {},
      alternatives: [],
    });
    await makeoverApi.createAbility("a Water sponge", "goodra", "blind");
    const { url, body } = lastCall();
    expect(url).toBe("/api/abilities/suggest");
    expect(body.species).toBe("goodra");
    expect(body.lore).toBe("blind");
  });

  it("omits species and lore on the standalone create path", async () => {
    mockFetch({
      draft: { ability: { chrooked_id: "x", name: "X", description: "" }, behavior: { effects: [] }, distribution: [] },
      rationale: {},
      alternatives: [],
    });
    await makeoverApi.createAbility("a Water sponge");
    const { body } = lastCall();
    expect(body.species).toBeUndefined();
    expect(body.lore).toBeUndefined();
  });
});
