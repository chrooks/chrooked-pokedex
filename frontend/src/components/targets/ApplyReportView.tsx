/* The Apply Report: headline counts, a per-category breakdown, the actionable
   (non-applied) entries with reasons, then the DATA-ONLY packets. Presentational
   — renders a report whether it came from a (safe) preview or a (destructive)
   apply; `mode` only changes the heading.

   The whole point is "what did NOT land, and why". Applied entries stay as
   counts; partial/blocked/held are listed line-by-line with the applier's own
   reason so the report is scannable instead of a markdown blob. */

import type {
  ApplyReportSummary,
  ReportEntry,
  ReportStatus,
} from "../../types";
import { PacketLink } from "./PacketLink";

type Props = {
  report: ApplyReportSummary;
  mode: "preview" | "apply";
};

const COUNTS = [
  { key: "applied", label: "Applied", tone: "ok" },
  { key: "partial", label: "Partial", tone: "warn" },
  { key: "blocked", label: "Blocked", tone: "bad" },
  { key: "held", label: "Held", tone: "hold" },
  { key: "created", label: "Created", tone: "new" },
] as const;

/** Status → tone + a short text tag (never color-alone — a11y). */
const STATUS_META: Record<ReportStatus, { tone: string; tag: string }> = {
  applied: { tone: "ok", tag: "OK" },
  partial: { tone: "warn", tag: "PARTIAL" },
  blocked: { tone: "bad", tag: "BLOCKED" },
  held: { tone: "hold", tag: "HELD" },
};

export function ApplyReportView({ report, mode }: Props) {
  const attention = report.entries; // server sends only the non-applied ones
  const categories = Object.entries(report.by_category).sort(([a], [b]) =>
    a.localeCompare(b),
  );

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
            data-zero={report[count.key] === 0 ? "" : undefined}
            id={`apply-count-${count.key}`}
          >
            <dt className="report__count-label">{count.label}</dt>
            <dd className="report__count-value mono">{report[count.key]}</dd>
          </div>
        ))}
      </dl>

      {categories.length > 0 && (
        <ul className="report__cats" id="apply-report-cats">
          {categories.map(([name, c]) => (
            <li key={name} className="report__cat">
              <span className="report__cat-name">{name}</span>
              <span className="report__cat-counts mono">
                <span className="report__cat-ok">{c.applied}</span>
                {c.partial > 0 && (
                  <span className="report__cat-flag" data-tone="warn">
                    {c.partial} partial
                  </span>
                )}
                {c.blocked > 0 && (
                  <span className="report__cat-flag" data-tone="bad">
                    {c.blocked} blocked
                  </span>
                )}
                {c.held > 0 && (
                  <span className="report__cat-flag" data-tone="hold">
                    {c.held} held
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      {attention.length > 0 ? (
        <div className="report__attention" id="apply-report-entries">
          <h4 className="report__sub">Needs attention ({attention.length})</h4>
          <ul className="report__entries">
            {attention.map((entry) => (
              <EntryRow key={`${entry.category}:${entry.chrooked_id}`} entry={entry} />
            ))}
          </ul>
        </div>
      ) : (
        <p className="report__all-clear" id="apply-report-clear" role="status">
          Everything landed. No blocked, partial, or held entries.
        </p>
      )}

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

function EntryRow({ entry }: { entry: ReportEntry }) {
  const meta = STATUS_META[entry.status];
  return (
    <li className="report__entry" data-tone={meta.tone}>
      <span className="report__entry-tag mono" aria-hidden="true">
        {meta.tag}
      </span>
      <span className="report__entry-body">
        <span className="report__entry-id mono">
          <span className="sr-only">{meta.tag}: </span>
          {entry.category} · {entry.chrooked_id}
        </span>
        {entry.reason && (
          <span className="report__entry-reason">{entry.reason}</span>
        )}
        {entry.partial_fields.length > 0 && (
          <span className="report__entry-fields mono">
            unresolved: {entry.partial_fields.join(", ")}
          </span>
        )}
      </span>
    </li>
  );
}
