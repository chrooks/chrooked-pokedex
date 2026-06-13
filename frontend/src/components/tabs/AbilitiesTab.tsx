import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import type { Ability } from "../../types";
import { ErrorView, EmptyView } from "../StatusView";
import "./tabs.css";

/** Read-only list of Ruleset-owned abilities (data only; the mechanic lives in
    a behavior spec, shown on the Behaviors tab). */
export function AbilitiesTab() {
  const { data, error, status, isLoading } = useResource<Ability[]>(api.abilities);

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading) return <p className="tab-loading">Loading abilities…</p>;
  if (data === null || data.length === 0)
    return <EmptyView message="The Ruleset owns no abilities yet." />;

  return (
    <div className="tab" id="tab-abilities">
      <dl className="tab-deflist">
        {data.map((ability) => (
          <div key={ability.chrooked_id} className="tab-deflist__item">
            <dt className="tab-strong">{ability.name}</dt>
            <dd className="tab-dim">
              {ability.description || <span className="tab-faint">No description.</span>}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
