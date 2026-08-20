/* Maps a stage's internal phase onto the parked-makeover dock's LED vocabulary
   (the AutoTail's: pulse = busy, amber = done/ready, chrome = error). "Ready"
   means a proposal is sitting un-locked — the light that says "open me". */

import type { StagePhase } from "../components/makeover/useMakeoverStage";

export type MakeoverActivity = "idle" | "proposing" | "ready" | "error";

export function activityOf(phase: StagePhase): MakeoverActivity {
  switch (phase) {
    case "proposing":
      return "proposing";
    case "proposed":
      return "ready";
    case "error":
      return "error";
    default:
      // "propose" (nothing asked yet) and "locking" (write in flight, resolves
      // into a stage advance) both read as quiet on the dock.
      return "idle";
  }
}

/** The LED state spelled out for aria-labels/titles — never color-alone. */
export function activityLabel(activity: MakeoverActivity): string | null {
  switch (activity) {
    case "proposing":
      return "proposing…";
    case "ready":
      return "proposal ready";
    case "error":
      return "proposal failed";
    default:
      return null;
  }
}
