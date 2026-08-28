/* A failed LOCK IN must keep the author's hand-tuned draft on screen: phase
   returns to "proposed" (draft visible + re-lockable) with the rejected banner.
   Regression for the Wakeupshock incident — a 422 lock parked the stage in
   "error" and the tuned learnset became invisible and unrecoverable. */
import { describe, expect, it } from "vitest";
import { reducer, type State } from "./useMakeoverStage";

const proposed: State<string[]> = {
  phase: "proposed",
  direction: "",
  draft: ["hand-tuned rows"],
  baseline: ["model rows"],
  rationale: {},
  alternatives: [],
  warnings: [],
  error: null,
  errorKind: null,
};

describe("reducer failed-lock recovery", () => {
  it("keeps the draft visible after a rejected lock", () => {
    const locking = reducer(proposed, { type: "locking" });
    const failed = reducer(locking, {
      type: "failed",
      kind: "lock",
      message: "move 'Wakeupshock' does not resolve to a known move.",
    });
    expect(failed.phase).toBe("proposed");
    expect(failed.draft).toEqual(["hand-tuned rows"]);
    expect(failed.error).toContain("Wakeupshock");
    expect(failed.errorKind).toBe("lock");
  });

  it("still lands in error when a propose fails (no draft yet)", () => {
    const empty: State<string[]> = { ...proposed, phase: "proposing", draft: null, baseline: null };
    const failed = reducer(empty, { type: "failed", kind: "propose", message: "503" });
    expect(failed.phase).toBe("error");
  });
});
