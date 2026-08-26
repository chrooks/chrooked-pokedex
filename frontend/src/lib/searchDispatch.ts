/* The single rail search live-syncs a search-owned Name pill onto whichever
   entity is active: the dex's `filter` param, moves' `mfilter`, abilities'
   `afilter`. This module is the kind → codec/param dispatch so App can write to
   the right place without each tab owning a search box. The URL is the shared
   store: every write dispatches chrooked:urlchange so useUrlState and the tabs'
   control hooks re-read. Pure module functions, no React. */

import type { KindKey } from "../types";
import { SEARCH_FILTER_ID, syncNameFilter } from "./filterEngine";
import type { FilterEntry } from "./filterEngine";
import { dexCodec } from "./dexViewCodec";
import { moveCodec } from "./moveViewCodec";
import { abilityCodec } from "./abilityViewCodec";
import type { ViewCodec } from "./viewCodec";

/** An entity whose filter param the rail search keeps a Name pill in. */
interface SearchTarget {
  codec: ViewCodec;
  filterParam: string;
}

/** Every entity with a filter builder. Type Chart (live type selection) and the
    non-list kinds have no pills — `searchTargetFor` returns null for them. */
const SEARCH_TARGETS: Partial<Record<KindKey, SearchTarget>> = {
  dex: { codec: dexCodec, filterParam: "filter" },
  moves: { codec: moveCodec, filterParam: "mfilter" },
  abilities: { codec: abilityCodec, filterParam: "afilter" },
};

/** The search target for a kind, or null when the kind has no filter builder. */
export function searchTargetFor(kind: KindKey): SearchTarget | null {
  return SEARCH_TARGETS[kind] ?? null;
}

function readFilter(target: SearchTarget, params: URLSearchParams): FilterEntry[] {
  return target.codec.decodeFilter(params.get(target.filterParam));
}

function writeFilter(
  target: SearchTarget,
  params: URLSearchParams,
  next: FilterEntry[],
): void {
  if (next.length === 0) {
    params.delete(target.filterParam);
  } else {
    params.set(target.filterParam, target.codec.encodeFilter(next));
  }
  const search = params.toString();
  const url = search ? `?${search}` : window.location.pathname;
  window.history.replaceState(null, "", url);
  window.dispatchEvent(new Event("chrooked:urlchange"));
}

/** Live-sync the search box into the target's filter param: add, update, or
    remove the search-owned Name pill to track `query`. No-op (no URL write)
    when the pill is already in sync. */
export function syncSearchToNameFilter(target: SearchTarget, query: string): void {
  const params = new URLSearchParams(window.location.search);
  const current = readFilter(target, params);
  const next = syncNameFilter(current, query);
  if (next === current) return;
  writeFilter(target, params, next);
}

/** Enter in the search box: keep the live pill. Re-ids the search-owned pill to
    the caller's permanent id so clearing the box no longer removes it — or, when
    an identical user pill already exists, drops the now-redundant search pill.
    Returns true when there was a search pill to commit (caller clears the box). */
export function commitSearchPill(target: SearchTarget, id: string): boolean {
  const params = new URLSearchParams(window.location.search);
  const current = readFilter(target, params);
  const pill = current.find(
    (e) => e.kind === "filter" && e.id === SEARCH_FILTER_ID,
  ) as Extract<FilterEntry, { kind: "filter" }> | undefined;
  if (pill === undefined) return false;
  const duplicate = current.some(
    (e) =>
      e.kind === "filter" &&
      e.id !== SEARCH_FILTER_ID &&
      e.field === "name" &&
      e.value.toLowerCase() === pill.value.toLowerCase(),
  );
  const next = duplicate
    ? current.filter((e) => e.id !== SEARCH_FILTER_ID)
    : current.map((e) => (e.id === SEARCH_FILTER_ID ? { ...e, id } : e));
  writeFilter(target, params, next);
  return true;
}
