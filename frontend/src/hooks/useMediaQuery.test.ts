/* The compact-shell threshold is one decision expressed in two languages — this
   constant and the media block in device-frame.css. When they drift, the CSS
   collapses the rail while the markup still fills it, and the contents spill
   out over the page. This pins the constant against the stylesheet. */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { COMPACT_SHELL_QUERY } from "./useMediaQuery";

describe("COMPACT_SHELL_QUERY", () => {
  it("matches the compact media block in device-frame.css", () => {
    const css = readFileSync(
      new URL("../components/device-frame.css", import.meta.url),
      "utf8",
    );
    expect(css).toContain(`@media ${COMPACT_SHELL_QUERY} {`);
  });

  it("covers a landscape handheld that clears both desktop thresholds", () => {
    // 1024x640 with a coarse pointer: not short enough, not narrow enough.
    expect(COMPACT_SHELL_QUERY).toContain("pointer: coarse");
  });
});
