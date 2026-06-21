/* ac1/ac2/ac3/ac5 (logic) — the proposal phase machine transitions.

   Pure reducer, so the whole flow (idle → input → loading → proposed →
   applying → applied, plus the error edges) is provable without a DOM. */

import { describe, it, expect } from "vitest";
import {
  initialState,
  sectionBody,
  suggestReducer,
  type SuggestState,
} from "./suggestMachine";

interface D {
  v: number;
}

function start(): SuggestState<D> {
  return initialState<D>();
}

describe("suggest phase machine", () => {
  it("starts idle with no draft (ac1: only the affordance shows)", () => {
    const s = start();
    expect(s.phase).toBe("idle");
    expect(s.draft).toBeNull();
  });

  it("open reveals the input (Progressive Disclosure)", () => {
    const s = suggestReducer(start(), { type: "open" });
    expect(s.phase).toBe("input");
  });

  it("submit from input goes loading (ac2: spinner state)", () => {
    let s = suggestReducer(start(), { type: "open" });
    s = suggestReducer(s, { type: "setDirection", direction: "special" });
    s = suggestReducer(s, { type: "submit" });
    expect(s.phase).toBe("loading");
    expect(s.direction).toBe("special");
  });

  it("submit is a no-op from idle (can't fire a call with no input)", () => {
    const s = suggestReducer(start(), { type: "submit" });
    expect(s.phase).toBe("idle");
  });

  it("proposed carries draft + rationale + alternatives (ac3)", () => {
    let s = suggestReducer(start(), { type: "open" });
    s = suggestReducer(s, { type: "submit" });
    s = suggestReducer(s, {
      type: "proposed",
      draft: { v: 1 },
      rationale: { primary: "why" },
      alternatives: [{ value: "Alt", rationale: "runner-up" }],
    });
    expect(s.phase).toBe("proposed");
    expect(s.draft).toEqual({ v: 1 });
    expect(s.rationale.primary).toBe("why");
    expect(s.alternatives).toHaveLength(1);
  });

  it("a failed suggest carries the message + kind, no draft written", () => {
    let s = suggestReducer(start(), { type: "open" });
    s = suggestReducer(s, { type: "submit" });
    s = suggestReducer(s, {
      type: "failed",
      kind: "suggest",
      message: "no key",
    });
    expect(s.phase).toBe("error");
    expect(s.error).toBe("no key");
    expect(s.errorKind).toBe("suggest");
    expect(s.draft).toBeNull();
  });

  it("editDraft replaces the working draft (ac4: curate before Apply)", () => {
    let s = suggestReducer(start(), { type: "open" });
    s = suggestReducer(s, { type: "submit" });
    s = suggestReducer(s, {
      type: "proposed",
      draft: { v: 1 },
      rationale: {},
      alternatives: [],
    });
    s = suggestReducer(s, { type: "editDraft", draft: { v: 2 } });
    expect(s.draft).toEqual({ v: 2 });
  });

  it("editDraft is a no-op before any proposal exists", () => {
    const s = suggestReducer(start(), { type: "editDraft", draft: { v: 9 } });
    expect(s.draft).toBeNull();
  });

  it("apply requires a proposed draft, then resolves to applied (ac5)", () => {
    let s = suggestReducer(start(), { type: "open" });
    s = suggestReducer(s, { type: "submit" });
    s = suggestReducer(s, {
      type: "proposed",
      draft: { v: 1 },
      rationale: {},
      alternatives: [],
    });
    s = suggestReducer(s, { type: "apply" });
    expect(s.phase).toBe("applying");
    s = suggestReducer(s, { type: "applied" });
    expect(s.phase).toBe("applied");
  });

  it("an Apply failure (422) goes to error, draft preserved (nothing lost)", () => {
    let s = suggestReducer(start(), { type: "open" });
    s = suggestReducer(s, { type: "submit" });
    s = suggestReducer(s, {
      type: "proposed",
      draft: { v: 1 },
      rationale: {},
      alternatives: [],
    });
    s = suggestReducer(s, { type: "apply" });
    s = suggestReducer(s, {
      type: "failed",
      kind: "apply",
      message: "loader rejected",
    });
    expect(s.phase).toBe("error");
    expect(s.errorKind).toBe("apply");
    expect(s.draft).toEqual({ v: 1 });
  });

  it("reset returns to a clean idle", () => {
    let s = suggestReducer(start(), { type: "open" });
    s = suggestReducer(s, { type: "submit" });
    s = suggestReducer(s, {
      type: "proposed",
      draft: { v: 1 },
      rationale: {},
      alternatives: [],
    });
    s = suggestReducer(s, { type: "reset" });
    expect(s).toEqual(initialState<D>());
  });
});

describe("sectionBody — read-only vs columns are mutually exclusive (ac1)", () => {
  it("shows the read-only body (not columns) while no draft exists", () => {
    // idle and input both precede a draft → the read-only list is the body, so
    // it is NOT duplicated alongside a current │ proposed grid.
    expect(sectionBody(start())).toBe("readonly");
    const input = suggestReducer(start(), { type: "open" });
    expect(sectionBody(input)).toBe("readonly");
  });

  it("swaps to the columns grid (hiding the read-only body) once a draft exists", () => {
    let s = suggestReducer(start(), { type: "open" });
    s = suggestReducer(s, { type: "submit" });
    s = suggestReducer(s, {
      type: "proposed",
      draft: { v: 1 },
      rationale: {},
      alternatives: [],
    });
    // BOUNCE 1 guard: with a draft, the renderer's grid IS the current column;
    // the read-only list must not render a third time.
    expect(sectionBody(s)).toBe("columns");
  });

  it("returns to the read-only body after a reset (no lingering columns)", () => {
    let s = suggestReducer(start(), { type: "open" });
    s = suggestReducer(s, { type: "submit" });
    s = suggestReducer(s, {
      type: "proposed",
      draft: { v: 1 },
      rationale: {},
      alternatives: [],
    });
    s = suggestReducer(s, { type: "reset" });
    expect(sectionBody(s)).toBe("readonly");
  });
});
