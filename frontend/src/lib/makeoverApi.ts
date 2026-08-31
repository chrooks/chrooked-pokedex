/* The makeover-specific API calls, layered over the SAME backend Seams the chat
   skills use (One Seam): the species-suggest endpoints, the apply/read-back
   targets machinery, and the two small makeover routes (rubric, design-log).
   Fetch + error mapping come from api.ts — one ApiError shape everywhere. */

import { getJson, sendJson } from "../api";
import type {
  AbilitySlots,
  AdditionalEffect,
  ApplyReportSummary,
  Behavior,
  LoreMode,
  LoreProvenance,
} from "../types";
import type { LearnsetRubric } from "./learnsetBands";

const postJson = <T,>(path: string, payload?: unknown): Promise<T> =>
  sendJson<T>("POST", path, payload);

/** One lore-grounded makeover direction: a typing + a short role label. */
export interface LoreOption {
  types: string[];
  role: string;
  /** 0-2 pool types that fit what the creature IS — its coverage moves. */
  flavor_types?: string[];
  rationale: string;
}

export interface LoreOptionsResponse {
  draft: { options: LoreOption[] };
  rationale: Record<string, string>;
  /** What the lore lookup did for this call (`{ mode: "off" }` when none ran). */
  lore?: LoreProvenance;
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

/** One proposed distribution target from ability-create. `replaces` is the
    species' real current occupant of that slot (proposal-only, stripped on write). */
export interface AbilityDistributionRow {
  species: string;
  slot: "primary" | "secondary" | "hidden";
  replaces?: string;
  reasoning?: string;
}

/** The ability-create draft: a new owned ability, its engine-neutral behavior stub
    (engine_hints ALWAYS empty — the human's grounding pass), and a distribution
    plan. Mirrors the POST /api/abilities/suggest contract. */
export interface AbilityCreateDraft {
  ability: { chrooked_id: string; name: string; description: string };
  behavior: Behavior;
  distribution: AbilityDistributionRow[];
}

export interface AbilityCreateResponse {
  draft: AbilityCreateDraft;
  rationale: { ability?: string; ai_rating?: string; distribution?: string };
  alternatives: { value: unknown; rationale: string }[];
  warnings?: string[];
  /** What the lore lookup did for this call (`{ mode: "off" }` when none ran). */
  lore?: LoreProvenance;
}

/** The move-create draft: a new owned move plus an optional engine-neutral behavior
    stub (engine_hints ALWAYS empty — the human's grounding pass). Mirrors the
    `POST /api/moves/suggest` CREATE contract (`draft.move` + optional
    `draft.behavior`). Fields the model may omit are optional here. */
export interface MoveCreateDraft {
  move: {
    chrooked_id: string;
    name: string;
    type: string;
    category: "physical" | "special" | "status";
    power?: number | null;
    accuracy?: number | null;
    pp?: number | null;
    priority?: number;
    target?: string;
    flags?: string[];
    effect?: string;
    additional_effects?: AdditionalEffect[];
    description?: string;
  };
  behavior?: Behavior;
}

export interface MoveCreateResponse {
  draft: MoveCreateDraft;
  rationale: { move?: string; edit?: string };
  alternatives: { value: unknown; rationale: string }[];
  warnings?: string[];
  chrooked_id: string;
}

/** One proposed recipient for distributing an EXISTING ability: species
    (chrooked_id) + slot. `replaces` is the species' current occupant of that slot
    (display-only). Mirrors `POST /api/abilities/{id}/distribute`. */
export interface AbilityDistributeRow {
  species: string;
  slot: "primary" | "secondary" | "hidden";
  replaces?: string;
  reasoning?: string;
}

export interface AbilityDistributeResponse {
  rows: AbilityDistributeRow[];
  rationale: string;
  warnings: string[];
}

export const makeoverApi = {
  /** The makeover opening move: 2-3 lore-grounded typing+role directions, on the
      species-suggest typing Seam (`mode: "lore-options"`). À la carte KEPT facets
      (current typing/abilities of facets set to KEEP) constrain the options so a
      kept typing is never changed. */
  loreOptions: (
    id: string,
    opts?: {
      direction?: string;
      keptTypes?: string[];
      keptAbilities?: AbilitySlots;
      /** Researched-lore mode for this call. Omitted or unrecognized = off. */
      lore?: LoreMode;
      /** The backdrop Target this call was launched from — the server's fallback
          join for a Target-original form canon has never heard of. */
      target?: string;
    },
  ) =>
    postJson<LoreOptionsResponse>(
      `/api/species/${encodeURIComponent(id)}/suggest/typing`,
      {
        mode: "lore-options",
        direction: opts?.direction,
        kept_types: opts?.keptTypes,
        kept_abilities: opts?.keptAbilities,
        lore: opts?.lore,
        target: opts?.target,
      },
    ),
  suggestTyping: (id: string, direction?: string, lore?: LoreMode, target?: string) =>
    postJson<TypingProposal>(
      `/api/species/${encodeURIComponent(id)}/suggest/typing`,
      { direction, lore, target },
    ),
  suggestStats: (id: string, direction?: string, target?: string) =>
    postJson<StatsProposal>(
      `/api/species/${encodeURIComponent(id)}/suggest/stats`,
      { direction, target },
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
  /** Drive the existing ability-create Seam: propose a brand-new ability + behavior
      stub + distribution. Writes nothing — the accept path is PUT ability →
      behavior → species ×N through the existing CRUD routes, on confirm.
      `species` is the anchor species' chrooked_id (#79) — omitted on the
      standalone create path, where a `lore` request is a clean no-op. */
  createAbility: (direction: string, species?: string, lore?: LoreMode) =>
    postJson<AbilityCreateResponse>("/api/abilities/suggest", {
      direction,
      species,
      lore,
    }),
  /** Drive the existing move-create Seam: propose a brand-new move (+ optional
      behavior stub). Writes nothing — the accept path is PUT move → behavior
      through the existing CRUD routes, on confirm (mirrors createAbility). */
  createMove: (direction: string) =>
    postJson<MoveCreateResponse>("/api/moves/suggest", { direction, mode: "create" }),
  /** Opt-in AI distribution for an EXISTING ability (the ✦ Suggest gate): propose
      recipient species + slots. Never writes — the accept path is the species CRUD
      through the panel's confirm. The route falls back to the ability's own
      description when `prompt` is omitted. */
  distributeAbility: (
    id: string,
    body: { prompt?: string; rarity?: string; limit?: number },
  ) =>
    postJson<AbilityDistributeResponse>(
      `/api/abilities/${encodeURIComponent(id)}/distribute`,
      body,
    ),
};

/** The anchor kit a design stage produces, used by the line strip + mirror-down. */
export interface StageFacts {
  types?: string[];
  stats?: Record<string, number>;
  abilities?: AbilitySlots;
}
