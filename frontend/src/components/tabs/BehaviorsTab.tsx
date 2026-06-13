import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import type { Behavior } from "../../types";
import { ErrorView, EmptyView } from "../StatusView";
import "./tabs.css";

/** Read-only list of behavior specs: the human-owned mechanic layer. Each shows
    its effects (each pinned to a neutral battle trigger) and acceptance cases. */
export function BehaviorsTab() {
  const { data, error, status, isLoading } = useResource<Behavior[]>(api.behaviors);

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading) return <p className="tab-loading">Loading behaviors…</p>;
  if (data === null || data.length === 0)
    return <EmptyView message="The Ruleset defines no custom behaviors yet." />;

  return (
    <div className="tab tab--behaviors" id="tab-behaviors">
      {data.map((behavior) => (
        <article key={behavior.chrooked_id} className="behavior">
          <header className="behavior__head">
            <h3 className="behavior__name">{behavior.name}</h3>
            <span className="behavior__applies mono">{behavior.applies_to}</span>
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
      ))}
    </div>
  );
}
