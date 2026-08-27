/* #88 acceptance proof for the save-state row.
 *
 * Runs headless only (playwright.config.ts pins it) — a headed window on this
 * machine is never wanted.
 *
 * Covers: the calm and forced-conflict states at all three shipped viewports
 * with screenshots, and a keyboard focus walk standing in for the D-pad (both
 * drive the same DOM focus — see lib/spatialNav.ts). */

import { test, expect, type Page } from "@playwright/test";

const VIEWPORTS = [
  { name: "537x412", width: 537, height: 412 },
  { name: "833x468", width: 833, height: 468 },
  { name: "468x833", width: 468, height: 833 },
];

const CALM = {
  available: true,
  folder: "rejuv-saves",
  conflicts: [],
  devices: [
    { name: "thor", id: "UMA523D-A", completion: 100, last_seen: null, seconds_ago: 720 },
    { name: "macbook", id: "MFJ6AQQ-B", completion: 100, last_seen: null, seconds_ago: 5400 },
    { name: "hestia", id: "OCLUO43-C", completion: 98.4, last_seen: null, seconds_ago: 60 },
  ],
  newest: "hestia",
  newest_seconds_ago: 60,
  stale: [],
};

const CONFLICT = {
  ...CALM,
  newest: "thor",
  newest_seconds_ago: 720,
  conflicts: [
    { file: "Game.sync-conflict-20260827-101500-UMA523D.rxdata", device: "thor" },
    { file: "Game_backup.sync-conflict-20260827-094102-MFJ6AQQ.rxdata", device: "macbook" },
  ],
};

const UNAVAILABLE = { available: false, folder: "rejuv-saves", conflicts: [] };

async function mount(page: Page, payload: unknown) {
  await page.route("**/api/targets/*/save-status", (route) =>
    route.fulfill({ json: payload }),
  );
  await page.goto("/e2e/harness.html");
  await expect(page.locator("#save-state-row")).toBeVisible();
}

for (const viewport of VIEWPORTS) {
  test(`calm state at ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await mount(page, CALM);

    await expect(page.locator("#save-state-toggle")).toContainText(
      "newest from hestia · synced 1m ago",
    );
    await expect(page.locator("#save-state-alert")).toHaveCount(0);
    await page.screenshot({ path: `e2e/screenshots/calm-${viewport.name}.png`, animations: "disabled" });

    // The row must not push the drawer into a horizontal scroll at any size.
    const overflow = await page.evaluate(() => {
      const row = document.querySelector("#save-state-row") as HTMLElement;
      return row.scrollWidth - row.clientWidth;
    });
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test(`conflict state at ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await mount(page, CONFLICT);

    await expect(page.locator("#save-state-toggle")).toContainText(
      "2 conflicted saves need picking",
    );
    const alert = page.locator("#save-state-alert");
    await expect(alert).toContainText("Game.sync-conflict-20260827-101500-UMA523D.rxdata");
    await expect(alert).toContainText("from thor");
    await expect(alert).toContainText("from macbook");
    await page.screenshot({ path: `e2e/screenshots/conflict-${viewport.name}.png`, animations: "disabled" });
  });
}

test("unavailable renders quietly, not as an error", async ({ page }) => {
  await page.setViewportSize(VIEWPORTS[0]);
  await mount(page, UNAVAILABLE);

  await expect(page.locator("#save-state-toggle")).toContainText(
    "sync status unavailable",
  );
  await expect(page.locator("#save-state-row")).toHaveClass(/save-row--mute/);
  await expect(page.locator("[role=alert]")).toHaveCount(0);
  await page.screenshot({ path: "e2e/screenshots/unavailable-537x412.png", animations: "disabled" });
});

test("focus walk reaches the row and its expansion", async ({ page }) => {
  await page.setViewportSize(VIEWPORTS[0]);
  await mount(page, CALM);

  // Tab from the top of the document: the row is a real control, so it lands
  // in the natural order without any focus management of its own.
  await page.keyboard.press("Tab");
  await expect(page.locator("#save-state-toggle")).toBeFocused();

  // A visible focus state, not just :focus — the pad cursor and the keyboard
  // ring both read from the same outline.
  const outline = await page
    .locator("#save-state-toggle")
    .evaluate((el) => getComputedStyle(el).outlineWidth);
  expect(parseFloat(outline)).toBeGreaterThan(0);

  // "A" on the pad clicks the focused element; Enter is the same activation.
  await page.keyboard.press("Enter");
  await expect(page.locator("#save-state-detail")).toBeVisible();
  await expect(page.locator("#save-state-toggle")).toHaveAttribute(
    "aria-expanded",
    "true",
  );

  // The expansion carries a real control of its own, reachable by the same walk.
  await page.keyboard.press("Tab");
  await expect(page.locator("#save-state-recheck")).toBeFocused();
  await page.screenshot({ path: "e2e/screenshots/expanded-focus-537x412.png", animations: "disabled" });

  await page.keyboard.press("Enter");
  await expect(page.locator("#save-state-detail")).toBeVisible();

  // Shift+Tab back and collapse — the toggle round-trips.
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Enter");
  await expect(page.locator("#save-state-detail")).toHaveCount(0);
});
