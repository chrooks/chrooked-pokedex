/* ac2 (partial) — the api `/suggest/*` client shape.

   Proves suggestAbility / suggestLearnset POST to the right endpoint with the
   right body, parse the typed proposal response, and pass the server's verbatim
   error message through on 503/422 (honest error states — nothing written).

   Node-env, mocked globalThis.fetch — same style as targetDialect.test.ts: no
   jsdom, no testing-library, no Playwright. */

import { describe, it, expect, vi, afterEach } from "vitest";
import { api, ApiError } from "../api";

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
});
