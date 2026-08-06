/* Saved expressions: a name → encoded-filter map, per entity, persisted in
   localStorage. Each value is exactly encodeFilter()'s output — the same string
   the `filter` / `mfilter` / `afilter` URL param carries — so a saved expression
   IS the share code, the same Decision Ledger savedTeams follows.

   Scoped by entity because the field registries differ: a dex expression names
   `bst` and `class`, a move expression names `power` and `flags`. Applying one
   to the other would build tokens for fields that entity cannot filter on.

   Pure and Storage-agnostic: every function takes a StorageLike, so a test can
   pass a plain in-memory fake. Any corruption at the key — bad JSON, wrong
   shape, foreign data — reads back empty, never a throw. */

import type { StorageLike } from "./savedTeams";

export const SAVED_FILTERS_KEY = "chrooked-saved-filters-v1";

/** name → encoded filter (encodeFilter output). */
export type SavedExpressions = Record<string, string>;

/** entity id (the control stack's idPrefix) → its saved expressions. */
export type SavedFilters = Record<string, SavedExpressions>;

/** How many expressions one entity may hold. A cap keeps the menu scannable and
    stops a runaway caller filling the storage quota. */
export const MAX_SAVED = 24;

function isSavedFilters(value: unknown): value is SavedFilters {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  return Object.values(value as Record<string, unknown>).every(
    (group) =>
      group !== null &&
      typeof group === "object" &&
      !Array.isArray(group) &&
      Object.values(group as Record<string, unknown>).every((v) => typeof v === "string"),
  );
}

/** Read the whole store. Corrupt or foreign data collapses to `{}`. */
export function loadSavedFilters(storage: StorageLike): SavedFilters {
  const raw = storage.getItem(SAVED_FILTERS_KEY);
  if (!raw) return {};
  try {
    const parsed: unknown = JSON.parse(raw);
    return isSavedFilters(parsed) ? { ...parsed } : {};
  } catch {
    return {};
  }
}

/** One entity's saved expressions, in insertion order. */
export function expressionsFor(storage: StorageLike, entity: string): SavedExpressions {
  return loadSavedFilters(storage)[entity] ?? {};
}

/**
 * Save (or overwrite) an expression under a name. A blank name and an empty
 * expression are both rejected here, not only in the UI — an unnamed or empty
 * entry would show in the menu as a row that does nothing.
 */
export function saveExpression(
  storage: StorageLike,
  entity: string,
  name: string,
  encoded: string,
): SavedFilters {
  const trimmed = name.trim();
  const current = loadSavedFilters(storage);
  const group = current[entity] ?? {};
  if (trimmed === "" || encoded === "") return current;
  // Overwriting an existing name is fine; only a NEW name can hit the cap.
  if (!(trimmed in group) && Object.keys(group).length >= MAX_SAVED) return current;
  const next: SavedFilters = { ...current, [entity]: { ...group, [trimmed]: encoded } };
  storage.setItem(SAVED_FILTERS_KEY, JSON.stringify(next));
  return next;
}

/** Delete one expression by name (a no-op if absent). */
export function deleteExpression(
  storage: StorageLike,
  entity: string,
  name: string,
): SavedFilters {
  const current = loadSavedFilters(storage);
  const group = current[entity];
  if (!group || !(name in group)) return current;
  const nextGroup = { ...group };
  delete nextGroup[name];
  const next: SavedFilters = { ...current, [entity]: nextGroup };
  storage.setItem(SAVED_FILTERS_KEY, JSON.stringify(next));
  return next;
}
