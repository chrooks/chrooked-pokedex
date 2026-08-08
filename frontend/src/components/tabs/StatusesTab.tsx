import { useState } from "react";
import { api } from "../../api";
import { PokeballSpinner } from "../PokeballSpinner";
import { useResource } from "../../hooks/useResource";
import type { Status } from "../../types";
import { ErrorView, EmptyView } from "../StatusView";
import { StatusEditor } from "../editors/StatusEditor";
import "./tabs.css";
import "../editors/editors.css";

/** Status conditions: burn, frostbite, paralysis, and the rest. Each card shows
    its player-facing description, the engine symbol it maps to, and its effect
    lines; editing runs through the {@link StatusEditor}. No create button — the
    status set is closed, since a new one means teaching an engine a new
    condition rather than adding a record. */
export function StatusesTab() {
  const { data, error, status, isLoading, reload } =
    useResource<Status[]>(api.statuses);
  const [editing, setEditing] = useState<Status | null>(null);

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading)
    return (
      <div className="tab-loading">
        <PokeballSpinner label="Loading statuses…" />
      </div>
    );

  const statuses = data ?? [];

  return (
    <div className="tab tab--statuses" id="tab-statuses">
      <div className="tab-toolbar">
        <span className="tab-toolbar__title">{statuses.length} statuses</span>
      </div>

      {statuses.length === 0 ? (
        <EmptyView message="The Ruleset defines no status conditions yet." />
      ) : (
        statuses.map((entry) => (
          <article
            key={entry.chrooked_id}
            className="behavior"
            id={`status-card-${entry.chrooked_id}`}
          >
            <header className="behavior__head">
              <h3 className="behavior__name">{entry.name}</h3>
              <span className="behavior__applies mono">
                {Object.entries(entry.aka)
                  .map(([engine, symbol]) => `${engine}: ${String(symbol)}`)
                  .join(" · ")}
              </span>
              <button
                type="button"
                className="tab-row-edit"
                aria-label={`Edit ${entry.name}`}
                onClick={() => setEditing(entry)}
              >
                Edit
              </button>
            </header>
            <p className="behavior__summary" id={`status-desc-${entry.chrooked_id}`}>
              {entry.description}
            </p>
            <ul className="behavior__effects">
              {entry.effects.map((effect, index) => (
                <li key={index} className="behavior__effect">
                  <span className="behavior__summary">{effect}</span>
                </li>
              ))}
            </ul>
          </article>
        ))
      )}

      {editing !== null && (
        <StatusEditor
          status={editing}
          onClose={() => setEditing(null)}
          onSaved={reload}
        />
      )}
    </div>
  );
}
