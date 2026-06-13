/* View state persisted in the URL query string, so a reload or a shared link
   restores the same tab, search, filter, and open species. A tiny replacement
   for a router: the tool is one page, so we sync a handful of params by hand. */

import { useCallback, useSyncExternalStore } from "react";
import type { KindKey } from "../types";

export interface ViewState {
  kind: KindKey;
  query: string;
  editedOnly: boolean;
  selected: string | null;
}

const KINDS: readonly KindKey[] = [
  "dex",
  "moves",
  "abilities",
  "type-chart",
  "behaviors",
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
  cachedState = {
    kind,
    query: params.get("q") ?? "",
    editedOnly: params.get("edited") === "1",
    selected: params.get("id"),
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

function writeState(next: ViewState): void {
  const params = new URLSearchParams();
  if (next.kind !== "dex") params.set("kind", next.kind);
  if (next.query) params.set("q", next.query);
  if (next.editedOnly) params.set("edited", "1");
  if (next.selected) params.set("id", next.selected);

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
