/* A registered target's detail card in the Targets tab. The tab is now
   registration + management only: preview / apply / the report moved to the
   header switcher and the PatchDrawer (the patch loop's high-hierarchy home).

   The one action here activates this target — sets it as the dex backdrop and
   jumps to the Dex — after which the header offers Preview / Apply for it. */

import type { Target } from "../../types";
import { EngineVersionReadout } from "./EngineVersionReadout";

type Props = {
  target: Target;
  /** Activate this target (set the backdrop) and show it on the Dex. */
  onViewBackdrop: (targetId: string) => void;
};

export function TargetDetail({ target, onViewBackdrop }: Props) {
  return (
    <div className="apply-panel" id="apply-panel">
      <div className="apply-panel__head">
        <div>
          <h2 className="apply-panel__title">{target.label}</h2>
          <p className="apply-panel__path mono">{target.path}</p>
        </div>
        <div className="apply-panel__head-meta">
          <span className="apply-panel__engine mono">{target.engine}</span>
          <span id="target-version-badge">
            <EngineVersionReadout id={target.id} engine={target.engine} />
          </span>
        </div>
      </div>

      <p className="apply-panel__hint">
        Set this as the active target to Preview or Apply from the header.
      </p>

      <div className="apply-panel__actions">
        <button
          type="button"
          id="target-backdrop-button"
          className="btn btn--primary"
          onClick={() => onViewBackdrop(target.id)}
        >
          View on dex →
        </button>
      </div>
    </div>
  );
}
