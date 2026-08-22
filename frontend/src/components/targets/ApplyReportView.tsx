/* The Apply Report: headline counts, a per-category breakdown, the actionable
   (non-applied) entries with reasons, then the DATA-ONLY packets. Renders a
   report whether it came from a (safe) preview or a (destructive) apply; `mode`
   only changes the heading.

   The counts and category rows double as filters: clicking a status tile
   (partial/blocked/held) or a category row narrows the needs-attention list to
   it, so a 500-entry report can be sliced to "just the blocked species" in one
   click. Applied/created tiles and all-applied categories are not clickable —
   they have no per-entry rows (applied entries are bulk-counted, never listed). */

import { useEffect, useMemo, useState } from "react";
import type {
  ApplyReportSummary,
  ReportEntry,
  ReportStatus,
} from "../../types";
import { PacketLink } from "./PacketLink";
import { SyncStatus } from "./SyncStatus";

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

/** Only these statuses have per-entry rows in the needs-attention list, so only
    these tiles filter it. */
const FILTERABLE: ReadonlySet<string> = new Set(["partial", "blocked", "held"]);

export function ApplyReportView({ report, mode }: Props) {
  const [statusFilter, setStatusFilter] = useState<ReportStatus | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  // A fresh run starts unfiltered (the previous filter may not even apply).
  useEffect(() => {
    setStatusFilter(null);
    setCategoryFilter(null);
  }, [report]);

  const categories = useMemo(
    () => Object.entries(report.by_category).sort(([a], [b]) => a.localeCompare(b)),
    [report.by_category],
  );

  const attention = report.entries; // server sends only the non-applied ones
  const shown = useMemo(
    () =>
      attention.filter(
        (e) =>
          (statusFilter === null || e.status === statusFilter) &&
          (categoryFilter === null || e.category === categoryFilter),
      ),
    [attention, statusFilter, categoryFilter],
  );
  const filtered = statusFilter !== null || categoryFilter !== null;

  const toggleStatus = (s: ReportStatus) =>
    setStatusFilter((cur) => (cur === s ? null : s));
  const toggleCategory = (c: string) =>
    setCategoryFilter((cur) => (cur === c ? null : c));
  const clearFilters = () => {
    setStatusFilter(null);
    setCategoryFilter(null);
  };

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

      {report.data_backup && report.data_backup.status !== "skipped" && (
        <p
          className="report__backup"
          id="apply-data-backup"
          data-status={report.data_backup.status}
        >
          {report.data_backup.status === "created"
            ? "Backed up Data/ → Data.bak before writing (boot-recompile safety net)."
            : report.data_backup.reason + "."}
        </p>
      )}

      {report.sync && <SyncStatus sync={report.sync} idPrefix="patch" />}

      <div
        className="report__counts"
        id="apply-report-counts"
        role="group"
        aria-label="Filter the list by status"
      >
        {COUNTS.map((count) => {
          const value = report[count.key];
          const canFilter = FILTERABLE.has(count.key) && value > 0;
          const active = statusFilter === count.key;
          const body = (
            <>
              <span className="report__count-label">{count.label}</span>
              <span className="report__count-value mono">{value}</span>
            </>
          );
          if (!canFilter) {
            return (
              <div
                key={count.key}
                className="report__count"
                data-tone={count.tone}
                data-zero={value === 0 ? "" : undefined}
                id={`apply-count-${count.key}`}
              >
                {body}
              </div>
            );
          }
          return (
            <button
              key={count.key}
              type="button"
              className="report__count report__count--btn"
              data-tone={count.tone}
              data-active={active ? "" : undefined}
              aria-pressed={active}
              id={`apply-count-${count.key}`}
              aria-label={`Show only ${count.label.toLowerCase()} entries`}
              onClick={() => toggleStatus(count.key as ReportStatus)}
            >
              {body}
            </button>
          );
        })}
      </div>

      {categories.length > 0 && (
        <ul className="report__cats" id="apply-report-cats">
          {categories.map(([name, c]) => {
            const drillable = c.partial + c.blocked + c.held > 0;
            const active = categoryFilter === name;
            const body = (
              <>
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
              </>
            );
            return (
              <li key={name}>
                {drillable ? (
                  <button
                    type="button"
                    className="report__cat report__cat--btn"
                    data-active={active ? "" : undefined}
                    aria-pressed={active}
                    aria-label={`Show only ${name} entries`}
                    onClick={() => toggleCategory(name)}
                  >
                    {body}
                  </button>
                ) : (
                  <span className="report__cat report__cat--static">{body}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {attention.length > 0 ? (
        <div className="report__attention" id="apply-report-entries">
          <h4 className="report__sub">
            Needs attention
            {filtered ? (
              <span className="report__sub-filter">
                {" "}
                showing {shown.length} of {attention.length}
                <button
                  type="button"
                  className="report__clear"
                  id="apply-report-clear-filter"
                  onClick={clearFilters}
                >
                  clear
                </button>
              </span>
            ) : (
              <span className="report__sub-count"> ({attention.length})</span>
            )}
          </h4>
          {shown.length > 0 ? (
            <ul className="report__entries">
              {shown.map((entry) => (
                <EntryRow key={`${entry.category}:${entry.chrooked_id}`} entry={entry} />
              ))}
            </ul>
          ) : (
            <p className="report__sub-note">No entries match the current filter.</p>
          )}
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
