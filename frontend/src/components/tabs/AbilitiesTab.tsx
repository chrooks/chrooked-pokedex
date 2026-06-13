import { useState } from "react";
import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import type { Ability } from "../../types";
import { ErrorView, EmptyView } from "../StatusView";
import { AbilityEditor } from "../editors/AbilityEditor";
import "./tabs.css";
import "../editors/editors.css";

/** Ruleset-owned abilities (data only; the mechanic lives in a behavior spec,
    shown on the Behaviors tab). A definition list plus create/edit/delete via
    the {@link AbilityEditor}; a save/delete reloads the list in place. */
export function AbilitiesTab() {
  const { data, error, status, isLoading, reload } =
    useResource<Ability[]>(api.abilities);
  const [editing, setEditing] = useState<{ ability: Ability | null } | null>(null);

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading) return <p className="tab-loading">Loading abilities…</p>;

  const abilities = data ?? [];

  return (
    <div className="tab" id="tab-abilities">
      <div className="tab-toolbar">
        <span className="tab-toolbar__title">{abilities.length} owned abilities</span>
        <button
          type="button"
          className="btn btn--primary btn--new"
          onClick={() => setEditing({ ability: null })}
        >
          <span aria-hidden="true">+ </span>New ability
        </button>
      </div>

      {abilities.length === 0 ? (
        <EmptyView message="The Ruleset owns no abilities yet. Create one to get started." />
      ) : (
        <dl className="tab-deflist">
          {abilities.map((ability) => (
            <div key={ability.chrooked_id} className="tab-deflist__item">
              <div className="tab-deflist__head">
                <dt className="tab-strong">{ability.name}</dt>
                <button
                  type="button"
                  className="tab-row-edit"
                  aria-label={`Edit ${ability.name}`}
                  onClick={() => setEditing({ ability })}
                >
                  Edit
                </button>
              </div>
              <dd className="tab-dim">
                {ability.description || (
                  <span className="tab-faint">No description.</span>
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {editing !== null && (
        <AbilityEditor
          ability={editing.ability}
          onClose={() => setEditing(null)}
          onSaved={reload}
        />
      )}
    </div>
  );
}
