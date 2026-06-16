/* Namespaced, URL-persisted control state for a non-dex entity (moves /
   abilities). Each entity owns its own param trio — e.g. mfilter/msort/mhide,
   afilter/asort/ahide — so a power≥100 pill on Moves never bleeds into the dex
   or Abilities (D3). Reads/writes preserve every other param, and the same
   chrooked:urlchange event drives re-render as the dex's useUrlState. */

import { useCallback, useSyncExternalStore } from "react";
import type { FilterEntry } from "../lib/filterEngine";
import type { SortKey } from "../lib/sortEngine";
import type { ViewCodec } from "../lib/viewCodec";

export interface EntityView {
  filter: FilterEntry[];
  sort: SortKey[];
  hidden: string[];
}

export interface EntityViewPatchInput {
  filter?: FilterEntry[];
  sort?: SortKey[];
  hidden?: string[];
}

/** The three namespaced param keys for one entity (filter / sort / hide). */
export interface EntityParamKeys {
  filter: string;
  sort: string;
  hide: string;
}

function subscribe(callback: () => void): () => void {
  window.addEventListener("popstate", callback);
  window.addEventListener("chrooked:urlchange", callback);
  return () => {
    window.removeEventListener("popstate", callback);
    window.removeEventListener("chrooked:urlchange", callback);
  };
}

// useSyncExternalStore needs a STABLE snapshot per entity: cache by the raw
// search string + the param keys identity so getSnapshot returns the same object
// until the URL actually changes. Keyed by the filter param name (unique per
// entity) so moves and abilities each keep their own cache slot.
const snapshotCache = new Map<string, { search: string; value: EntityView }>();

function readView(codec: ViewCodec, keys: EntityParamKeys): EntityView {
  const search = window.location.search;
  const cached = snapshotCache.get(keys.filter);
  if (cached && cached.search === search) {
    return cached.value;
  }
  const params = new URLSearchParams(search);
  const value: EntityView = {
    filter: codec.decodeFilter(params.get(keys.filter)),
    sort: codec.decodeSort(params.get(keys.sort)),
    hidden: codec.decodeHidden(params.get(keys.hide)),
  };
  snapshotCache.set(keys.filter, { search, value });
  return value;
}

function writeView(
  codec: ViewCodec,
  keys: EntityParamKeys,
  next: EntityView,
): void {
  const params = new URLSearchParams(window.location.search);
  params.delete(keys.filter);
  params.delete(keys.sort);
  params.delete(keys.hide);
  if (next.filter.length) params.set(keys.filter, codec.encodeFilter(next.filter));
  if (next.sort.length) params.set(keys.sort, codec.encodeSort(next.sort));
  if (next.hidden.length) params.set(keys.hide, codec.encodeHidden(next.hidden));

  const search = params.toString();
  const url = search ? `?${search}` : window.location.pathname;
  window.history.replaceState(null, "", url);
  window.dispatchEvent(new Event("chrooked:urlchange"));
}

/** Read + patch one entity's namespaced control state, persisted in the URL. */
export function useEntityView(
  codec: ViewCodec,
  keys: EntityParamKeys,
): [EntityView, (patch: EntityViewPatchInput) => void] {
  const getSnapshot = useCallback(() => readView(codec, keys), [codec, keys]);
  const view = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  const update = useCallback(
    (patch: EntityViewPatchInput) => {
      writeView(codec, keys, { ...readView(codec, keys), ...patch });
    },
    [codec, keys],
  );

  return [view, update];
}
