/* "Save for offline" warm-up (#122). Fetches every read route and sprite the
   dex needs so the service worker's runtime caches (src/pwa/caching.ts) hold
   them before the network goes away. The data itself is small — the dex is a
   handful of list routes — the sprites are the bulk.

   Pure: fetch and storage are injected so vitest runs it in Node. */

import type { DexEntry } from "../types";
import { spriteUrl, targetSpriteUrl } from "./sprites";

const SAVED_KEY = "chrooked-pokedex:offline-saved";
// One stamp per backdrop: a canon save warms no target route, so switching to
// Rejuv must read as unsaved until its own routes are fetched.
export const savedKey = (targetId: string | null) => `${SAVED_KEY}:${targetId ?? "canon"}`;
// ponytail: fixed fan-out; tune if the CDN rate-limits or the phone chokes.
const CONCURRENCY = 8;

interface KeyStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const CANON_ROUTES = [
  "/api/dex",
  "/api/moves",
  "/api/abilities",
  "/api/type-chart",
  "/api/behaviors",
  "/api/statuses",
  "/api/meta/evolution-methods",
  "/api/meta/learnset-rubric",
  "/api/targets",
];

/** Every GET the dex reads for the given backdrop target (canon when null). */
export function offlineRoutes(targetId: string | null): string[] {
  if (targetId === null) return CANON_ROUTES.filter((r) => r !== "/api/targets");
  const t = `/api/targets/${encodeURIComponent(targetId)}`;
  return [
    ...CANON_ROUTES,
    `${t}/dex`,
    `${t}/moves`,
    `${t}/abilities`,
    `${t}/type-chart`,
    `${t}/namespace`,
    `${t}/dialect`,
  ];
}

export interface SpriteFetch {
  /** First try: the target's own art when a target is active, else the CDN. */
  primary: string;
  /** The CDN, when the primary was a target file that may 404. */
  fallback: string | null;
}

export function spriteUrlsFor(entries: DexEntry[], targetId: string | null): SpriteFetch[] {
  const seen = new Set<string>();
  const out: SpriteFetch[] = [];
  for (const e of entries) {
    const cdn = spriteUrl(e.chrooked_id, e.dex);
    const target = targetId === null ? null : targetSpriteUrl(targetId, e.dex, e.chrooked_id);
    const primary = target ?? cdn;
    if (primary === null || seen.has(primary)) continue;
    seen.add(primary);
    out.push({ primary, fallback: target !== null ? cdn : null });
  }
  return out;
}

export interface WarmOptions {
  entries: DexEntry[];
  targetId: string | null;
  onProgress?: (done: number, total: number) => void;
  fetcher?: typeof fetch;
  store?: KeyStore;
  signal?: AbortSignal;
}

export interface WarmResult {
  done: number;
  total: number;
}

const isCdn = (url: string) => url.startsWith("https://");

// The <img> tag loads CDN sprites no-cors and the CDN answers `Vary: Origin`,
// so a cors warm-up would never match the img's cache lookup. Opaque responses
// read as status 0, so "ok" for a CDN url is "the fetch did not throw".
// ponytail: an opaque 404 is cached too (cosmetic: that sprite was missing anyway).
async function fetchOne(fetcher: typeof fetch, url: string, signal?: AbortSignal): Promise<boolean> {
  try {
    const res = await fetcher(url, isCdn(url) ? { mode: "no-cors", signal } : { signal });
    return isCdn(url) ? true : res.ok;
  } catch {
    return false;
  }
}

export async function warmOffline({
  entries,
  targetId,
  onProgress,
  fetcher = fetch,
  store = localStorage,
  signal,
}: WarmOptions): Promise<WarmResult> {
  const routes = offlineRoutes(targetId);
  const sprites = spriteUrlsFor(entries, targetId);
  const total = routes.length + sprites.length;
  let done = 0;
  let allRoutesOk = true;
  const tick = () => onProgress?.(done, total);

  const jobs: Array<() => Promise<void>> = [
    ...routes.map((r) => async () => {
      const ok = await fetchOne(fetcher, r, signal);
      if (ok) done += 1;
      else allRoutesOk = false;
      tick();
    }),
    ...sprites.map((s) => async () => {
      let ok = await fetchOne(fetcher, s.primary, signal);
      if (!ok && s.fallback !== null) ok = await fetchOne(fetcher, s.fallback, signal);
      if (ok) done += 1;
      tick();
    }),
  ];

  let next = 0;
  const worker = async () => {
    while (next < jobs.length && !signal?.aborted) {
      const job = jobs[next++];
      await job();
    }
  };
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));

  // A missing sprite is cosmetic; a missing route means a tab is dead offline,
  // so only a full route set counts as "saved".
  if (allRoutesOk && !signal?.aborted) store.setItem(savedKey(targetId), new Date().toISOString());
  return { done, total };
}

export function savedAt(targetId: string | null, store: KeyStore = localStorage): Date | null {
  const raw = store.getItem(savedKey(targetId));
  if (raw === null) return null;
  const d = new Date(raw);
  return Number.isNaN(d.getTime()) ? null : d;
}

// navigator.onLine lies both ways (Wi-Fi with no route reads true; some
// emulations never flip it), and once the service worker serves every GET from
// cache no page fetch ever fails. So ask the network directly: a HEAD is not
// matched by any caching rule (all GET-only), so it must reach the origin.
export const PROBE_URL = "/manifest.webmanifest";

export async function isReachable(fetcher: typeof fetch = fetch): Promise<boolean> {
  try {
    const res = await fetcher(PROBE_URL, { method: "HEAD", cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}
