/* The phase machine behind the proposal flow, as a pure reducer so it is
   testable without a DOM (mirrors the project's pure-logic test convention).

   Phases (Progressive Disclosure):
     idle      — only the `✦ suggest` affordance shows.
     input     — the direction input is open, awaiting a submit.
     loading   — the /suggest call is in flight (Poké Ball spinner).
     proposed  — a draft is in hand; the proposed column shows, editable.
     applying  — the Apply PUT is in flight.
     applied   — the section was written; provisional amber resolves to solid.
     error     — a /suggest or Apply call failed; carries the server's message.

   The `Draft` is section-specific (abilities vs learnset); the machine never
   inspects it, so the same machine drives both sections (ac7). */

export type SuggestPhase =
  | "idle"
  | "input"
  | "loading"
  | "proposed"
  | "applying"
  | "applied"
  | "error";

/** The error origin, so the UI can word a 503 (key/snapshot) vs an Apply 422
    (loader rejected the draft) honestly. */
export type SuggestErrorKind = "suggest" | "apply";

export interface SuggestState<Draft> {
  phase: SuggestPhase;
  /** The author's freeform steer; persists across a re-suggest so they can edit. */
  direction: string;
  /** The current (possibly user-edited) draft, or null before a proposal. */
  draft: Draft | null;
  /** Per-key rationale from the model (slot name, or "learnset"). */
  rationale: Record<string, string>;
  /** The model's swappable runner-up picks. */
  alternatives: import("../../types").ProposalAlternative[];
  /** The server's verbatim message on a failed suggest/apply, else null. */
  error: string | null;
  /** Where a present `error` came from, so the UI can phrase it. */
  errorKind: SuggestErrorKind | null;
}

export type SuggestAction<Draft> =
  | { type: "open" }
  | { type: "setDirection"; direction: string }
  | { type: "submit" }
  | {
      type: "proposed";
      draft: Draft;
      rationale: Record<string, string>;
      alternatives: import("../../types").ProposalAlternative[];
    }
  | { type: "failed"; kind: SuggestErrorKind; message: string }
  | { type: "editDraft"; draft: Draft }
  | { type: "apply" }
  | { type: "applied" }
  | { type: "reset" };

export function initialState<Draft>(): SuggestState<Draft> {
  return {
    phase: "idle",
    direction: "",
    draft: null,
    rationale: {},
    alternatives: [],
    error: null,
    errorKind: null,
  };
}

/** What the shell shows for the section body, given the current state. The
    read-only body and the current │ proposed grid are MUTUALLY EXCLUSIVE: while a
    draft exists the renderer's grid IS the current column, so the read-only list
    must NOT also render (else it triplicates — the BOUNCE 1 defect). Pure so it is
    guarded without a DOM. */
export function sectionBody<Draft>(
  state: SuggestState<Draft>,
): "readonly" | "columns" {
  return state.draft !== null ? "columns" : "readonly";
}

/** Pure transition. Unknown actions for the current phase are no-ops, so a
    stray click during a pending call can't corrupt the flow. */
export function suggestReducer<Draft>(
  state: SuggestState<Draft>,
  action: SuggestAction<Draft>,
): SuggestState<Draft> {
  switch (action.type) {
    case "open":
      // From idle (or back from an error/applied) reveal the direction input.
      return { ...state, phase: "input", error: null, errorKind: null };

    case "setDirection":
      return { ...state, direction: action.direction };

    case "submit":
      // Only a primed input (or a re-suggest from proposed) can start a call.
      if (state.phase !== "input" && state.phase !== "proposed") return state;
      return { ...state, phase: "loading", error: null, errorKind: null };

    case "proposed":
      return {
        ...state,
        phase: "proposed",
        draft: action.draft,
        rationale: action.rationale,
        alternatives: action.alternatives,
        error: null,
        errorKind: null,
      };

    case "failed":
      return {
        ...state,
        phase: "error",
        error: action.message,
        errorKind: action.kind,
      };

    case "editDraft":
      // Curating a cell only makes sense once a draft exists.
      if (state.draft === null) return state;
      return { ...state, draft: action.draft };

    case "apply":
      if (state.phase !== "proposed" || state.draft === null) return state;
      return { ...state, phase: "applying", error: null, errorKind: null };

    case "applied":
      return { ...state, phase: "applied" };

    case "reset":
      return initialState<Draft>();

    default:
      return state;
  }
}
