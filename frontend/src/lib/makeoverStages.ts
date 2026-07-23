/* The Makeover Workbench stage progression, as pure functions (no React, no DOM)
   so the à la carte picker, the propose → tweak → LOCK IN heartbeat, and the
   resume-mid-line derivation are unit-tested without a browser.

   À la carte (ac8): the flow is not a fixed pipeline. Each design stage is either
   SELECTED (worked this session) or KEEP (skipped untouched). The active stage is
   the first selected stage not yet locked this session. With ZERO stages selected
   the journey is mirror-only: a single MIRROR step copies the final evo's current
   kit down to its pre-evos, then the tail runs. Smart defaults: an untouched
   species selects all five design stages; a partially-edited one selects only the
   stages that aren't already in the Ruleset (resume-derived). */

import type { OverridableField } from "../types";

/** The five design stages, in heartbeat order. */
export type DesignStage = "direction" | "typing" | "stats" | "abilities" | "learnset";
/** The automatic tail, streamed into the rail after the last design lock. */
export type AutoStage = "apply" | "proof" | "log";
/** Every workbench stage: the design stages, the standalone MIRROR step (the
    mirror-only journey), the auto tail, then the terminal `done`. */
export type Stage = DesignStage | "mirror" | AutoStage | "done";

export const DESIGN_STAGES: readonly DesignStage[] = [
  "direction",
  "typing",
  "stats",
  "abilities",
  "learnset",
];
export const AUTO_STAGES: readonly AutoStage[] = ["apply", "proof", "log"];
export const ALL_STAGES: readonly Stage[] = [
  ...DESIGN_STAGES,
  "mirror",
  ...AUTO_STAGES,
  "done",
];

const ORDER: Record<Stage, number> = {
  direction: 0,
  typing: 1,
  stats: 2,
  abilities: 3,
  learnset: 4,
  mirror: 5,
  apply: 6,
  proof: 7,
  log: 8,
  done: 9,
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

/** Which design stages already exist in the Ruleset, derived from the species'
    overridden fields. `types` implies BOTH typing and its direction. */
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

/** The smart-default stage selection: all five for an untouched species; only the
    stages NOT already in the Ruleset for a partially-edited one (resume-derived).
    A fully-made-over species defaults to an empty selection → the mirror-only
    journey (nothing left to design; just copy the kit down). */
export function defaultSelected(
  overriddenFields: readonly OverridableField[],
): Set<DesignStage> {
  const locked = lockedFromFields(overriddenFields);
  if (locked.size === 0) return new Set(DESIGN_STAGES);
  return new Set(DESIGN_STAGES.filter((stage) => !locked.has(stage)));
}

/** A facet-derived summary for the design-log line when the run had no picked
    direction (ac6): a direction-less à la carte run (learnset-only, mirror-only)
    still logs *why* by naming the facets it touched. */
export function facetSummary(selected: ReadonlySet<DesignStage>): string {
  const worked = DESIGN_STAGES.filter((s) => s !== "direction" && selected.has(s));
  if (worked.length === 0) return "mirror-only: current kit onto pre-evos";
  if (worked.length === 1) return `${worked[0]}-only repass`;
  return `${worked.join(" + ")} repass`;
}

/** Toggle a stage in/out of the selection (immutable). KEEP ⇄ selected. */
export function toggleSelected(
  selected: ReadonlySet<DesignStage>,
  stage: DesignStage,
): Set<DesignStage> {
  const next = new Set(selected);
  if (next.has(stage)) next.delete(stage);
  else next.add(stage);
  return next;
}

/** The active stage: the first SELECTED design stage not yet locked this session,
    in heartbeat order. With nothing selected, the mirror-only journey — `mirror`
    until it is done, then the tail (`apply`). Once every selected stage is locked,
    the tail. */
export function firstUnlocked(
  selected: ReadonlySet<DesignStage>,
  sessionLocked: ReadonlySet<Stage>,
): Stage {
  for (const stage of DESIGN_STAGES) {
    if (selected.has(stage) && !sessionLocked.has(stage)) return stage;
  }
  if (selected.size === 0 && !sessionLocked.has("mirror")) return "mirror";
  return "apply";
}

/** Whether the rail should let the author jump to `stage`: a stage locked this
    session (revisit), the active stage itself, or an auto/mirror stage at or
    behind the active frontier. A queued-but-not-yet-active design stage is not
    navigable (stages are worked in order). */
export function canNavigate(
  stage: Stage,
  _selected: ReadonlySet<DesignStage>,
  sessionLocked: ReadonlySet<Stage>,
  active: Stage,
): boolean {
  if (stage === active) return true;
  if (sessionLocked.has(stage)) return true;
  if (isDesignStage(stage)) return false;
  return stageIndex(stage) <= stageIndex(active);
}

/** Resolve the active stage: honor the URL's stage when it is reachable given the
    selection + this session's locks, else fall back to the frontier. Clamps a
    stale/hand-typed URL that points ahead of the work done or at a KEPT stage. */
export function resolveActiveStage(
  urlStage: Stage | null,
  selected: ReadonlySet<DesignStage>,
  sessionLocked: ReadonlySet<Stage>,
): Stage {
  const frontier = firstUnlocked(selected, sessionLocked);
  if (urlStage === null) return frontier;
  if (stageIndex(urlStage) > stageIndex(frontier)) return frontier;
  if (isDesignStage(urlStage) && !selected.has(urlStage)) return frontier;
  return urlStage;
}
