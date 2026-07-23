/* URL persistence for the Makeover Workbench: the anchor species + the active
   stage, so a reload restores the workbench exactly and Back returns to the dex
   as it was. Pure encode/decode over URLSearchParams, unit-tested; useUrlState
   owns wiring these two params alongside the rest of the view state. */

import { ALL_STAGES, type Stage } from "./makeoverStages";

const SPECIES_PARAM = "mk";
const STAGE_PARAM = "mkstage";

const VALID_STAGES = new Set<string>(ALL_STAGES);

export interface MakeoverUrlState {
  /** The anchor species' chrooked_id, or null when the workbench is closed. */
  species: string | null;
  /** The active stage, or null to let the workbench derive it from the Ruleset. */
  stage: Stage | null;
}

export function isValidStage(value: string | null | undefined): value is Stage {
  return value != null && VALID_STAGES.has(value);
}

/** Read the makeover state out of a URLSearchParams. A stage without a species is
    ignored (there is nothing to stage), keeping the URL self-consistent. */
export function decodeMakeover(params: URLSearchParams): MakeoverUrlState {
  const species = params.get(SPECIES_PARAM);
  if (!species) return { species: null, stage: null };
  const rawStage = params.get(STAGE_PARAM);
  return { species, stage: isValidStage(rawStage) ? rawStage : null };
}

/** Write the makeover state into a URLSearchParams (mutating it): both params are
    cleared first so a closed workbench leaves no trace, then set when open. */
export function encodeMakeover(
  params: URLSearchParams,
  value: MakeoverUrlState,
): void {
  params.delete(SPECIES_PARAM);
  params.delete(STAGE_PARAM);
  if (!value.species) return;
  params.set(SPECIES_PARAM, value.species);
  if (value.stage) params.set(STAGE_PARAM, value.stage);
}

/** The param names this codec owns, so useUrlState can clear them before a rewrite
    without hardcoding the strings. */
export const MAKEOVER_PARAMS = [SPECIES_PARAM, STAGE_PARAM] as const;
