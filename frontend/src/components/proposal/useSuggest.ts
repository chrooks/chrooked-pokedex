/* The proposal flow as a hook: wraps the pure {@link suggestReducer} phase
   machine and drives the two async edges (the /suggest call, the Apply PUT).

   Section-agnostic by construction — it takes injected `suggest` and `apply`
   functions and never inspects the `Draft`, so one hook drives both the
   abilities and the learnset columns (ac7). The transition logic lives in
   suggestMachine.ts and is unit-tested there without a DOM. */

import { useCallback, useReducer } from "react";
import { ApiError } from "../../api";
import type { ProposalAlternative, SuggestResponse } from "../../types";
import {
  initialState,
  suggestReducer,
  type SuggestState,
} from "./suggestMachine";

/** A short, honest phrasing for a 503 so the author knows nothing was written
    and what to do. Other statuses pass the server's verbatim message through. */
function suggestErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 503) {
      return error.message;
    }
    return error.message;
  }
  return error instanceof Error ? error.message : "Unexpected error";
}

export interface UseSuggest<Draft> {
  state: SuggestState<Draft>;
  /** Reveal the direction input. */
  open: () => void;
  /** Update the freeform direction text. */
  setDirection: (direction: string) => void;
  /** Run the /suggest call with the current direction. */
  submit: () => Promise<void>;
  /** Replace the working draft after a cell edit or an alternative swap. */
  editDraft: (draft: Draft) => void;
  /** Run the Apply PUT (read-merge-write); resolves true on a clean write. */
  apply: () => Promise<boolean>;
  /** Return to idle, clearing the draft. */
  reset: () => void;
}

interface Args<Draft> {
  /** The /suggest call for this section, given the freeform direction. */
  suggest: (direction: string) => Promise<SuggestResponse<Draft>>;
  /** The Apply write for this section, given the curated draft. */
  apply: (draft: Draft) => Promise<unknown>;
  /** Called after a clean Apply so the ledger can refresh. */
  onApplied?: () => void;
}

export function useSuggest<Draft>({
  suggest,
  apply,
  onApplied,
}: Args<Draft>): UseSuggest<Draft> {
  const [state, dispatch] = useReducer(
    suggestReducer<Draft>,
    undefined,
    initialState<Draft>,
  );

  const open = useCallback(() => dispatch({ type: "open" }), []);

  const setDirection = useCallback(
    (direction: string) => dispatch({ type: "setDirection", direction }),
    [],
  );

  const editDraft = useCallback(
    (draft: Draft) => dispatch({ type: "editDraft", draft }),
    [],
  );

  const reset = useCallback(() => dispatch({ type: "reset" }), []);

  const submit = useCallback(async () => {
    dispatch({ type: "submit" });
    try {
      const result = await suggest(state.direction);
      dispatch({
        type: "proposed",
        draft: result.draft,
        rationale: result.rationale ?? {},
        alternatives: (result.alternatives ?? []) as ProposalAlternative[],
      });
    } catch (caught: unknown) {
      dispatch({
        type: "failed",
        kind: "suggest",
        message: suggestErrorMessage(caught),
      });
    }
  }, [suggest, state.direction]);

  const runApply = useCallback(async (): Promise<boolean> => {
    if (state.draft === null) return false;
    dispatch({ type: "apply" });
    try {
      await apply(state.draft);
      dispatch({ type: "applied" });
      onApplied?.();
      return true;
    } catch (caught: unknown) {
      dispatch({
        type: "failed",
        kind: "apply",
        message: suggestErrorMessage(caught),
      });
      return false;
    }
  }, [apply, onApplied, state.draft]);

  return {
    state,
    open,
    setDirection,
    submit,
    editDraft,
    apply: runApply,
    reset,
  };
}
