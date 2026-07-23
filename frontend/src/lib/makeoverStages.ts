/* The Makeover Workbench stage progression, as pure functions (no React, no DOM)
   so the propose → tweak → LOCK IN heartbeat and the resume-mid-line derivation
   are unit-tested without a browser.

   The Ruleset is the source of truth for progression (matches the chat makeover's
   "check the current Override before proposing"): a design stage is LOCKED once
   its field exists on the species' Override, so a reload or a resume lands on the
   first unlocked stage. The direction stage has no field of its own — it is locked
   once typing is (a chosen typing implies a chosen direction). */

import type { OverridableField } from "../types";

/** The five design stages, in heartbeat order. */
export type DesignStage = "direction" | "typing" | "stats" | "abilities" | "learnset";
/** The automatic tail, streamed into the rail after the last design lock. */
export type AutoStage = "apply" | "proof" | "log";
/** Every workbench stage, plus the terminal `done`. */
export type Stage = DesignStage | AutoStage | "done";

export const DESIGN_STAGES: readonly DesignStage[] = [
  "direction",
  "typing",
  "stats",
  "abilities",
  "learnset",
];
export const AUTO_STAGES: readonly AutoStage[] = ["apply", "proof", "log"];
export const ALL_STAGES: readonly Stage[] = [...DESIGN_STAGES, ...AUTO_STAGES, "done"];

const ORDER: Record<Stage, number> = {
  direction: 0,
  typing: 1,
  stats: 2,
  abilities: 3,
  learnset: 4,
  apply: 5,
  proof: 6,
  log: 7,
  done: 8,
};

/** The stage's position in the flow (for gating and rail rendering). */
export function stageIndex(stage: Stage): number {
  return ORDER[stage];
}

export function isDesignStage(stage: Stage): stage is DesignStage {
  return (DESIGN_STAGES as readonly string[]).includes(stage);
}

export function isAutoStage(stage: Stage): stage is AutoStage {
  return (AUTO_STAGES as readonly string[]).includes(stage);
}

/** Which design stages are already locked, derived from the species' overridden
    fields. `types` locks BOTH typing and its implied direction. */
export function lockedFromFields(
  overriddenFields: readonly OverridableField[],
): Set<DesignStage> {
  const locked = new Set<DesignStage>();
  const has = (f: OverridableField) => overriddenFields.includes(f);
  if (has("types")) {
    locked.add("direction");
    locked.add("typing");
  }
  if (has("stats")) locked.add("stats");
  if (has("abilities")) locked.add("abilities");
  if (has("learnset")) locked.add("learnset");
  return locked;
}

/** The first design stage not yet locked, in heartbeat order — or `apply` (the
    head of the auto tail) once every design stage is locked. Resume lands here. */
export function firstUnlocked(locked: ReadonlySet<DesignStage>): Stage {
  for (const stage of DESIGN_STAGES) {
    if (!locked.has(stage)) return stage;
  }
  return "apply";
}

/** Whether `stage` may be locked now: every earlier design stage must already be
    locked (lock gating — you cannot lock typing before direction is chosen). */
export function canLock(
  stage: DesignStage,
  locked: ReadonlySet<DesignStage>,
): boolean {
  for (const earlier of DESIGN_STAGES) {
    if (earlier === stage) return true;
    if (!locked.has(earlier)) return false;
  }
  return true;
}

/** Whether the rail should let the author navigate to `stage`: any locked design
    stage, the active stage, and any already-reached auto stage. A design stage
    ahead of the frontier is disabled (you cannot skip work). */
export function canNavigate(
  stage: Stage,
  locked: ReadonlySet<DesignStage>,
  active: Stage,
): boolean {
  if (stage === active) return true;
  if (isDesignStage(stage)) return locked.has(stage) || stage === firstUnlocked(locked);
  // Auto stages are reachable only once they are at or before the active stage.
  return stageIndex(stage) <= stageIndex(active);
}

/** The design stage locked AFTER `stage` — the next stop for the flow. `learnset`
    (the last design stage) advances into the auto tail at `apply`. */
export function nextStage(stage: Stage): Stage {
  const idx = ALL_STAGES.indexOf(stage);
  if (idx < 0 || idx === ALL_STAGES.length - 1) return "done";
  return ALL_STAGES[idx + 1];
}

/** The stage before `stage`, for the Esc/back path. Never past `direction`. */
export function prevStage(stage: Stage): Stage {
  const idx = ALL_STAGES.indexOf(stage);
  if (idx <= 0) return "direction";
  return ALL_STAGES[idx - 1];
}

/** Resolve the active stage: the URL's stage when it is valid AND reachable given
    the locked set, else the first unlocked stage. Keeps a stale/hand-typed URL
    from stranding the workbench ahead of the work actually done. */
export function resolveActiveStage(
  urlStage: Stage | null,
  locked: ReadonlySet<DesignStage>,
): Stage {
  const frontier = firstUnlocked(locked);
  if (urlStage === null) return frontier;
  // A design stage past the frontier is not yet reachable — clamp to the frontier.
  if (isDesignStage(urlStage) && stageIndex(urlStage) > stageIndex(frontier)) {
    return frontier;
  }
  return urlStage;
}
