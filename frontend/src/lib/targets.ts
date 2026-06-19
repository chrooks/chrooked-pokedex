/* Pure helpers for the Targets panel: the engine option set + a label map, and
   a client-side guard that the add form is well-formed before we POST. The
   server is the real authority (it 422s a missing / non-git path), but failing
   fast here keeps the submit honest and the Error State legible. No React. */

import type { EngineKey } from "../types";

/** The engines a Target can register as, in display order. Both apply
    end-to-end; the detected version shows in the ENGINE · VERSION readout. */
export const ENGINES: readonly EngineKey[] = ["pokeemerald", "essentials"];

const ENGINE_LABELS: Record<EngineKey, string> = {
  pokeemerald: "pokeemerald",
  essentials: "Essentials",
};

export function engineLabel(engine: EngineKey): string {
  return ENGINE_LABELS[engine] ?? engine;
}

export interface AddTargetDraft {
  label: string;
  path: string;
  engine: EngineKey;
}

/** True when both label and path are non-blank. The server validates that the
    path is a real git repo; this only stops an obviously empty submit. */
export function isAddDraftReady(draft: AddTargetDraft): boolean {
  return draft.label.trim().length > 0 && draft.path.trim().length > 0;
}

/** Normalize a draft for the wire: trim the text fields, keep the engine. */
export function normalizeDraft(draft: AddTargetDraft): AddTargetDraft {
  return {
    label: draft.label.trim(),
    path: draft.path.trim(),
    engine: draft.engine,
  };
}

/** True when an error is the dirty-working-tree refusal (HTTP 409). Drives the
    Force-toggle Error State on Apply. */
export function isDirtyTreeStatus(status: number | null): boolean {
  return status === 409;
}
