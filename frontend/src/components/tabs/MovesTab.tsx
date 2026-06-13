import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import type { Move } from "../../types";
import { TypeChip } from "../TypeChip";
import { ErrorView, EmptyView } from "../StatusView";
import "./tabs.css";

/** Read-only table of Ruleset-owned moves. Power/accuracy/pp are mono figures;
    a status move shows an em dash for power. */
export function MovesTab() {
  const { data, error, status, isLoading } = useResource<Move[]>(api.moves);

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading) return <p className="tab-loading">Loading moves…</p>;
  if (data === null || data.length === 0)
    return <EmptyView message="The Ruleset owns no moves yet." />;

  return (
    <div className="tab" id="tab-moves">
      <table className="tab-table">
        <thead>
          <tr>
            <th>Move</th>
            <th>Type</th>
            <th>Cat</th>
            <th className="tab-num">Pow</th>
            <th className="tab-num">Acc</th>
            <th className="tab-num">PP</th>
            <th>Effect</th>
          </tr>
        </thead>
        <tbody>
          {data.map((move) => (
            <tr key={move.chrooked_id}>
              <td className="tab-strong">{move.name}</td>
              <td>
                <TypeChip type={move.type} variant="code" />
              </td>
              <td className="tab-dim">{move.category}</td>
              <td className="tab-num mono">{move.power ?? "—"}</td>
              <td className="tab-num mono">{move.accuracy ?? "—"}</td>
              <td className="tab-num mono">{move.pp ?? "—"}</td>
              <td className="tab-dim">{move.effect === "hit" ? "" : move.effect}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
