/* Sprite URL resolution from the PokéAPI sprite CDN. The browser caches these;
   below-the-fold sprites lazy-load.

   Forms share a base national dex number (Hisuian Goodra is 706, like Goodra),
   so a sprite-by-dex URL can only show the base form. `sprite-ids.json` (baked
   by scripts/build_sprite_index.py) maps a form's chrooked_id to its distinct
   PokéAPI form id, so forms render correctly. Anything not in that map — base
   species and cosmetic combos PokéAPI doesn't model — falls back to the dex
   number. A null result (no dex, or a 0 id) tells the cell to draw a placeholder. */

import spriteIds from "../data/sprite-ids.json";
import nationalDex from "../data/national-dex.json";

const SPRITE_BASE =
  "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon";

const FORM_SPRITE_ID: Record<string, number> = spriteIds;
// chrooked_id -> canonical national dex №. The PokéAPI CDN is keyed by national
// dex, but a Target's `dex` field is its own local order (Essentials = PBS file
// position), which desyncs from national once the Target reorders the dex (IF2).
// So resolve the CDN sprite by national dex from this map, not the passed dex.
const NATIONAL_DEX: Record<string, number> = nationalDex;

export function spriteUrl(chrookedId: string, dex: number | null): string | null {
  const formId = FORM_SPRITE_ID[chrookedId];
  if (formId !== undefined) {
    return `${SPRITE_BASE}/${formId}.png`;
  }
  // National dex from the canon map; fall back to the passed dex for ids absent
  // from canon (e.g. Target-only fusions PokéAPI can't sprite anyway).
  const national = NATIONAL_DEX[chrookedId] ?? dex;
  if (national === null || national <= 0) {
    return null;
  }
  return `${SPRITE_BASE}/${national}.png`;
}

/** Return the target-local sprite URL for a given dex №, or null when dex is
    absent / non-positive.  The endpoint 404s if the file is not on disk, so
    the caller should fall back to the CDN url via an onError handler.
    `chrookedId` rides along as a query param so Rejuv targets can resolve
    per-form art (Essentials targets ignore it). */
export function targetSpriteUrl(
  targetId: string,
  dex: number | null,
  chrookedId?: string,
): string | null {
  if (dex === null || dex <= 0) {
    return null;
  }
  const id = chrookedId ? `?id=${encodeURIComponent(chrookedId)}` : "";
  return `/api/targets/${encodeURIComponent(targetId)}/sprite/${dex}${id}`;
}
