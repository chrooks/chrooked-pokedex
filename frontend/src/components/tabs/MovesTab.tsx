import { useMemo, useState } from "react";
import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import { MOVE_FLAGS } from "../../lib/format";
import type { Move } from "../../types";
import { TypeChip } from "../TypeChip";
import { ErrorView, EmptyView } from "../StatusView";
import { MoveEditor } from "../editors/MoveEditor";
import "./tabs.css";
import "../editors/editors.css";

/** Ruleset-owned moves: a table with create/edit/delete, a Tags column showing
    each move's neutral flags, and a filter bar — a name search plus toggleable
    flag chips (AND-combined) so you can pull up e.g. every kicking move. */
export function MovesTab() {
  const { data, error, status, isLoading, reload } = useResource<Move[]>(api.moves);
  const [editing, setEditing] = useState<{ move: Move | null } | null>(null);
  const [query, setQuery] = useState("");
  const [activeFlags, setActiveFlags] = useState<string[]>([]);

  const moves = useMemo(() => data ?? [], [data]);

  // Flags actually present in the data, in canonical order — the filter chips.
  const presentFlags = useMemo(() => {
    const present = new Set(moves.flatMap((m) => m.flags));
    return MOVE_FLAGS.filter((flag) => present.has(flag));
  }, [moves]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return moves.filter((move) => {
      const nameMatch = q === "" || move.name.toLowerCase().includes(q);
      const flagMatch = activeFlags.every((flag) => move.flags.includes(flag));
      return nameMatch && flagMatch;
    });
  }, [moves, query, activeFlags]);

  function toggleFlag(flag: string) {
    setActiveFlags((flags) =>
      flags.includes(flag) ? flags.filter((f) => f !== flag) : [...flags, flag],
    );
  }

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading) return <p className="tab-loading">Loading moves…</p>;

  return (
    <div className="tab" id="tab-moves">
      <div className="tab-toolbar">
        <span className="tab-toolbar__title">
          {filtered.length === moves.length
            ? `${moves.length} owned moves`
            : `${filtered.length} of ${moves.length} moves`}
        </span>
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
        <>
          <div className="tab-filterbar">
            <input
              type="search"
              className="tab-search"
              placeholder="Search moves by name"
              aria-label="Search moves by name"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {presentFlags.map((flag) => (
              <button
                key={flag}
                type="button"
                className="move-tag"
                data-on={activeFlags.includes(flag)}
                aria-pressed={activeFlags.includes(flag)}
                aria-label={`Toggle ${flag} filter`}
                onClick={() => toggleFlag(flag)}
              >
                {flag}
              </button>
            ))}
          </div>

          {filtered.length === 0 ? (
            <EmptyView message="No moves match the current filter." />
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
                  <th>Tags</th>
                  <th aria-label="Edit" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((move) => (
                  <tr key={move.chrooked_id}>
                    <td className="tab-strong">{move.name}</td>
                    <td>
                      <TypeChip type={move.type} variant="code" />
                    </td>
                    <td className="tab-dim">{move.category}</td>
                    <td className="tab-num mono">{move.power ?? "—"}</td>
                    <td className="tab-num mono">{move.accuracy ?? "—"}</td>
                    <td className="tab-num mono">{move.pp ?? "—"}</td>
                    <td>
                      {move.flags.length === 0 ? (
                        <span className="tab-faint">—</span>
                      ) : (
                        <span className="move-tags">
                          {move.flags.map((flag) => (
                            <button
                              key={flag}
                              type="button"
                              className="move-tag"
                              data-on={activeFlags.includes(flag)}
                              aria-pressed={activeFlags.includes(flag)}
                              aria-label={`Filter by ${flag}`}
                              onClick={() => toggleFlag(flag)}
                            >
                              {flag}
                            </button>
                          ))}
                        </span>
                      )}
                    </td>
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
        </>
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
