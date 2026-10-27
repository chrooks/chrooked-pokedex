import { describe, expect, it } from "vitest";
import { offlineRoutes, savedAt, spriteUrlsFor, warmOffline } from "./offline";
import type { DexEntry } from "../types";

const entry = (chrooked_id: string, dex: number | null): DexEntry =>
  ({ chrooked_id, dex, name: chrooked_id }) as unknown as DexEntry;

const store = () => {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
  };
};

describe("offlineRoutes", () => {
  it("lists the canon read routes and the target-scoped ones", () => {
    const canon = offlineRoutes(null);
    expect(canon).toContain("/api/dex");
    expect(canon).toContain("/api/type-chart");
    expect(canon.some((r) => r.includes("/targets/"))).toBe(false);
    const scoped = offlineRoutes("rejuv");
    expect(scoped).toContain("/api/targets/rejuv/dex");
    expect(scoped).toContain("/api/targets/rejuv/moves");
    expect(scoped).toContain("/api/targets");
  });
});

describe("spriteUrlsFor", () => {
  it("prefers the target file, falls back to the CDN, drops unspriteable rows", () => {
    const rows = [entry("pikachu", 25), entry("missingno", null)];
    const urls = spriteUrlsFor(rows, "rejuv");
    expect(urls).toEqual([
      { primary: "/api/targets/rejuv/sprite/25?id=pikachu", fallback: expect.stringMatching(/\/25\.png$/) },
    ]);
    const canon = spriteUrlsFor(rows, null);
    expect(canon[0].primary).toMatch(/\/25\.png$/);
    expect(canon[0].fallback).toBeNull();
  });
});

describe("warmOffline", () => {
  it("fetches every route and sprite, reports progress, stamps the save", async () => {
    const seen: string[] = [];
    const fetcher = (async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      seen.push(url);
      // Target sprite 404s → the CDN fallback must be fetched no-cors.
      if (url.startsWith("/api/targets/rejuv/sprite/")) return new Response(null, { status: 404 });
      if (url.startsWith("https://")) expect(init?.mode).toBe("no-cors");
      return new Response("{}", { status: 200 });
    }) as typeof fetch;
    const progress: number[] = [];
    const s = store();
    const result = await warmOffline({
      entries: [entry("pikachu", 25), entry("raichu", 26)],
      targetId: "rejuv",
      fetcher,
      store: s,
      onProgress: (done) => progress.push(done),
    });
    const routes = offlineRoutes("rejuv");
    expect(result.total).toBe(routes.length + 2);
    expect(result.done).toBe(result.total);
    expect(progress[progress.length - 1]).toBe(result.total);
    for (const r of routes) expect(seen).toContain(r);
    expect(seen.filter((u) => u.startsWith("https://")).length).toBe(2);
    expect(savedAt("rejuv", s)).toBeInstanceOf(Date);
    expect(savedAt(null, s)).toBeNull();
  });

  it("counts a failed route as not done and does not stamp the save", async () => {
    const fetcher = (async () => new Response(null, { status: 500 })) as typeof fetch;
    const s = store();
    const result = await warmOffline({ entries: [], targetId: null, fetcher, store: s });
    expect(result.done).toBe(0);
    expect(savedAt(null, s)).toBeNull();
  });
});

describe("isReachable", () => {
  it("is a HEAD that bypasses the caches, false on a thrown fetch", async () => {
    let init: RequestInit | undefined;
    const ok = (async (_u: string | URL | Request, i?: RequestInit) => {
      init = i;
      return new Response(null, { status: 200 });
    }) as typeof fetch;
    const { isReachable } = await import("./offline");
    expect(await isReachable(ok)).toBe(true);
    expect(init?.method).toBe("HEAD");
    expect(init?.cache).toBe("no-store");
    const down = (async () => {
      throw new TypeError("Failed to fetch");
    }) as typeof fetch;
    expect(await isReachable(down)).toBe(false);
  });
});
