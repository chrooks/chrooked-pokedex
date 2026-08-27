/* Proof harness for the save-state row (#88).
 *
 * Mounts the real SaveStateRow inside the real drawer shell and the real
 * stylesheets, and nothing else. The app's other surfaces need a live backend
 * with a registered Target; this row needs one mocked endpoint, so driving the
 * whole app would only add ways for the proof to fail for unrelated reasons.
 *
 * Playwright fulfils /api/targets/harness/save-status to pick the state. */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { SaveStateRow } from "../src/components/targets/SaveStateRow";
import "../src/styles/tokens.css";
import "../src/styles/global.css";
import "../src/components/editors/editors.css";
import "../src/components/targets/targets.css";
import "../src/components/targets/patch-drawer.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <div className="patch-overlay">
      <aside className="patch-drawer" role="dialog" aria-label="Patch target">
        <header className="patch-drawer__head">
          <div className="patch-drawer__head-row">
            <div className="patch-drawer__id">
              <span className="patch-drawer__eyebrow mono">PATCH TARGET</span>
              <h2 className="patch-drawer__title">Rejuvenation (thor)</h2>
              <p className="patch-drawer__path mono">/data/rejuv</p>
            </div>
          </div>
        </header>
        <SaveStateRow targetId="harness" />
        <div className="patch-drawer__actions">
          <button type="button" className="btn btn--primary">
            Preview
          </button>
          <button type="button" className="btn btn--danger">
            Apply…
          </button>
        </div>
      </aside>
    </div>
  </StrictMode>,
);
