import { describe, expect, it } from "vitest";
import {
  DESIGN_STAGES,
  canNavigate,
  defaultSelected,
  facetSummary,
  firstUnlocked,
  lockedFromFields,
  resolveActiveStage,
  toggleSelected,
  type DesignStage,
  type Stage,
} from "./makeoverStages";

function sel(...stages: DesignStage[]): Set<DesignStage> {
  return new Set(stages);
}
function done(...stages: Stage[]): Set<Stage> {
  return new Set(stages);
}
const ALL = sel(...DESIGN_STAGES);

describe("lockedFromFields", () => {
  it("locks direction and typing together when types are overridden", () => {
    const set = lockedFromFields(["types"]);
    expect(set.has("direction")).toBe(true);
    expect(set.has("typing")).toBe(true);
    expect(set.has("stats")).toBe(false);
  });
  it("ignores evolution (not a workbench stage)", () => {
    expect(lockedFromFields(["evolution"]).size).toBe(0);
  });
});

describe("defaultSelected — smart defaults", () => {
  it("selects all five for an untouched species", () => {
    expect([...defaultSelected([])].sort()).toEqual(
      ["abilities", "direction", "learnset", "stats", "typing"],
    );
  });
  it("resume-derives: selects only the stages not already in the Ruleset", () => {
    // types + stats already overridden → typing/direction/stats kept, work the rest.
    expect([...defaultSelected(["types", "stats"])].sort()).toEqual(["abilities", "learnset"]);
  });
  it("a fully made-over species defaults to mirror-only (empty selection)", () => {
    expect(defaultSelected(["types", "stats", "abilities", "learnset"]).size).toBe(0);
  });
});

describe("facetSummary — direction-less design-log line (ac6)", () => {
  it("names a single-facet repass", () => {
    expect(facetSummary(sel("learnset"))).toBe("learnset-only repass");
  });
  it("names a multi-facet repass", () => {
    expect(facetSummary(sel("typing", "stats"))).toBe("typing + stats repass");
  });
  it("describes the mirror-only journey when nothing is selected", () => {
    expect(facetSummary(sel())).toBe("mirror-only: current kit onto pre-evos");
  });
  it("ignores direction (not a written facet)", () => {
    expect(facetSummary(sel("direction", "learnset"))).toBe("learnset-only repass");
  });
});

describe("toggleSelected", () => {
  it("removes a selected stage (→ KEEP) and re-adds it", () => {
    const off = toggleSelected(ALL, "learnset");
    expect(off.has("learnset")).toBe(false);
    expect(toggleSelected(off, "learnset").has("learnset")).toBe(true);
  });
});

describe("firstUnlocked — active stage across journeys", () => {
  it("full journey walks the selected stages in order", () => {
    expect(firstUnlocked(ALL, done())).toBe("direction");
    expect(firstUnlocked(ALL, done("direction", "typing"))).toBe("stats");
  });

  it("learnset-only journey activates learnset, then MIRROR, then the tail", () => {
    const only = sel("learnset");
    expect(firstUnlocked(only, done())).toBe("learnset");
    expect(firstUnlocked(only, done("learnset"))).toBe("mirror");
    expect(firstUnlocked(only, done("learnset", "mirror"))).toBe("apply");
  });

  it("mirror-only journey (nothing selected) runs the mirror step, then the tail", () => {
    expect(firstUnlocked(sel(), done())).toBe("mirror");
    expect(firstUnlocked(sel(), done("mirror"))).toBe("apply");
  });

  it("MIRROR is a standing stop in every journey — after the last design lock", () => {
    expect(firstUnlocked(ALL, done(...DESIGN_STAGES))).toBe("mirror");
    expect(firstUnlocked(sel("typing", "stats"), done("typing", "stats"))).toBe("mirror");
    expect(firstUnlocked(sel("typing", "stats"), done("typing", "stats", "mirror"))).toBe(
      "apply",
    );
  });
});

describe("canNavigate", () => {
  it("lets the author revisit a stage locked this session", () => {
    expect(canNavigate("typing", ALL, done("direction", "typing"), "stats")).toBe(true);
  });
  it("blocks a queued design stage that is not yet active", () => {
    expect(canNavigate("learnset", ALL, done("direction"), "typing")).toBe(false);
  });
  it("does not offer a KEPT (deselected) stage", () => {
    // learnset-only: typing is KEEP, not navigable.
    expect(canNavigate("typing", sel("learnset"), done(), "learnset")).toBe(false);
  });
});

describe("resolveActiveStage", () => {
  it("uses the frontier when the URL has no stage", () => {
    expect(resolveActiveStage(null, ALL, done("direction", "typing"))).toBe("stats");
  });
  it("clamps a URL stage ahead of the work done", () => {
    expect(resolveActiveStage("learnset", ALL, done("direction"))).toBe("typing");
  });
  it("clamps a URL pointing at a KEPT stage back to the frontier", () => {
    // typing is KEEP in a learnset-only journey → clamp to the frontier.
    expect(resolveActiveStage("typing", sel("learnset"), done())).toBe("learnset");
  });
  it("honors a URL stage at or behind the frontier", () => {
    expect(resolveActiveStage("direction", ALL, done("direction", "typing"))).toBe("direction");
  });
  it("resolves the mirror step for a mirror-only journey", () => {
    expect(resolveActiveStage(null, sel(), done())).toBe("mirror");
  });
});
