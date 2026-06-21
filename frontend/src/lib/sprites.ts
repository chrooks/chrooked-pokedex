/* Sprite URL resolution from the PokéAPI sprite CDN. The browser caches these;
   below-the-fold sprites lazy-load.

   Forms share a base national dex number (Hisuian Goodra is 706, like Goodra),
   so a sprite-by-dex URL can only show the base form. `sprite-ids.json` (baked
   by scripts/build_sprite_index.py) maps a form's chrooked_id to its distinct
   PokéAPI form id, so forms render correctly. Anything not in that map — base
   species and cosmetic combos PokéAPI doesn't model — falls back to the dex
   number. A null result (no dex, or a 0 id) tells the cell to draw a placeholder. */

import spriteIds from "../data/sprite-ids.json";

const SPRITE_BASE =
  "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon";

const FORM_SPRITE_ID: Record<string, number> = spriteIds;

export function spriteUrl(chrookedId: string, dex: number | null): string | null {
  const formId = FORM_SPRITE_ID[chrookedId];
  if (formId !== undefined) {
    return `${SPRITE_BASE}/${formId}.png`;
  }
  if (dex === null || dex <= 0) {
    return null;
  }
  return `${SPRITE_BASE}/${dex}.png`;
}

/** Return the target-local sprite URL for a given dex №, or null when dex is
    absent / non-positive.  The endpoint 404s if the file is not on disk, so
    the caller should fall back to the CDN url via an onError handler. */
export function targetSpriteUrl(targetId: string, dex: number | null): string | null {
  if (dex === null || dex <= 0) {
    return null;
  }
  return `/api/targets/${encodeURIComponent(targetId)}/sprite/${dex}`;
}
