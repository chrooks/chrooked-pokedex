/* The automatic tail: once the last design stage locks, apply → proof → log run
   without being asked (the makeover skill's tail, as UI). Apply runs via the
   existing Targets machinery and the Apply Report renders verbatim — blocked
   entries are NAMED, never summarized (ac6). The read-back diff is the proof
   artifact (READ-BACK OK · N/N). The design-log entry is harvested from the
   session's direction + corrections and confirmed on one editable line before it
   appends. Skeletons, no spinners; every backend message surfaced verbatim. */

import { useEffect, useRef, useState } from "react";
import { ApiError } from "../../api";
import type { ApplyReportSummary } from "../../types";
import { makeoverApi, type ReadBackResponse } from "../../lib/makeoverApi";
import { SyncStatus } from "../targets/SyncStatus";

type Sub = "apply" | "proof" | "log" | "done";

interface Props {
  anchorName: string;
  /** The whole line the makeover touched (anchor + pre-evos), for the read-back. */
  changedIds: string[];
  targetId: string | null;
  targetLabel: string | null;
  /** The direction chosen in the direction stage. */
  direction: string;
  /** The corrections harvested from the tweak loops (redirects/edits). */
  corrections: string[];
  onStage: (sub: Sub) => void;
  onDone: () => void;
}

function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Unexpected error";
}

