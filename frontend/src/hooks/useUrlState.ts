/* View state persisted in the URL query string, so a reload or a shared link
   restores the same tab, search, filter, and open species. A tiny replacement
   for a router: the tool is one page, so we sync a handful of params by hand. */

import { useCallback, useSyncExternalStore } from "react";
import type { KindKey } from "../types";
import type { ColumnKey } from "../lib/dexColumns";
import type { FilterEntry } from "../lib/dexFilters";
import type { SortKey } from "../lib/dexSort";
import {
  decodeFilter,
  decodeHidden,
  decodeSort,
  encodeFilter,
  encodeHidden,
  encodeSort,
} from "../lib/dexViewCodec";
import { decodeParty, encodeParty, type PartyMember } from "../lib/teamViewCodec";
import { decodeMakeover, encodeMakeover, MAKEOVER_PARAMS } from "../lib/makeoverUrlCodec";
import type { DesignStage, Stage } from "../lib/makeoverStages";

export type DexLayout = "grid" | "table";

export interface ViewState {
  kind: KindKey;
  query: string;
  editedOnly: boolean;
  /** Expand every match to its whole evolution line (dex only). */
  evoLine: boolean;
  selected: string | null;
  /** How the open species renders: the side panel (default) or full-page. */
  detail: "panel" | "full";
  layout: DexLayout;
  /** The boolean filter tree (applies to both grid and table). */
  filter: FilterEntry[];
  /** Multi-key sort, priority-ordered (table-only effect). */
  sort: SortKey[];
  /** Hidden data columns (table-only effect). */
  hidden: ColumnKey[];
  /** A Target id whose backdrop the dex is showing (target ⊕ Ruleset), or null
      for the base ⊕ Ruleset canon. Set from the Targets panel after a preview. */
  backdrop: string | null;
  /** The Team tab's party: up to six species (+ optional ability), shareable via
      the URL like every other view state. */
  party: PartyMember[];
  /** The Makeover Workbench anchor species (its chrooked_id), or null when the
      workbench is closed. URL-persisted so a reload restores it. */
  makeover: string | null;
  /** The active makeover stage, or null to derive it from the Ruleset state. */
  makeoverStage: Stage | null;
  /** An explicit à-la-carte stage seed for the workbench (deep links from a
      profile section's suggest button), or null for smart defaults. */
  makeoverSelect: DesignStage[] | null;
}

const KINDS: readonly KindKey[] = [
  "dex",
  "moves",
  "abilities",
  "type-chart",
  "team",
  "behaviors",
  "targets",
  "ledger",
];

// useSyncExternalStore requires a STABLE snapshot: getSnapshot must return the
// same object until the store actually changes, or React re-renders forever.
// We cache by the raw query string and only rebuild when it differs.
let cachedSearch: string | null = null;
let cachedState: ViewState | null = null;

function readState(): ViewState {
  const search = window.location.search;
  if (cachedSearch === search && cachedState !== null) {
    return cachedState;
  }
  const params = new URLSearchParams(search);
  const rawKind = params.get("kind");
  const kind = (KINDS as string[]).includes(rawKind ?? "")
    ? (rawKind as KindKey)
    : "dex";
  cachedSearch = search;
  const mk = decodeMakeover(params);
  cachedState = {
    kind,
    query: params.get("q") ?? "",
    editedOnly: params.get("edited") === "1",
    evoLine: params.get("line") === "1",
    selected: params.get("id"),
    detail: params.get("detail") === "full" ? "full" : "panel",
    layout: params.get("view") === "table" ? "table" : "grid",
    filter: decodeFilter(params.get("filter")),
    sort: decodeSort(params.get("sort")),
    hidden: decodeHidden(params.get("hide")),
    backdrop: params.get("backdrop"),
    party: decodeParty(params.get("team")),
    makeover: mk.species,
    makeoverStage: mk.stage,
    makeoverSelect: mk.selected,
  };
  return cachedState;
}

function subscribe(callback: () => void): () => void {
  window.addEventListener("popstate", callback);
  window.addEventListener("chrooked:urlchange", callback);
  return () => {
    window.removeEventListener("popstate", callback);
    window.removeEventListener("chrooked:urlchange", callback);
  };
}

/** The params useUrlState owns; everything else (the moves/abilities entity
    params: mfilter/msort/mhide, afilter/asort/ahide) is preserved untouched so
    each tab keeps its own control state with no cross-bleed (D3). */
const OWNED_PARAMS = [
  "kind",
  "q",
  "edited",
  "line",
  "id",
  "detail",
  "view",
  "filter",
  "sort",
  "hide",
  "backdrop",
  "team",
  ...MAKEOVER_PARAMS,
] as const;

function writeState(next: ViewState): void {
  // Start from the live params so foreign keys survive, then rewrite only ours.
  const params = new URLSearchParams(window.location.search);
  for (const key of OWNED_PARAMS) params.delete(key);
  if (next.kind !== "dex") params.set("kind", next.kind);
  if (next.query) params.set("q", next.query);
  if (next.editedOnly) params.set("edited", "1");
  if (next.evoLine) params.set("line", "1");
  if (next.selected) params.set("id", next.selected);
  if (next.detail === "full") params.set("detail", "full");
  if (next.layout === "table") params.set("view", "table");
  if (next.filter.length) params.set("filter", encodeFilter(next.filter));
  if (next.sort.length) params.set("sort", encodeSort(next.sort));
  if (next.hidden.length) params.set("hide", encodeHidden(next.hidden));
  if (next.backdrop) params.set("backdrop", next.backdrop);
  if (next.party.length) params.set("team", encodeParty(next.party));
  encodeMakeover(params, {
    species: next.makeover,
    stage: next.makeoverStage,
    selected: next.makeoverSelect,
  });

  const search = params.toString();
  const url = search ? `?${search}` : window.location.pathname;
  window.history.replaceState(null, "", url);
  window.dispatchEvent(new Event("chrooked:urlchange"));
}

export function useUrlState(): [ViewState, (patch: Partial<ViewState>) => void] {
  const state = useSyncExternalStore(subscribe, readState, readState);

  const update = useCallback((patch: Partial<ViewState>) => {
    writeState({ ...readState(), ...patch });
  }, []);

  return [state, update];
}
