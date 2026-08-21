import { describe, expect, it } from "vitest";
import { placeCard } from "./hoverPlacement";

const viewport = { width: 1200, height: 800 };

describe("placeCard", () => {
  it("places below the anchor when the card fits", () => {
    const pos = placeCard({ top: 100, bottom: 120, left: 300 }, { width: 260, height: 200 }, viewport);
    expect(pos).toEqual({ top: 126, left: 300 });
  });

  it("flips above when the bottom of the viewport is too close", () => {
    const pos = placeCard({ top: 700, bottom: 720, left: 300 }, { width: 260, height: 200 }, viewport);
    expect(pos.top).toBe(700 - 6 - 200);
  });

  it("clamps to the right edge", () => {
    const pos = placeCard({ top: 100, bottom: 120, left: 1100 }, { width: 260, height: 200 }, viewport);
    expect(pos.left).toBe(1200 - 260 - 8);
  });

  it("never leaves the top or left margin", () => {
    const pos = placeCard({ top: 10, bottom: 790, left: 2 }, { width: 260, height: 900 }, viewport);
    expect(pos.top).toBeGreaterThanOrEqual(8);
    expect(pos.left).toBe(8);
  });
});
