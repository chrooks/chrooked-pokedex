/* The patch workspace: a right slide-in drawer that previews or applies the
   Ruleset to the ACTIVE target. Opened from the header switcher.

   Preview (safe): runs the real applier on the fork, reverts it, shows the
   report. Apply (destructive, ac11): a two-step — the header opens this drawer
   armed; the explicit confirm fires the write. A dirty tree returns 409 and
   renders the Force Error State; Apply will not proceed until Force is on.

   The drawer mirrors DetailLedger's overlay/aside pattern (scrim + dialog +
   slide-in) so the app has one drawer idiom, not two. */

import { useEffect, useRef, useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faXmark } from "@fortawesome/free-solid-svg-icons";
import { api, ApiError } from "../../api";
import type { ApplyReportSummary, Target } from "../../types";
import { isDirtyTreeStatus } from "../../lib/targets";
import { PokeballSpinner } from "../PokeballSpinner";
import { ApplyReportView } from "./ApplyReportView";
import { ApplyErrorView } from "./ApplyErrorView";
import { EngineVersionReadout } from "./EngineVersionReadout";
import "./patch-drawer.css";

type Mode = "preview" | "apply";

type RunState =
  | { kind: "idle" }
  | { kind: "running"; mode: Mode }
  | { kind: "report"; mode: Mode; report: ApplyReportSummary }
  | { kind: "error"; status: number | null; message: string; detail: unknown };

type Props = {
  target: Target;
  /** Which action opened the drawer: Preview auto-runs; Apply arms the confirm. */
  trigger: Mode;
  onClose: () => void;
  /** Refetch the dex after a real apply so the backdrop reflects new values. */
  onApplied: () => void;
};

export function PatchDrawer({ target, trigger, onClose, onApplied }: Props) {
  const [run, setRun] = useState<RunState>({ kind: "idle" });
  const [confirming, setConfirming] = useState(false);
  const [force, setForce] = useState(false);
  const panelRef = useRef<HTMLElement>(null);
  // Monotonic run token: a settled run only commits its result if it is still
  // the latest one. Guards the StrictMode double-mount and rapid target switches
  // from landing a stale report over a newer run.
  const runIdRef = useRef(0);

  const busy = run.kind === "running";
  const runMode = run.kind === "running" ? run.mode : null;
  const dirty = run.kind === "error" && isDirtyTreeStatus(run.status);

  async function doPreview() {
    setConfirming(false);
    const runId = ++runIdRef.current;
    setRun({ kind: "running", mode: "preview" });
    try {
      const report = await api.previewTarget(target.id);
      if (runId === runIdRef.current) setRun({ kind: "report", mode: "preview", report });
    } catch (caught: unknown) {
      if (runId === runIdRef.current) setRun(errorState(caught));
    }
  }

  async function doApply() {
    const runId = ++runIdRef.current;
    setRun({ kind: "running", mode: "apply" });
    try {
      const report = await api.applyTarget(target.id, force);
      if (runId !== runIdRef.current) return;
      setConfirming(false);
      setRun({ kind: "report", mode: "apply", report });
      onApplied();
    } catch (caught: unknown) {
      if (runId === runIdRef.current) setRun(errorState(caught));
    }
  }

  // The trigger picks the opening action: Preview auto-runs (safe); Apply arms
  // the confirm (destructive — never auto-fire). Re-runs if the target changes
  // while the drawer is open.
  useEffect(() => {
    // Restore focus to the opener (the header Preview/Apply button) on close so
    // the keyboard loop isn't dropped onto <body>.
    const opener = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    if (trigger === "preview") {
      void doPreview();
    } else {
      setConfirming(true);
    }
    return () => opener?.focus?.();
    // doPreview is stable per render for this target; intentionally keyed on the
    // (target, trigger) pair only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target.id, trigger]);

  const confirmDisabled = busy || (dirty && !force);

  return (
    <div className="patch-overlay">
      <button
        type="button"
        className="patch-overlay__scrim"
        aria-label="Close patch panel"
        tabIndex={-1}
        onClick={onClose}
      />
      <aside
        className="patch-drawer"
        id="patch-drawer"
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="patch-drawer-title"
      >
        <header className="patch-drawer__head">
          <div className="patch-drawer__head-row">
            <div className="patch-drawer__id">
              <span className="patch-drawer__eyebrow mono">PATCH TARGET</span>
              <h2 className="patch-drawer__title" id="patch-drawer-title">
                {target.label}
              </h2>
              <p className="patch-drawer__path mono">{target.path}</p>
            </div>
            <button
              type="button"
              className="patch-drawer__close"
              onClick={onClose}
              aria-label="Close (Esc)"
              title="Close (Esc)"
            >
              <FontAwesomeIcon icon={faXmark} aria-hidden="true" />
            </button>
          </div>
          <div className="patch-drawer__meta">
            <span className="patch-drawer__engine mono">{target.engine}</span>
            <EngineVersionReadout id={target.id} engine={target.engine} />
          </div>
        </header>

        <div className="patch-drawer__actions">
          <button
            type="button"
            id="target-preview-button"
            className="btn btn--primary"
            disabled={busy}
            onClick={() => void doPreview()}
          >
            {runMode === "preview" ? "Previewing…" : "Preview"}
          </button>

          {!confirming && (
            <button
              type="button"
              id="apply-arm-button"
              className="btn btn--danger patch-drawer__arm"
              disabled={busy}
              onClick={() => setConfirming(true)}
            >
              Apply…
            </button>
          )}
        </div>

        {confirming && (
          <div
            className="apply-confirm"
            id="apply-confirm"
            role="group"
            aria-label="Confirm apply"
          >
            <span className="apply-confirm__warn">
              This writes <strong>{target.label}</strong> on disk. This cannot be
              undone.
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
                  : runMode === "apply"
                    ? "Applying…"
                    : "Yes, apply"}
              </button>
            </div>
          </div>
        )}

        <div className="patch-drawer__output" aria-live="polite">
        {dirty && run.kind === "error" && (
          <div className="apply-error" id="apply-dirty-error" role="alert">
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
          <ApplyErrorView
            status={run.status}
            message={run.message}
            detail={run.detail}
          />
        )}

        {busy && (
          <div className="patch-drawer__running">
            <PokeballSpinner label={`${runMode ?? "Running"}…`} />
          </div>
        )}

        {run.kind === "report" && (
          <ApplyReportView report={run.report} mode={run.mode} />
        )}
        </div>
      </aside>
    </div>
  );
}

function errorState(caught: unknown): RunState {
  if (caught instanceof ApiError) {
    return {
      kind: "error",
      status: caught.status,
      message: caught.message,
      detail: caught.detail,
    };
  }
  return {
    kind: "error",
    status: null,
    message: caught instanceof Error ? caught.message : "Unexpected error",
    detail: null,
  };
}
