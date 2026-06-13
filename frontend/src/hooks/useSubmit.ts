/* Wraps a single async write (save or delete) with the state every editor
   needs: in-flight, the server's verbatim error message (the loader's 422
   text), and the citing-species list when a delete is blocked by the 409
   delete-guard. Keeps each editor's handler free of try/catch boilerplate. */

import { useCallback, useState } from "react";
import { citingFrom } from "../api";

export interface SubmitState {
  isSaving: boolean;
  /** The server's verbatim message on failure (422 loader text, 409, 503). */
  error: string | null;
  /** Species names blocking a delete (HTTP 409), or null. */
  citing: string[] | null;
  /** Run `action`; resolves to true on success, false on failure. */
  run: (action: () => Promise<unknown>) => Promise<boolean>;
  /** Clear the current error/citing without running anything. */
  reset: () => void;
}

export function useSubmit(): SubmitState {
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [citing, setCiting] = useState<string[] | null>(null);

  const reset = useCallback(() => {
    setError(null);
    setCiting(null);
  }, []);

  const run = useCallback(async (action: () => Promise<unknown>): Promise<boolean> => {
    setIsSaving(true);
    setError(null);
    setCiting(null);
    try {
      await action();
      return true;
    } catch (caught: unknown) {
      setCiting(citingFrom(caught));
      setError(caught instanceof Error ? caught.message : "Unexpected error");
      return false;
    } finally {
      setIsSaving(false);
    }
  }, []);

  return { isSaving, error, citing, run, reset };
}
