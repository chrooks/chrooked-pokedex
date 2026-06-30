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
}

/**
 * `fetcher` MUST be a stable reference (a module-level function like `api.dex`,
 * or a `useCallback`). It is the effect's only data dependency, so a new
 * function each render would re-fetch in a loop.
 */
export function useResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
): ResourceState<T> {
  const [state, setState] = useState<Omit<ResourceState<T>, "reload">>({
    data: null,
    error: null,
    status: null,
    isLoading: true,
  });
  const [token, setToken] = useState(0);
  const reload = useCallback(() => setToken((t) => t + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    // Stale-while-revalidate: only the FIRST load (no data yet) shows the
    // skeleton. A reload after a write keeps the current rows on screen and
    // fetches in the background, so an edit swaps in the new data without the
    // table flashing to skeleton or the scroll jumping to top.
    setState((prev) => ({ ...prev, isLoading: prev.data === null, error: null }));

    fetcher(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
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

  return { ...state, reload };
}

function messageOf(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}