export function AutoTail({
  anchorName,
  changedIds,
  targetId,
  targetLabel,
  direction,
  corrections,
  onStage,
  onDone,
}: Props) {
  const [report, setReport] = useState<ApplyReportSummary | null>(null);
  const [proof, setProof] = useState<ReadBackResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sub, setSub] = useState<Sub>("apply");
  const ranApply = useRef(false);

  // Design-log confirm line (harvested, editable).
  const [logLine, setLogLine] = useState(`${anchorName} line`);
  const [logCorrections, setLogCorrections] = useState(corrections.join("; "));
  const [logDone, setLogDone] = useState<string | null>(null);

  function advance(next: Sub) {
    setSub(next);
    onStage(next);
  }

  // Apply runs once, automatically, when the tail opens.
  useEffect(() => {
    if (ranApply.current || sub !== "apply") return;
    ranApply.current = true;
    if (targetId === null) {
      setError("No registered target to apply to. Register one in the Targets tab, then reopen the makeover.");
      return;
    }
    void (async () => {
      setBusy(true);
      setError(null);
      try {
        const result = await makeoverApi.applyTarget(targetId);
        setReport(result);
        advance("proof");
        const readback = await makeoverApi.readBack(targetId, changedIds);
        setProof(readback);
        advance("log");
      } catch (caught: unknown) {
        setError(messageOf(caught));
      } finally {
        setBusy(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function confirmLog() {
    setBusy(true);
    setError(null);
    try {
      const result = await makeoverApi.appendDesignLog({
        line: logLine,
        direction,
        corrections: logCorrections || undefined,
      });
      setLogDone(result.section);
      advance("done");
    } catch (caught: unknown) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mk-tail" id="mk-auto-tail" data-sub={sub}>
      <TailStep label="APPLY" state={report ? "done" : error && sub === "apply" ? "error" : busy && sub === "apply" ? "busy" : "idle"}>
        {targetLabel && (
          <p className="mk-tail__target mono">
            target · {targetLabel}
          </p>
        )}
        {busy && sub === "apply" && <TailSkeleton label="Applying…" />}
        {report && <ApplyReportView report={report} />}
      </TailStep>

      <TailStep label="PROOF" state={proof ? (proof.ok ? "done" : "error") : sub === "proof" && busy ? "busy" : "idle"}>
        {sub === "proof" && busy && <TailSkeleton label="Reading back…" />}
        {proof && <ProofView proof={proof} />}
      </TailStep>

      <TailStep label="LOG" state={logDone ? "done" : sub === "log" ? "active" : "idle"}>
        {sub === "log" && logDone === null && (
          <div className="mk-tail__log">
            <label className="mk-stage__redirect-label mono" htmlFor="mk-log-line">
              design-log line
            </label>
            <input
              id="mk-log-line"
              className="mk-stage__redirect-input mono"
              type="text"
              value={logLine}
              onChange={(event) => setLogLine(event.target.value)}
            />
            <label className="mk-stage__redirect-label mono" htmlFor="mk-log-corrections">
              corrections (harvested)
            </label>
            <textarea
              id="mk-log-corrections"
              className="mk-tail__log-corrections mono"
              rows={2}
              value={logCorrections}
              onChange={(event) => setLogCorrections(event.target.value)}
            />
            <p className="mk-tail__log-direction mono">direction · {direction || "(none)"}</p>
            <button type="button" className="mk-btn mk-btn--lock" disabled={busy} onClick={() => void confirmLog()}>
              {busy ? "APPENDING…" : "CONFIRM & APPEND"}
            </button>
          </div>
        )}
        {logDone && (
          <>
            <pre className="mk-tail__log-appended mono">{logDone}</pre>
            <button type="button" className="mk-btn mk-btn--lock" onClick={onDone} id="mk-done">
              DONE
            </button>
          </>
        )}
      </TailStep>

      {error !== null && (
        <p className="mk-stage__error" role="alert">
          <span className="mk-stage__error-tag mono" aria-hidden="true">error</span>
          {error}
        </p>
      )}
    </div>
  );
}

function TailStep({
  label,
  state,
  children,
}: {
  label: string;
  state: "idle" | "busy" | "active" | "done" | "error";
  children: React.ReactNode;
}) {
  return (
    <section className="mk-tail__step" data-state={state} aria-label={label}>
      <h3 className="mk-tail__step-head mono">
        <span className="mk-tail__step-led" aria-hidden="true" />
        {label}
        <span className="mk-tail__step-state mono">{state}</span>
      </h3>
      {children}
    </section>
  );
}

function TailSkeleton({ label }: { label: string }) {
  return (
    <div className="mk-stage__skeleton" aria-busy="true" aria-live="polite">
      <span className="sr-only">{label}</span>
      <span className="mk-skel-row" />
      <span className="mk-skel-row" />
    </div>
  );
}

function ApplyReportView({ report }: { report: ApplyReportSummary }) {
  const blocked = report.entries.filter((e) => e.status === "blocked");
  const partial = report.entries.filter((e) => e.status === "partial");
  return (
    <div className="mk-report">
      <p className="mk-report__counts mono">
        applied {report.applied} · partial {report.partial} · blocked {report.blocked}
        {report.held > 0 && ` · held ${report.held}`}
      </p>
      {blocked.length > 0 && (
        <ul className="mk-report__list mk-report__list--blocked" id="mk-report-blocked">
          {blocked.map((entry, i) => (
            <li key={i} className="mono">
              <span className="mk-report__cat">{entry.category}</span> {entry.chrooked_id}
              {entry.symbol ? ` (${entry.symbol})` : ""} — {entry.reason}
            </li>
          ))}
        </ul>
      )}
      {partial.length > 0 && (
        <ul className="mk-report__list mk-report__list--partial">
          {partial.map((entry, i) => (
            <li key={i} className="mono">
              <span className="mk-report__cat">{entry.category}</span> {entry.chrooked_id} — {entry.reason}
              {entry.partial_fields.length > 0 && ` [${entry.partial_fields.join(", ")}]`}
            </li>
          ))}
        </ul>
      )}
      {report.sync && <SyncStatus sync={report.sync} idPrefix="makeover" />}
      <details className="mk-report__md">
        <summary className="mono">full report</summary>
        <pre className="mk-report__md-body mono">{report.report_md}</pre>
      </details>
    </div>
  );
}

function ProofView({ proof }: { proof: ReadBackResponse }) {
  return (
    <div className="mk-proof">
      <p className="mk-proof__headline mono" data-ok={proof.ok || undefined}>
        {proof.ok ? "READ-BACK OK" : "READ-BACK MISMATCH"} · {proof.ok_count}/{proof.total}
      </p>
      {proof.species.map((species) => (
        <div key={species.chrooked_id} className="mk-proof__species">
          <p className="mk-proof__species-head mono" data-ok={species.ok || undefined}>
            {species.name} · {species.ok_count}/{species.total}
            {species.missing && " · MISSING ON DISK"}
          </p>
          <ul className="mk-proof__checks">
            {species.checks
              .filter((check) => !check.ok)
              .map((check, i) => (
                <li key={i} className="mono mk-proof__check" data-ok={false}>
                  {check.field}: expected {JSON.stringify(check.expected)} · got{" "}
                  {JSON.stringify(check.actual)}
                </li>
              ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
