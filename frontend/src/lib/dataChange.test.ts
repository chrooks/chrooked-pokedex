import { describe, expect, it } from "vitest";
import { emitDataChange, onDataChange } from "./dataChange";

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
