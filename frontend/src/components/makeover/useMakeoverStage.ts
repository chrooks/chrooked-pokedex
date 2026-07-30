/* The per-stage heartbeat: propose → tweak → LOCK IN, with the hybrid tweak loop
   (ac3). A design stage proposes via the existing /api suggest Seam, lets the
   author edit the draft inline AND re-roll with a redirect that carries their
   edits forward as constraints, and writes NOTHING to the Ruleset until an
   explicit LOCK IN (the read-merge-write through the existing CRUD route). The
   pure re-roll rule lives in lib/makeoverTweak.ts and is unit-tested there. */

import { useCallback, useReducer } from "react";
import { api, ApiError } from "../../api";
import type { DexEntry, SpeciesOverride } from "../../types";
import {
  rerollDirection,
  type MakeoverSection,
  type SectionDraft,
} from "../../lib/makeoverTweak";
import type { ProposalAlternative } from "../../types";

export type StagePhase = "propose" | "proposing" | "proposed" | "locking" | "error";
// "flagged": a proposal came back but tripped a soft bound — shown for editing
// with the reason banner above it (distinct from "propose", a hard NO PROPOSAL).
export type StageErrorKind = "propose" | "lock" | "flagged";

export interface StageProposal<Draft> {
  draft: Draft;
  rationale: Record<string, string>;
  alternatives: ProposalAlternative[];
  /** Per-item verbatim warnings on a PARTIAL proposal (e.g. an ability slot the
      model couldn't fill with a real ability). The stage stays usable. */
  warnings?: string[];
  /** Set when the draft is flagged (a soft bound tripped) but still editable —
      surfaced as a banner above the shown draft. */
  error?: string;
}

interface State<Draft> {
  phase: StagePhase;
  /** The author's freeform redirect steer; persists across a re-roll. */
  direction: string;
  /** The working (possibly hand-edited) draft, or null before a proposal. */
  draft: Draft | null;
  /** The last draft the model proposed — the baseline the re-roll diffs against. */
  baseline: Draft | null;
  rationale: Record<string, string>;
  alternatives: ProposalAlternative[];
  /** Per-item warnings from a partial proposal (verbatim server messages). */
  warnings: string[];
  error: string | null;
  errorKind: StageErrorKind | null;
}

type Action<Draft> =
  | { type: "setDirection"; direction: string }
  | { type: "proposing" }
  | { type: "proposed"; proposal: StageProposal<Draft> }
  | { type: "edit"; draft: Draft }
  | { type: "locking" }
  | { type: "failed"; kind: StageErrorKind; message: string };

function reducer<Draft>(state: State<Draft>, action: Action<Draft>): State<Draft> {
  switch (action.type) {
    case "setDirection":
      return { ...state, direction: action.direction };
    case "proposing":
      return { ...state, phase: "proposing", error: null, errorKind: null };
    case "proposed":
      return {
        ...state,
        phase: "proposed",
        draft: action.proposal.draft,
        baseline: action.proposal.draft,
        rationale: action.proposal.rationale,
        alternatives: action.proposal.alternatives,
        warnings: action.proposal.warnings ?? [],
        // A flagged draft still lands in "proposed" (shown + editable); its reason
        // rides along as a banner rather than blocking the draft.
        error: action.proposal.error ?? null,
        errorKind: action.proposal.error ? "flagged" : null,
      };
    case "edit":
      // Curating a row only makes sense once a draft exists.
      if (state.draft === null) return state;
      return { ...state, draft: action.draft };
    case "locking":
      if (state.phase !== "proposed" || state.draft === null) return state;
      return { ...state, phase: "locking", error: null, errorKind: null };
    case "failed":
      return { ...state, phase: "error", error: action.message, errorKind: action.kind };
    default:
      return state;
  }
}

function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Unexpected error";
}

export interface UseMakeoverStage<Draft> {
  phase: StagePhase;
  direction: string;
  draft: Draft | null;
  rationale: Record<string, string>;
  alternatives: ProposalAlternative[];
  warnings: string[];
  error: string | null;
  errorKind: StageErrorKind | null;
  setDirection: (text: string) => void;
  /** Run the first proposal (or a re-roll — edits ride along as constraints). */
  propose: () => Promise<void>;
  /** Replace the working draft after an inline edit or an alternative swap. */
  editDraft: (draft: Draft) => void;
  /** Write the locked draft through CRUD (the anchor only). */
  lockIn: () => Promise<boolean>;
}

