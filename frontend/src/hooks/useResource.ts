/* A minimal abortable fetch hook for the read-only M1 surfaces. One in-flight
   request per resource; the previous is aborted when the fetcher changes or the
   component unmounts (no stale-closure writes). When M2 adds mutations, this is
   the seam to swap for TanStack Query — kept deliberately small until then. */

import { useEffect, useState } from "react";
import { ApiError } from "../api";

export interface ResourceState<T> {
  data: T | null;
  error: string | null;
  status: number | null;
  isLoading: boolean;
}

/**
 * `fetcher` MUST be a stable reference (a module-level function like `api.dex`,
 * or a `useCallback`). It is the effect's only dependency, so a new function
 * each render would re-fetch in a loop.
 */
export function useResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
): ResourceState<T> {
  const [state, setState] = useState<ResourceState<T>>({
    data: null,
    error: null,
    status: null,
    isLoading: true,
  });

  useEffect(() => {
    const controller = new AbortController();
    setState({ data: null, error: null, status: null, isLoading: true });

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
        setState({
          data: null,
          error: messageOf(error),
          status: error instanceof ApiError ? error.status : null,
          isLoading: false,
        });
      });

    return () => controller.abort();
  }, [fetcher]);

  return state;
}

function messageOf(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}
