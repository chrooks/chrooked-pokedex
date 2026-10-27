/* Service-worker runtime caching rules (#122). Pure data so vitest can assert
   on them without the Vite plugin; vite.config.ts hands the array to Workbox.

   Two caches:
   - chrooked-api: same-origin GET /api/* — network-first, so an editor reload
     after a save shows the saved data, and only a dead or slow network falls
     back to the cached copy. Only 200s are kept, so a 404 target sprite never
     shadows the CDN fallback.
   - chrooked-sprites: the PokeAPI CDN — cache-first, sprites never change.
     <img> fetches are no-cors (opaque, status 0), so 0 must be cacheable.

   Every rule is GET-only. Writes (PUT/POST/DELETE) never enter a cache.

   Workbox serializes a function `urlPattern` with `.toString()` into sw.js, so
   a pattern may reference nothing outside its own body — a closed-over
   constant becomes a ReferenceError inside the worker and the rule goes dead.
   The CDN rule is a RegExp for that reason. */

export const API_CACHE = "chrooked-api";
export const SPRITE_CACHE = "chrooked-sprites";
export const SPRITE_CDN_PATTERN = /^https:\/\/raw\.githubusercontent\.com\/PokeAPI\/sprites\//;

interface RouteContext {
  url: URL;
  sameOrigin: boolean;
}

export interface CachingRule {
  urlPattern: RegExp | ((ctx: RouteContext) => boolean);
  method: "GET";
  handler: "NetworkFirst" | "CacheFirst";
  options: {
    cacheName: string;
    cacheableResponse?: { statuses: number[] };
    expiration?: { maxEntries?: number; maxAgeSeconds?: number };
    networkTimeoutSeconds?: number;
  };
}

export const isApiRead = ({ url, sameOrigin }: RouteContext): boolean =>
  sameOrigin && url.pathname.startsWith("/api/");

export const isSpriteCdn = ({ url }: RouteContext): boolean =>
  SPRITE_CDN_PATTERN.test(url.href);

// A cold /api/dex on the container takes ~15 s (the Ruleset loads per request);
// past this the cached copy answers and the network result refreshes it.
const API_NETWORK_TIMEOUT_SECONDS = 20;
const ONE_YEAR_SECONDS = 365 * 24 * 60 * 60;
// Rejuv dex + forms is ~1,300 sprites; headroom for both sprite tiers.
const SPRITE_MAX_ENTRIES = 4000;

export const runtimeCaching: CachingRule[] = [
  {
    // Inline body, no outer references — see the serialization note above.
    urlPattern: ({ url, sameOrigin }) => sameOrigin && url.pathname.startsWith("/api/"),
    method: "GET",
    handler: "NetworkFirst",
    options: {
      cacheName: API_CACHE,
      cacheableResponse: { statuses: [200] },
      networkTimeoutSeconds: API_NETWORK_TIMEOUT_SECONDS,
    },
  },
  {
    urlPattern: SPRITE_CDN_PATTERN,
    method: "GET",
    handler: "CacheFirst",
    options: {
      cacheName: SPRITE_CACHE,
      cacheableResponse: { statuses: [0, 200] },
      expiration: { maxEntries: SPRITE_MAX_ENTRIES, maxAgeSeconds: ONE_YEAR_SECONDS },
    },
  },
];
