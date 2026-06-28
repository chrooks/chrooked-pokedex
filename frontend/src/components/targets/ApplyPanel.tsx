/* The preview / apply workspace for one selected Target.

   Preview (safe): runs the real applier on the fork and reverts it. On success
   it shows the report counts.

   The "view this target's dex backdrop" affordance is always available for the
   selected target — the backdrop read path (target ⊕ Ruleset) has no clean-tree
   requirement, so it must not be gated behind a successful Preview. Gating it on
   Preview trapped the user after a real Apply: the Apply dirties the tree, which
   then 409s Preview (which has no Force), leaving no door to the backdrop.

   Apply (destructive, ac11): a deliberate two-step. The bare Apply button arms a
   confirm step; only the explicit confirm fires the write. A dirty tree comes
   back 409 and renders a designed Error State with a Force toggle — Apply will
   not proceed until Force is on, and the confirm copy stays honest about
   overriding the safety check. */

import { useState } from "react";
import { api, ApiError } from "../../api";
import type { ApplyReportSummary, Target } from "../../types";
import { isDirtyTreeStatus } from "../../lib/targets";
import { ApplyReportView } from "./ApplyReportView";
import { EngineVersionReadout } from "./EngineVersionReadout";

type Props = {
  target: Target;
  /** Switch the dex to this target's backdrop after a successful preview. */
  onViewBackdrop: (targetId: string) => void;
};

type RunState =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "report"; mode: "preview" | "apply"; report: ApplyReportSummary }
  | { kind: "error"; status: number | null; message: string };

export function ApplyPanel({ target, onViewBackdrop }: Props) {
  const [run, setRun] = useState<RunState>({ kind: "idle" });
  const [confirming, setConfirming] = useState(false);
  const [force, setForce] = useState(false);

  const busy = run.kind === "running";
  const dirty = run.kind === "error" && isDirtyTreeStatus(run.status);

  async function doPreview() {
    setConfirming(false);
    setRun({ kind: "running" });
    try {
      const report = await api.previewTarget(target.id);
      setRun({ kind: "report", mode: "preview", report });
    } catch (caught: unknown) {
      setRun(errorState(caught));
    }
  }

  async function doApply() {
    setRun({ kind: "running" });
    try {
      const report = await api.applyTarget(target.id, force);
      setConfirming(false);
      setRun({ kind: "report", mode: "apply", report });
    } catch (caught: unknown) {
      setRun(errorState(caught));
    }
  }

  // The destructive path is gated: a dirty tree needs Force on before confirm.
  const confirmDisabled = busy || (dirty && !force);

  return (
    <div className="apply-panel" id="apply-panel">
      <div className="apply-panel__head">
        <div>
          <h2 className="apply-panel__title">{target.label}</h2>
          <p className="apply-panel__path mono">{target.path}</p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "var(--space-1)" }}>
          <span className="apply-panel__engine mono">{target.engine}</span>
          <span id="target-version-badge">
            <EngineVersionReadout id={target.id} engine={target.engine} />
          </span>
        </div>
      </div>

      <div className="apply-panel__actions">
        <button
          type="button"
          id="target-preview-button"
          className="btn btn--primary"
          disabled={busy}
          onClick={() => void doPreview()}
        >
          {busy ? "Running…" : "Preview"}
        </button>

        {/* Backdrop is a read-only fork ⊕ Ruleset view — no Preview/clean tree
            needed, so it's always available, not gated behind a preview run. */}
        <button
          type="button"
          id="target-backdrop-button-direct"
          className="btn"
          disabled={busy}
          onClick={() => onViewBackdrop(target.id)}
        >
          View dex backdrop
        </button>

        {!confirming ? (
          <button
            type="button"
            id="apply-arm-button"
            className="btn btn--danger apply-panel__arm"
            disabled={busy}
            onClick={() => setConfirming(true)}
          >
            Apply…
          </button>
        ) : null}

        <button
          type="button"
          id="target-backdrop-button"
          className="btn apply-panel__backdrop-btn"
          disabled={busy}
          onClick={() => onViewBackdrop(target.id)}
        >
          View dex backdrop →
        </button>

        {confirming ? (
          <div className="apply-confirm" id="apply-confirm" role="group" aria-label="Confirm apply">
            <span className="apply-confirm__warn">
              This writes <strong>{target.label}</strong> on disk. This cannot be undone.
            </span>
            <div className="apply-confirm__buttons">
              <button
                type="button"
                className="btn"
                disabled={busy}
                onClick={() => setConfirming(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                id="apply-confirm-button"
                className="btn btn--danger-solid"
                disabled={confirmDisabled}
                onClick={() => void doApply()}
              >
                {dirty
                  ? force
                    ? "Force apply anyway"
                    : "Apply blocked — tree is dirty"
                  : "Yes, apply"}
              </button>
            </div>
          </div>
        ) : null}
      </div>

      {dirty && (
        <div
          className="apply-error"
          id="apply-dirty-error"
          role="alert"
        >
          <div className="apply-error__badge mono">409</div>
          <div className="apply-error__body">
            <p className="apply-error__title">The target's git tree is dirty</p>
            <p className="apply-error__detail">{run.message}</p>
            <label className="apply-error__force" htmlFor="apply-force-toggle">
              <input
                id="apply-force-toggle"
                type="checkbox"
                checked={force}
                onChange={(event) => setForce(event.target.checked)}
              />
              <span className="apply-error__force-text">
                <strong>Force</strong> — override the dirty-tree safety check and
                apply over uncommitted changes.
              </span>
            </label>
          </div>
        </div>
      )}

      {run.kind === "error" && !dirty && (
        <div className="apply-error apply-error--plain" id="apply-error" role="alert">
          <div className="apply-error__badge mono">{run.status ?? "ERR"}</div>
          <div className="apply-error__body">
            <p className="apply-error__title">Run failed</p>
            <p className="apply-error__detail">{run.message}</p>
          </div>
        </div>
      )}

      {run.kind === "report" && (
        <ApplyReportView report={run.report} mode={run.mode} />
      )}
    </div>
  );
}

function errorState(caught: unknown): RunState {
  if (caught instanceof ApiError) {
    return { kind: "error", status: caught.status, message: caught.message };
  }
  return {
    kind: "error",
    status: null,
    message: caught instanceof Error ? caught.message : "Unexpected error",
  };
}
