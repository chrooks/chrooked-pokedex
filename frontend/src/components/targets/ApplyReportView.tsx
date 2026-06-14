/* The Apply Report: the four headline counts as a stat strip, then the
   DATA-ONLY created abilities as working packet links. Presentational — it
   renders a report whether it came from a (safe) preview or a (destructive)
   apply; the `mode` only changes the heading. */

import type { ApplyReportSummary } from "../../types";
import { PacketLink } from "./PacketLink";

type Props = {
  report: ApplyReportSummary;
  mode: "preview" | "apply";
};

const COUNTS = [
  { key: "applied", label: "Applied", tone: "ok" },
  { key: "partial", label: "Partial", tone: "warn" },
  { key: "blocked", label: "Blocked", tone: "bad" },
  { key: "created", label: "Created", tone: "new" },
] as const;

export function ApplyReportView({ report, mode }: Props) {
  return (
    <section className="report" id="apply-report" aria-label="Apply report">
      <h3 className="report__heading">
        {mode === "preview" ? "Preview report" : "Apply report"}
        <span className="report__heading-note">
          {mode === "preview"
            ? "ran the applier, reverted the fork"
            : "the fork was written"}
        </span>
      </h3>

      <dl className="report__counts" id="apply-report-counts">
        {COUNTS.map((count) => (
          <div
            key={count.key}
            className="report__count"
            data-tone={count.tone}
            id={`apply-count-${count.key}`}
          >
            <dt className="report__count-label">{count.label}</dt>
            <dd className="report__count-value mono">{report[count.key]}</dd>
          </div>
        ))}
      </dl>

      {report.data_only.length > 0 && (
        <div className="report__data-only" id="apply-data-only">
          <h4 className="report__sub">DATA-ONLY abilities ({report.data_only.length})</h4>
          <p className="report__sub-note">
            Created with no engine mechanic — each carries a behavior packet to
            hand to the engine.
          </p>
          <ul className="report__packets">
            {report.data_only.map((entry) => (
              <PacketLink key={entry.chrooked_id} entry={entry} />
            ))}
          </ul>
        </div>
      )}

      <details className="report__raw">
        <summary>Full report markdown</summary>
        <pre className="report__raw-md mono">{report.report_md}</pre>
      </details>
    </section>
  );
}
