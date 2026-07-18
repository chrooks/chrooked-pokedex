/* A minimal abortable fetch hook for the local API surfaces. One in-flight
   request per resource; the previous is aborted when the fetcher changes, the
   component unmounts, or a `reload()` is requested (no stale-closure writes).

   M2a added `reload()` so a write (save/delete) can refetch its list in place.
   This is still the seam to swap for TanStack Query when caching/optimistic
   updates earn it — kept deliberately small until then. */

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api";

export interface ResourceState<T> {
  data: T | null;
  error: string | null;
  status: number | null;
  isLoading: boolean;
  /** Re-run the fetcher (e.g. after a write changed the data on disk). */
  reload: () => void;
  /** Locally patch the cached data (e.g. an optimistic edit before the write
      round-trips). Does not touch loading/error state or trigger a fetch. */
  mutate: (updater: (data: T | null) => T | null) => void;
}

/**
 * `fetcher` MUST be a stable reference (a module-level function like `api.dex`,
 * or a `useCallback`). It is the effect's only data dependency, so a new
 * function each render would re-fetch in a loop.
 */
// Module-level cache keyed by fetcher identity (fetcher must be a stable
// module-level/useCallback ref, same contract as below). Survives the tab
// component unmounting — switching tabs shows the last-fetched data instantly
// instead of a skeleton, then revalidates in the background.
const cache = new WeakMap<
  (signal: AbortSignal) => Promise<unknown>,
  unknown
>();

export function useResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
): ResourceState<T> {
  const cached = cache.get(fetcher) as T | undefined;
  const [state, setState] = useState<Omit<ResourceState<T>, "reload" | "mutate">>({
    data: cached ?? null,
    error: null,
    status: null,
    isLoading: cached === undefined,
  });
  const [token, setToken] = useState(0);
  const reload = useCallback(() => setToken((t) => t + 1), []);
  const mutate = useCallback(
    (updater: (data: T | null) => T | null) => {
      setState((prev) => {
        const data = updater(prev.data);
        cache.set(fetcher, data);
        return { ...prev, data };
      });
    },
    [fetcher],
  );

  useEffect(() => {
    const controller = new AbortController();
    // Stale-while-revalidate: only the FIRST load (no data yet, cached or
    // in-state) shows the skeleton. A reload after a write, or remounting a
    // tab that already has cached data, keeps rows on screen and fetches in
    // the background, so the table never flashes to skeleton or scroll-jumps.
    setState((prev) => ({ ...prev, isLoading: prev.data === null, error: null }));

    fetcher(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          cache.set(fetcher, data);
          setState({ data, error: null, status: 200, isLoading: false });
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        // A failed BACKGROUND revalidate keeps the stale rows rather than
        // blanking to the error view — the write that triggered it already
        // surfaces its own error in the editor. Only a first-load failure (no
        // rows to fall back to) owns the error view.
        setState((prev) => ({
          data: prev.data,
          error: prev.data === null ? messageOf(error) : null,
          status: error instanceof ApiError ? error.status : prev.status,
          isLoading: false,
        }));
      });

    return () => controller.abort();
  }, [fetcher, token]);

  return { ...state, reload, mutate };
}

function messageOf(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}
