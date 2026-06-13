import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import type { TypeChartEntry } from "../../types";
import { TypeChip } from "../TypeChip";
import { ErrorView, EmptyView } from "../StatusView";
import "./tabs.css";

/** Read-only list of type-chart multiplier overrides (attacker vs defender). A
    multiplier reads with its meaning: 0 = immune, 0.5 = resisted, 2 = super. */
export function TypeChartTab() {
  const { data, error, status, isLoading } =
    useResource<TypeChartEntry[]>(api.typeChart);

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading) return <p className="tab-loading">Loading type chart…</p>;
  if (data === null || data.length === 0)
    return <EmptyView message="The Ruleset overrides no type matchups." />;

  return (
    <div className="tab" id="tab-type-chart">
      <ul className="tab-matchups">
        {data.map((entry) => (
          <li
            key={`${entry.attacker}-${entry.defender}-${entry.multiplier}`}
            className="tab-matchup"
          >
            <TypeChip type={entry.attacker} variant="code" />
            <span className="tab-matchup__vs">vs</span>
            <TypeChip type={entry.defender} variant="code" />
            <span className="tab-matchup__mult mono" data-meaning={meaning(entry.multiplier)}>
              ×{entry.multiplier}
            </span>
            <span className="tab-matchup__word">{meaning(entry.multiplier)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function meaning(multiplier: number): string {
  if (multiplier === 0) return "immune";
  if (multiplier < 1) return "resisted";
  if (multiplier > 1) return "super effective";
  return "neutral";
}
