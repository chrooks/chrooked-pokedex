import { afterAll, describe, expect, it } from "vitest";

// Node has no window; an EventTarget is all dataChange needs from it.
const fakeWindow = new EventTarget();
Object.assign(globalThis, { window: fakeWindow });
afterAll(() => {
  delete (globalThis as { window?: unknown }).window;
});

const { emitDataChange, onDataChange } = await import("./dataChange");

describe("emitDataChange", () => {
  it("coalesces a burst of emits into one event", async () => {
    let fired = 0;
    const off = onDataChange(() => fired++);
    emitDataChange();
    emitDataChange();
    emitDataChange();
    await Promise.resolve();
    expect(fired).toBe(1);
    off();
  });
});
