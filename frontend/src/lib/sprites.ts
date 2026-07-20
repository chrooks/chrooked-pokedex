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

// Values are usually a PokeAPI form id (10162), but forms PokeAPI models only as
// a *form* rather than a distinct pokemon — Cherrim Sunshine — have no numeric id
// and live at a name-suffixed path instead ("421-sunshine"). Both slot straight
// into the same `<value>.png` url, so the map takes either.
const FORM_SPRITE_ID: Record<string, number | string> = spriteIds;
// chrooked_id -> canonical national dex №. The PokéAPI CDN is keyed by national
// dex, but a Target's `dex` field is its own local order (Essentials = PBS file
// position), which desyncs from national once the Target reorders the dex (IF2).
// So resolve the CDN sprite by national dex from this map, not the passed dex.
const NATIONAL_DEX: Record<string, number> = nationalDex;

// Target snapshots slug forms as `<base>--<formwords>` (Rejuv: `ponyta--galarianform`)
// while the baked maps use the base-snapshot scheme (`ponytagalar`). Bridge the two
// by matching the baked suffix against the form words as a prefix — `galar` matches
// `galarianform`, `hisui` matches `hisuianform` — longest suffix wins. Anything with
// no match resolves under its base id, which at worst shows the base sprite.
const _resolved = new Map<string, string>();

function canonicalId(chrookedId: string): string {
  if (!chrookedId.includes("--")) return chrookedId;
  const cached = _resolved.get(chrookedId);
  if (cached !== undefined) return cached;
  const [base, ...rest] = chrookedId.split("--");
  const form = rest.join("");
  let best = base;
  for (const key of Object.keys(FORM_SPRITE_ID)) {
    if (!key.startsWith(base) || key.length <= best.length) continue;
    if (form.startsWith(key.slice(base.length))) best = key;
  }
  _resolved.set(chrookedId, best);
  return best;
}

export function spriteUrl(chrookedId: string, dex: number | null): string | null {
  const id = canonicalId(chrookedId);
  const formId = FORM_SPRITE_ID[id];
  if (formId !== undefined) {
    return `${SPRITE_BASE}/${formId}.png`;
  }
  // National dex from the canon map; fall back to the passed dex for ids absent
  // from canon (e.g. Target-only fusions PokéAPI can't sprite anyway).
  const national = NATIONAL_DEX[id] ?? dex;
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
