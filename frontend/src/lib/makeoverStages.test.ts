import { describe, expect, it } from "vitest";
import {
  canLock,
  canNavigate,
  firstUnlocked,
  lockedFromFields,
  nextStage,
  prevStage,
  resolveActiveStage,
  type DesignStage,
} from "./makeoverStages";

function locked(...stages: DesignStage[]): Set<DesignStage> {
  return new Set(stages);
}

describe("lockedFromFields", () => {
  it("locks direction and typing together when types are overridden", () => {
    const set = lockedFromFields(["types"]);
    expect(set.has("direction")).toBe(true);
    expect(set.has("typing")).toBe(true);
    expect(set.has("stats")).toBe(false);
  });

  it("locks each design stage from its own field", () => {
    const set = lockedFromFields(["types", "stats", "abilities", "learnset"]);
    expect([...set].sort()).toEqual(["abilities", "direction", "learnset", "stats", "typing"]);
  });

  it("ignores evolution (not a workbench stage)", () => {
    expect(lockedFromFields(["evolution"]).size).toBe(0);
  });
});

describe("firstUnlocked — resume lands on the first unlocked stage", () => {
  it("is direction on a fresh species", () => {
    expect(firstUnlocked(locked())).toBe("direction");
  });

  it("skips locked stages", () => {
    expect(firstUnlocked(locked("direction", "typing"))).toBe("stats");
  });

  it("is the auto tail (apply) once every design stage is locked", () => {
    expect(firstUnlocked(locked("direction", "typing", "stats", "abilities", "learnset"))).toBe(
      "apply",
    );
  });
});

describe("canLock — lock gating", () => {
  it("allows direction first", () => {
    expect(canLock("direction", locked())).toBe(true);
  });

  it("blocks stats before typing is locked", () => {
    expect(canLock("stats", locked("direction"))).toBe(false);
  });

  it("allows learnset only after every earlier design stage locks", () => {
    expect(canLock("learnset", locked("direction", "typing", "stats", "abilities"))).toBe(true);
    expect(canLock("learnset", locked("direction", "typing", "stats"))).toBe(false);
  });
});

describe("canNavigate", () => {
  it("lets the author revisit a locked stage", () => {
    expect(canNavigate("typing", locked("direction", "typing"), "stats")).toBe(true);
  });

  it("blocks jumping to a design stage past the frontier", () => {
    expect(canNavigate("learnset", locked("direction"), "typing")).toBe(false);
  });
});

describe("nextStage / prevStage", () => {
  it("advances learnset into the auto tail", () => {
    expect(nextStage("learnset")).toBe("apply");
  });
  it("walks back but never past direction", () => {
    expect(prevStage("typing")).toBe("direction");
    expect(prevStage("direction")).toBe("direction");
  });
});

describe("resolveActiveStage", () => {
  it("uses the frontier when the URL has no stage", () => {
    expect(resolveActiveStage(null, locked("direction", "typing"))).toBe("stats");
  });

  it("clamps a stale URL stage that is ahead of the work done", () => {
    // URL says learnset but only direction is locked → clamp to the frontier.
    expect(resolveActiveStage("learnset", locked("direction"))).toBe("typing");
  });

  it("honors a URL stage at or behind the frontier", () => {
    expect(resolveActiveStage("direction", locked("direction", "typing"))).toBe("direction");
  });
});
