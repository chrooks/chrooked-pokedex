/* ac2 (partial) — api.targetDialect payload parsing.

   Proves the function calls the correct endpoint and correctly parses the
   {dialect, label} shape.  Runs in the default node environment (no DOM) by
   mocking globalThis.fetch.  Follows the node-env test style of the other
   lib/*.test.ts files — no jsdom, no testing-library, no Playwright. */

import { describe, it, expect, vi, afterEach } from "vitest";
import { api } from "../api";

function mockFetch(body: unknown, status = 200): void {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: () => Promise.resolve(body),
  } as unknown as Response);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("api.targetDialect (ac2)", () => {
  it("parses essentials16 payload: dialect + label", async () => {
    mockFetch({ dialect: "essentials16", label: "16.2" });
    const result = await api.targetDialect("abc123");
    expect(result.dialect).toBe("essentials16");
    expect(result.label).toBe("16.2");
  });

  it("parses pokeemerald payload: both fields null", async () => {
    mockFetch({ dialect: null, label: null });
    const result = await api.targetDialect("xyz789");
    expect(result.dialect).toBeNull();
    expect(result.label).toBeNull();
  });

  it("calls the correct endpoint with the target id", async () => {
    mockFetch({ dialect: "essentials21", label: "v19+ (modern)" });
    await api.targetDialect("myid42");
    const fetchSpy = globalThis.fetch as ReturnType<typeof vi.fn>;
    const calledUrl = fetchSpy.mock.calls[0][0] as string;
    expect(calledUrl).toBe("/api/targets/myid42/dialect");
  });
});