interface Args<Draft extends SectionDraft> {
  section: MakeoverSection;
  entry: DexEntry;
  /** The direction carried from the direction stage — the first proposal's steer. */
  initialDirection?: string;
  /** The suggest call for this section (the existing /api Seam). */
  propose: (id: string, direction: string) => Promise<StageProposal<Draft>>;
  /** Merge the locked draft into the raw Override (this section's field only). */
  merge: (raw: SpeciesOverride, draft: Draft) => SpeciesOverride;
  /** Called once the lock lands cleanly, with the locked draft (record facts). */
  onLocked: (draft: Draft) => void;
  /** Called with every author-typed steer (first-propose direction or re-roll
      redirect), so the session harvests it into the design log's corrections. */
  onRedirect?: (text: string) => void;
}

function seedOverride(entry: DexEntry): SpeciesOverride {
  return {
    name: entry.name,
    chrooked_id: entry.chrooked_id,
    aka: entry.dex !== null ? { dex: entry.dex } : {},
    types: null,
    abilities: null,
    stats: null,
    learnset: null,
    evolution: null,
  };
}

export function useMakeoverStage<Draft extends SectionDraft>({
  section,
  entry,
  initialDirection,
  propose,
  merge,
  onLocked,
  onRedirect,
}: Args<Draft>): UseMakeoverStage<Draft> {
  const [state, dispatch] = useReducer(reducer<Draft>, {
    phase: "propose",
    direction: initialDirection ?? "",
    draft: null,
    baseline: null,
    rationale: {},
    alternatives: [],
    warnings: [],
    error: null,
    errorKind: null,
  });

  const setDirection = useCallback(
    (direction: string) => dispatch({ type: "setDirection", direction }),
    [],
  );

  const editDraft = useCallback(
    (draft: Draft) => dispatch({ type: "edit", draft }),
    [],
  );

  const runPropose = useCallback(async () => {
    // On a re-roll (a draft already exists) fold the author's edits into the
    // direction so their hand-tuning survives (ac3). The first proposal just
    // sends the raw direction.
    const isReroll = state.draft !== null;
    const composed = isReroll
      ? rerollDirection(section, state.direction, state.baseline, state.draft)
      : state.direction;
    // Harvest every author-typed steer so it lands in the design log: all re-roll
    // redirects, AND a first-propose direction the author wrote or edited. The
    // injected initialDirection is excluded — it is already the log's `direction`.
    const isAuthorSteer = isReroll
      ? composed.trim() !== ""
      : composed.trim() !== "" && composed !== (initialDirection ?? "");
    if (isAuthorSteer) onRedirect?.(composed);
    dispatch({ type: "proposing" });
    try {
      const proposal = await propose(entry.chrooked_id, composed);
      dispatch({ type: "proposed", proposal });
    } catch (caught: unknown) {
      dispatch({ type: "failed", kind: "propose", message: messageOf(caught) });
    }
  }, [section, state.direction, state.baseline, state.draft, propose, entry.chrooked_id, onRedirect, initialDirection]);

  const lockIn = useCallback(async (): Promise<boolean> => {
    if (state.draft === null) return false;
    const draft = state.draft;
    dispatch({ type: "locking" });
    try {
      let raw: SpeciesOverride;
      try {
        raw = await api.speciesOverride(entry.chrooked_id);
      } catch {
        raw = seedOverride(entry);
      }
      await api.putSpecies(entry.chrooked_id, merge(raw, draft));
      onLocked(draft);
      return true;
    } catch (caught: unknown) {
      dispatch({ type: "failed", kind: "lock", message: messageOf(caught) });
      return false;
    }
  }, [state.draft, entry, merge, onLocked]);

  return {
    phase: state.phase,
    direction: state.direction,
    draft: state.draft,
    rationale: state.rationale,
    alternatives: state.alternatives,
    warnings: state.warnings,
    error: state.error,
    errorKind: state.errorKind,
    setDirection,
    propose: runPropose,
    editDraft,
    lockIn,
  };
}
