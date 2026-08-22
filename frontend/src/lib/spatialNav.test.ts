/**
 * Spatial focus movement — the D-pad's job.
 *
 * Tests the pure geometry (`pickInDirection`); the DOM wrapper around it is
 * thin plumbing. The rule that matters on a real grid is the across-axis
 * penalty: pressing Down must land one ROW below, never on whichever
 * neighbouring-column cell happens to be nearest as the crow flies.
 */

import { describe, expect, test } from "vitest";
import { pickInDirection, type Box } from "./spatialNav";

const CELL = 100;
const COLUMNS = 4;

/** `count` boxes laid out as a 4-column grid of 100x100 cells. */
function grid(count: number): Box[] {
  return Array.from({ length: count }, (_, i) => ({
    left: (i % COLUMNS) * CELL,
    top: Math.floor(i / COLUMNS) * CELL,
    width: CELL,
    height: CELL,
  }));
}

/** Pick from a grid, treating `fromIndex` as the current cell (excluded from
    the candidate pool, exactly as focusInDirection does). */
function step(cells: Box[], fromIndex: number, direction: Parameters<typeof pickInDirection>[2]) {
  const others = cells.filter((_, i) => i !== fromIndex);
  const picked = pickInDirection(cells[fromIndex], others, direction);
  if (picked === null) return null;
  // Map back to the original index so assertions read in grid terms.
  return cells.indexOf(others[picked]);
}

describe("pickInDirection", () => {
  test("right moves one cell along the row", () => {
    expect(step(grid(8), 0, "right")).toBe(1);
  });

  test("left moves back along the row", () => {
    expect(step(grid(8), 2, "left")).toBe(1);
  });

  test("down lands one full row below, not on a diagonal neighbour", () => {
    // cell-5 sits directly below cell-1. cell-4 and cell-6 are diagonal and
    // only slightly further as the crow flies; the penalty must rule them out.
    expect(step(grid(8), 1, "down")).toBe(5);
  });

  test("up returns to the cell directly above", () => {
    expect(step(grid(8), 6, "up")).toBe(2);
  });

  test("returns null at the right edge of a single row", () => {
    expect(step(grid(4), 3, "right")).toBeNull();
  });

  test("returns null when moving up from the top row", () => {
    expect(step(grid(8), 1, "up")).toBeNull();
  });

  test("down from the last row has nowhere to go", () => {
    expect(step(grid(8), 6, "down")).toBeNull();
  });

  test("wrapping is NOT implied — right from the row end does not jump rows", () => {
    // cell-3 ends row 0; cell-4 starts row 1 and is far to the LEFT, so it must
    // not be treated as "to the right". A wrap here would feel like teleporting.
    expect(step(grid(8), 3, "right")).toBeNull();
  });

  test("prefers the nearer of two candidates in the same direction", () => {
    const boxes: Box[] = [
      { left: 0, top: 0, width: 10, height: 10 },
      { left: 50, top: 0, width: 10, height: 10 },
      { left: 500, top: 0, width: 10, height: 10 },
    ];
    expect(step(boxes, 0, "right")).toBe(1);
  });

  test("an empty candidate pool yields null", () => {
    expect(pickInDirection({ left: 0, top: 0, width: 10, height: 10 }, [], "down")).toBeNull();
  });

  test("a candidate at the exact same centre is not a move", () => {
    const here: Box = { left: 0, top: 0, width: 10, height: 10 };
    expect(pickInDirection(here, [{ ...here }], "right")).toBeNull();
  });

  test("ragged rows still resolve down to the column-aligned cell", () => {
    // A last row with two cells: down from cell-1 must reach the one beneath it.
    const boxes = grid(4).concat([
      { left: 0, top: CELL, width: CELL, height: CELL },
      { left: CELL, top: CELL, width: CELL, height: CELL },
    ]);
    expect(step(boxes, 1, "down")).toBe(5);
  });
});
