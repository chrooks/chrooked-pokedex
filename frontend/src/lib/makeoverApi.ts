/* The makeover-specific API calls, layered over the SAME backend Seams the chat
   skills use (One Seam): the species-suggest endpoints, the apply/read-back
   targets machinery, and the two small makeover routes (rubric, design-log). Kept
   in its own module so the shared api.ts stays untouched; reuses ApiError for
   honest, verbatim server messages (422/503 surfaced as-is). */

import { ApiError } from "../api";
import type { AbilitySlots, ApplyReportSummary } from "../types";
import type { LearnsetRubric } from "./learnsetBands";

async function postJson<T>(path: string, payload?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: payload !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: payload !== undefined ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) throw await toError(response);
  return (await response.json()) as T;
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal });
  if (!response.ok) throw await toError(response);
  return (await response.json()) as T;
}

async function toError(response: Response): Promise<ApiError> {
  let detail: unknown = null;
  try {
    const body = (await response.json()) as { detail?: unknown };
    detail = body.detail ?? null;
  } catch {
    // Non-JSON error body; fall through to the status line.
  }
  const message =
    typeof detail === "string"
      ? detail
      : `Request failed (${response.status} ${response.statusText})`;
  return new ApiError(response.status, message, detail);
}

/** One lore-grounded makeover direction: a typing + a short role label. */
export interface LoreOption {
  types: string[];
  role: string;
  rationale: string;
}

export interface LoreOptionsResponse {
  draft: { options: LoreOption[] };
  rationale: Record<string, string>;
}

export interface TypingProposal {
  draft: { types: string[] };
  rationale: Record<string, string>;
  alternatives: { value: unknown; rationale: string }[];
}

export interface StatsProposal {
  draft: { stats: Record<string, number> };
  rationale: Record<string, string>;
  alternatives: { value: unknown; rationale: string }[];
}

/** One species' read-back diff: per-field expected/actual checks + a headline. */
export interface ReadBackFieldCheck {
  field: string;
  expected: unknown;
  actual: unknown;
  ok: boolean;
}
export interface ReadBackSpecies {
  chrooked_id: string;
  name: string;
  missing: boolean;
  checks: ReadBackFieldCheck[];
  ok_count: number;
  total: number;
  ok: boolean;
}
export interface ReadBackResponse {
  species: ReadBackSpecies[];
  ok_count: number;
  total: number;
  ok: boolean;
}

export const makeoverApi = {
  /** The makeover opening move: 2-3 lore-grounded typing+role directions, on the
      species-suggest typing Seam (`mode: "lore-options"`). */
  loreOptions: (id: string, direction?: string) =>
    postJson<LoreOptionsResponse>(
      `/api/species/${encodeURIComponent(id)}/suggest/typing`,
      { mode: "lore-options", direction },
    ),
  suggestTyping: (id: string, direction?: string) =>
    postJson<TypingProposal>(
      `/api/species/${encodeURIComponent(id)}/suggest/typing`,
      { direction },
    ),
  suggestStats: (id: string, direction?: string) =>
    postJson<StatsProposal>(
      `/api/species/${encodeURIComponent(id)}/suggest/stats`,
      { direction },
    ),
  /** The pacing-band rubric — the single source of truth the learnset stage
      annotates rows against. */
  learnsetRubric: (signal?: AbortSignal) =>
    getJson<LearnsetRubric>("/api/meta/learnset-rubric", signal),
  /** Apply the Ruleset to a registered Target (the auto tail). Surfaces the full
      Apply Report; blocked entries are named, never summarized. */
  applyTarget: (targetId: string, force = false) =>
    postJson<ApplyReportSummary>(
      `/api/targets/${encodeURIComponent(targetId)}/apply`,
      { force },
    ),
  /** Read the applied species back off the Target and diff vs the Ruleset. */
  readBack: (targetId: string, chrookedIds: string[]) =>
    postJson<ReadBackResponse>(
      `/api/targets/${encodeURIComponent(targetId)}/read-back`,
      { chrooked_ids: chrookedIds },
    ),
  /** Append the harvested design-log entry after the one-line confirm. */
  appendDesignLog: (payload: {
    line: string;
    direction: string;
    corrections?: string;
    new_mechanics?: string;
  }) => postJson<{ section: string }>("/api/design-log", payload),
};

/** The anchor kit a design stage produces, used by the line strip + mirror-down. */
export interface StageFacts {
  types?: string[];
  stats?: Record<string, number>;
  abilities?: AbilitySlots;
}
