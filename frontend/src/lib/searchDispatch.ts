/* The single rail search needs to promote a term to a Name filter pill on
   whichever entity is active (ac9). The dex writes through useUrlState's own
   `filter` param; moves and abilities write to their namespaced filter param
   (mfilter / afilter). This module is the kind → codec/param dispatch so
   App.handleSearchEnter can write to the right place without each tab owning a
   search box. Pure module functions; the URL is the shared store and the
   chrooked:urlchange event drives every subscriber's re-render. Pure, no React. */

import type { KindKey } from "../types";
import { appendNameFilter } from "./filterEngine";
import { moveCodec } from "./moveViewCodec";
import { abilityCodec } from "./abilityViewCodec";
import type { ViewCodec } from "./viewCodec";

/** A namespaced entity that the rail search can promote a Name pill onto. */
interface SearchTarget {
  codec: ViewCodec;
  filterParam: string;
}

/** Only the entities with their OWN namespaced filter param. The dex is handled
    inline by App via useUrlState (`filter` param), so it is intentionally
    absent — `searchTargetFor` returns null for it and every non-list kind. */
const SEARCH_TARGETS: Partial<Record<KindKey, SearchTarget>> = {
  moves: { codec: moveCodec, filterParam: "mfilter" },
  abilities: { codec: abilityCodec, filterParam: "afilter" },
};

/** The namespaced search target for a kind, or null when the dex (or a non-list
    kind) owns the search. */
export function searchTargetFor(kind: KindKey): SearchTarget | null {
  return SEARCH_TARGETS[kind] ?? null;
}

/** Promote `query` to a Name pill on the given non-dex entity's namespaced
    filter param, persisting it in the URL. No-op (returns false) when the term
    is blank, a duplicate, or at the pill cap — appendNameFilter signals that by
    returning the same array reference. Returns true when a pill was added so the
    caller can clear the search box. */
export function promoteSearchToPill(
  target: SearchTarget,
  query: string,
  id: string,
): boolean {
  const params = new URLSearchParams(window.location.search);
  const current = target.codec.decodeFilter(params.get(target.filterParam));
  const next = appendNameFilter(current, query, id);
  if (next === current) {
    return false;
  }
  params.set(target.filterParam, target.codec.encodeFilter(next));
  const search = params.toString();
  const url = search ? `?${search}` : window.location.pathname;
  window.history.replaceState(null, "", url);
  window.dispatchEvent(new Event("chrooked:urlchange"));
  return true;
}
