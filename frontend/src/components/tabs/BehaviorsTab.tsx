import { useState } from "react";
import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import type { Behavior } from "../../types";
import { ErrorView, EmptyView } from "../StatusView";
import { BehaviorEditor } from "../editors/BehaviorEditor";
import "./tabs.css";
import "../editors/editors.css";

/** Behavior specs: the human-owned mechanic layer. Each card shows its effects
    (pinned to a neutral battle trigger) and acceptance cases; create/edit/delete
    runs through the {@link BehaviorEditor}. */
export function BehaviorsTab() {
  const { data, error, status, isLoading, reload } =
    useResource<Behavior[]>(api.behaviors);
  const [editing, setEditing] = useState<{ behavior: Behavior | null } | null>(null);

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading) return <p className="tab-loading">Loading behaviors…</p>;

  const behaviors = data ?? [];

  return (
    <div className="tab tab--behaviors" id="tab-behaviors">
      <div className="tab-toolbar">
        <span className="tab-toolbar__title">{behaviors.length} behaviors</span>
        <button
          type="button"
          className="btn btn--primary btn--new"
          onClick={() => setEditing({ behavior: null })}
        >
          <span aria-hidden="true">+ </span>New behavior
        </button>
      </div>

      {behaviors.length === 0 ? (
        <EmptyView message="The Ruleset defines no custom behaviors yet. Create one to get started." />
      ) : (
        behaviors.map((behavior) => (
          <article key={behavior.chrooked_id} className="behavior">
            <header className="behavior__head">
              <h3 className="behavior__name">{behavior.name}</h3>
              <span className="behavior__applies mono">{behavior.applies_to}</span>
              <button
                type="button"
                className="tab-row-edit"
                aria-label={`Edit ${behavior.name}`}
                onClick={() => setEditing({ behavior })}
              >
                Edit
              </button>
            </header>
            <ul className="behavior__effects">
              {behavior.effects.map((effect, index) => (
                <li key={index} className="behavior__effect">
                  <span className="behavior__trigger mono">{effect.trigger}</span>
                  <span className="behavior__summary">{effect.summary}</span>
                  {effect.when !== null && (
                    <span className="behavior__when">when {effect.when}</span>
                  )}
                </li>
              ))}
            </ul>
            {behavior.test_cases.length > 0 && (
              <details className="behavior__tests">
                <summary>
                  {behavior.test_cases.length} test case
                  {behavior.test_cases.length === 1 ? "" : "s"}
                </summary>
                <ul>
                  {behavior.test_cases.map((test, index) => (
                    <li key={index}>
                      <span className="behavior__given">{test.given}</span>
                      <span className="behavior__expect">→ {test.expect}</span>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </article>
        ))
      )}

      {editing !== null && (
        <BehaviorEditor
          behavior={editing.behavior}
          onClose={() => setEditing(null)}
          onSaved={reload}
        />
      )}
    </div>
  );
}
