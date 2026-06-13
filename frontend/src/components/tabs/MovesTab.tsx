import { useState } from "react";
import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import type { Move } from "../../types";
import { TypeChip } from "../TypeChip";
import { ErrorView, EmptyView } from "../StatusView";
import { MoveEditor } from "../editors/MoveEditor";
import "./tabs.css";
import "../editors/editors.css";

/** Ruleset-owned moves: a table plus create/edit/delete. Power/accuracy/pp are
    mono figures; a status move shows an em dash for power. Editing opens the
    {@link MoveEditor}; a save/delete reloads the list in place. */
export function MovesTab() {
  const { data, error, status, isLoading, reload } = useResource<Move[]>(api.moves);
  // null = closed; { move: null } = new; { move } = edit that move.
  const [editing, setEditing] = useState<{ move: Move | null } | null>(null);

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading) return <p className="tab-loading">Loading moves…</p>;

  const moves = data ?? [];

  return (
    <div className="tab" id="tab-moves">
      <div className="tab-toolbar">
        <span className="tab-toolbar__title">{moves.length} owned moves</span>
        <button
          type="button"
          className="btn btn--primary btn--new"
          onClick={() => setEditing({ move: null })}
        >
          <span aria-hidden="true">+ </span>New move
        </button>
      </div>

      {moves.length === 0 ? (
        <EmptyView message="The Ruleset owns no moves yet. Create one to get started." />
      ) : (
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
              <th aria-label="Edit" />
            </tr>
          </thead>
          <tbody>
            {moves.map((move) => (
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
                <td className="tab-num">
                  <button
                    type="button"
                    className="tab-row-edit"
                    aria-label={`Edit ${move.name}`}
                    onClick={() => setEditing({ move })}
                  >
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editing !== null && (
        <MoveEditor
          move={editing.move}
          onClose={() => setEditing(null)}
          onSaved={reload}
        />
      )}
    </div>
  );
}
