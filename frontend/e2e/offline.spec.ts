/* #122 acceptance proof: the dex works with no network after one save.
 *
 * Drives the built app on `vite preview` (:5175, proxied to the real API on
 * :8000) so the service worker is the production one. Headless only.
 *
 * ac1 — manifest + service worker registered.
 * ac2 — Save for offline reaches a full count.
 * ac3 — offline reload renders the grid and the offline strip from cache.
 * ac4 (writes never cached) is a vitest on src/pwa/caching.ts. */

import { test, expect } from "@playwright/test";

const APP = "http://localhost:5175";
// ~1,300 sprites on the CDN; generous so a slow link is not a false red.
const WARM_TIMEOUT_MS = 240_000;
// The API loads the Ruleset per request; a cold dex on a busy hestia takes a while.
const DEX_LOAD_MS = 90_000;

test.describe.configure({ mode: "serial" });

test("installable, saves for offline, survives an offline reload", async ({ context, page }) => {
  test.setTimeout(WARM_TIMEOUT_MS + 60_000);
  await page.goto(`${APP}/`);

  // ac1: manifest + SW.
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute("href", /manifest\.webmanifest/);
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload(); // first controlled load
  await expect(page.locator(".dex-cell").first()).toBeVisible({ timeout: DEX_LOAD_MS });
  expect(await page.evaluate(() => navigator.serviceWorker.controller !== null)).toBe(true);

  // ac2: warm-up.
  const save = page.locator("#offline-save");
  await expect(save).toHaveText(/Save for offline|Refresh/);
  await save.click();
  await expect(page.locator(".offline-bar")).toHaveText(/Saving for offline/);
  await expect(page.locator(".offline-bar")).toHaveText(/Saved for offline · \w+ \d+/, {
    timeout: WARM_TIMEOUT_MS,
  });
  await page.screenshot({ path: "e2e/screenshots/offline-saved.png" });
  // The worker's own caches hold the goods — Chrome's HTTP cache could mask a
  // dead rule (it did once: a pattern that closed over an unserialized const).
  const cached = await page.evaluate(async () => {
    const api = await (await caches.open("chrooked-api")).keys();
    const sprites = await (await caches.open("chrooked-sprites")).keys();
    return { api: api.map((r) => new URL(r.url).pathname), sprites: sprites.length };
  });
  expect(cached.api).toContain("/api/dex");
  expect(cached.sprites).toBeGreaterThan(100);

  // ac3: cut the network, reload, read from cache.
  await context.setOffline(true);
  await page.reload();
  await expect(page.locator(".offline-bar")).toHaveText(/Offline · showing what was saved/);
  await expect(page.locator(".dex-cell").first()).toBeVisible({ timeout: DEX_LOAD_MS });
  const cells = await page.locator(".dex-cell").count();
  expect(cells).toBeGreaterThan(20);
  // A sprite from the cache actually decoded (not the placeholder number).
  const spriteOk = await page
    .locator(".dex-cell img")
    .first()
    .evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0);
  expect(spriteOk).toBe(true);
  await page.screenshot({ path: "e2e/screenshots/offline-reload.png" });
  await context.setOffline(false);
});
