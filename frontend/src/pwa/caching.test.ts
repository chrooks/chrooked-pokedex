import { describe, expect, it } from "vitest";
import { isApiRead, isSpriteCdn, runtimeCaching } from "./caching";

// The exact context Workbox passes a function urlPattern inside the worker.
const run = (pattern: (typeof runtimeCaching)[number]["urlPattern"], href: string) =>
  pattern instanceof RegExp ? pattern.test(href) : pattern(ctx(href));

const ctx = (href: string) => {
  const url = new URL(href);
  return { url, sameOrigin: url.origin === "https://dex.example" };
};

describe("runtime caching rules", () => {
  it("caches same-origin API reads", () => {
    expect(isApiRead(ctx("https://dex.example/api/dex"))).toBe(true);
    expect(isApiRead(ctx("https://dex.example/api/targets/rejuv/sprite/25?id=pikachu"))).toBe(true);
    expect(isApiRead(ctx("https://dex.example/assets/app.js"))).toBe(false);
    expect(isApiRead(ctx("https://other.example/api/dex"))).toBe(false);
  });

  it("caches the PokeAPI sprite CDN only", () => {
    expect(
      isSpriteCdn(ctx("https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png")),
    ).toBe(true);
    expect(isSpriteCdn(ctx("https://raw.githubusercontent.com/someone/else/x.png"))).toBe(false);
  });

  it("never caches a write: every rule is GET-only", () => {
    expect(runtimeCaching.length).toBeGreaterThan(0);
    for (const rule of runtimeCaching) expect(rule.method).toBe("GET");
  });

  it("survives Workbox's toString() serialization: no pattern closes over a name", () => {
    for (const rule of runtimeCaching) {
      if (rule.urlPattern instanceof RegExp) continue;
      // Evaluate the function from its own source, as sw.js will.
      const rebuilt = new Function(`return (${rule.urlPattern.toString()})`)() as typeof rule.urlPattern;
      expect(run(rebuilt, "https://dex.example/api/dex")).toBe(run(rule.urlPattern, "https://dex.example/api/dex"));
    }
    const sprites = runtimeCaching.find((r) => r.options.cacheName === "chrooked-sprites")!;
    expect(run(sprites.urlPattern, "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png")).toBe(true);
  });

  it("serves API reads network-first with a timeout and sprites cache-first", () => {
    const api = runtimeCaching.find((r) => r.options.cacheName === "chrooked-api");
    const sprites = runtimeCaching.find((r) => r.options.cacheName === "chrooked-sprites");
    expect(api?.handler).toBe("NetworkFirst");
    expect(api?.options.networkTimeoutSeconds).toBeGreaterThan(0);
    expect(sprites?.handler).toBe("CacheFirst");
    // <img> fetches are no-cors → opaque status 0; the sprite rule must accept it.
    expect(sprites?.options.cacheableResponse?.statuses).toContain(0);
    expect(api?.options.cacheableResponse?.statuses).toEqual([200]);
  });
});
