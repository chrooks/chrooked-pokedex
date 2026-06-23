/* The Change Ledger tab (M6): an append-only history of every Ruleset mutation.

   Reads GET /api/ledger newest-first, filterable by scope and kind. Each row
   shows when, the scope and source as chips, the entity, and a compact field
   diff. Apply rows show the report counts; seed rows show the bulk summary.

   Per-entity history: when `view.query` carries a chrooked_id (set by the detail
   ledger's "history" button), the list is pre-filtered to that entity. */

import { useMemo, useState } from "react";
import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import { useUrlState } from "../../hooks/useUrlState";
import type { LedgerEntry } from "../../types";
import { PokeballSpinner } from "../PokeballSpinner";
import { ErrorView, EmptyView } from "../StatusView";
import { formatLedgerTs, renderLedgerValue, scopeKind } from "../../lib/ledgerFormat";
import "./ledger-tab.css";

const KINDS = ["", "species", "move", "ability", "type-chart", "behavior", "apply", "seed"] as const;

export function LedgerTab() {
  const [view, update] = useUrlState();
  const chrookedId = view.query.trim() || undefined;
  // Kind filter is local UI state (not URL-persisted); the entity filter rides on
  // view.query so the detail ledger's "History" button can deep-link to it.
  const [kind, setKind] = useState("");

  // Memoize the fetcher on the active filters so useResource refetches when they
  // change. The chrooked_id (entity history) filters server-side too.
  const fetcher = useMemo(
    () => (signal?: AbortSignal) =>
      api
        .ledger(
          {
            chrooked_id: chrookedId,
            kind: kind || undefined,
            limit: 500,
          },
          signal,
        )
        .then((r) => r.entries),
    [chrookedId, kind],
  );
  const { data, error, status, isLoading } = useResource<LedgerEntry[]>(fetcher);

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading)
    return (
      <div className="tab-loading">
        <PokeballSpinner label="Loading ledger…" />
      </div>
    );

  const entries = data ?? [];

  return (
    <div className="tab tab--ledger" id="tab-ledger">
      <div className="ledger-tab__toolbar">
        <span className="ledger-tab__count">
          {entries.length} change{entries.length === 1 ? "" : "s"}
          {chrookedId && (
            <>
              {" for "}
              <strong>{chrookedId}</strong>{" "}
              <button
                type="button"
                id="ledger-clear-entity"
                className="ledger-tab__clear"
                onClick={() => update({ query: "" })}
              >
                clear
              </button>
            </>
          )}
        </span>
        <label className="ledger-tab__filter">
          Kind
          <select
            id="ledger-filter-kind"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {k === "" ? "all" : k}
              </option>
            ))}
          </select>
        </label>
      </div>

      {entries.length === 0 ? (
        <EmptyView message="No changes recorded yet. Edits, applies, harvests, and seeds will show here." />
      ) : (
        <ol className="ledger-tab__list">
          {entries.map((entry, i) => (
            <LedgerRow key={`${entry.ts}-${i}`} entry={entry} />
          ))}
        </ol>
      )}
    </div>
  );
}

function LedgerRow({ entry }: { entry: LedgerEntry }) {
  return (
    <li className="ledger-tab__row" data-source={entry.source}>
      <div className="ledger-tab__row-head">
        <time className="ledger-tab__ts mono">{formatLedgerTs(entry.ts)}</time>
        <span className={`ledger-tab__chip ledger-tab__chip--${scopeKind(entry.scope)}`}>
          {entry.scope}
        </span>
        <span className="ledger-tab__chip ledger-tab__chip--source">{entry.source}</span>
        <span className="ledger-tab__kind">{entry.kind}</span>
        {entry.chrooked_id && (
          <span className="ledger-tab__entity mono">{entry.chrooked_id}</span>
        )}
      </div>
      <LedgerDetail entry={entry} />
    </li>
  );
}

function LedgerDetail({ entry }: { entry: LedgerEntry }) {
  if (entry.report) {
    return (
      <div className="ledger-tab__report">
        applied {entry.report.applied} · partial {entry.report.partial} · blocked{" "}
        {entry.report.blocked}
      </div>
    );
  }
  if (entry.summary) {
    return (
      <div className="ledger-tab__report">
        {Object.entries(entry.summary)
          .map(([k, v]) => `${k}: ${v}`)
          .join(" · ")}
      </div>
    );
  }
  if (entry.fields && Object.keys(entry.fields).length > 0) {
    return (
      <ul className="ledger-tab__fields">
        {Object.entries(entry.fields).map(([field, { from, to }]) => (
          <li key={field} className="ledger-tab__field">
            <span className="ledger-tab__field-name">{field}</span>
            <span className="ledger-tab__from mono">{renderLedgerValue(from)}</span>
            <span className="ledger-tab__arrow" aria-hidden="true">→</span>
            <span className="ledger-tab__to mono">{renderLedgerValue(to)}</span>
          </li>
        ))}
      </ul>
    );
  }
  return null;
}
