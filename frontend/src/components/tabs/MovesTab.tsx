import { useMemo, useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faPencil } from "@fortawesome/free-solid-svg-icons";
import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import { useUrlState } from "../../hooks/useUrlState";
import {
  MOVE_FLAGS,
  isMoveEdited,
  matchesMoveEditedFilter,
  type MoveEditedFilter,
} from "../../lib/format";
import type { DexEntry, Move } from "../../types";
import { EditedLed } from "../EditedLed";
import { TypeChip } from "../TypeChip";
import { ErrorView, EmptyView } from "../StatusView";
import { MoveEditor } from "../editors/MoveEditor";
import { DetailSidebar } from "../sidebar/DetailSidebar";
import { MoveDetail } from "../sidebar/MoveDetail";
import { ReverseLookupTab } from "../sidebar/ReverseLookupTab";
import "./tabs.css";
import "../editors/editors.css";

/** The three Edited-filter segments, mirroring the abilities tab's edited toggle
    with an explicit base-only option for browsing untouched moves. */
const EDITED_FILTERS: { key: MoveEditedFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "edited", label: "Edited" },
  { key: "base", label: "Not edited" },
];

/** The Moves tab at species-dex parity: the FULL merged list (base ⊕ Ruleset)
    with an edited-LED per row, an Edited filter, the existing flag chips + name
    search, a base→now diff in the editor, and per-Target backdrop awareness. In
    backdrop mode the list swaps to the selected fork's moves ⊕ Ruleset. */
export function MovesTab() {
  const [view] = useUrlState();
  // Swap the fetcher to the Target's backdrop (fork ⊕ Ruleset) when one is set;
  // otherwise read the base ⊕ Ruleset canon. Memoized by backdrop id so
  // useResource sees a stable fetcher and refetches only when the backdrop flips.
  const fetcher = useMemo(
    () => (view.backdrop ? api.targetMoves(view.backdrop) : api.moves),
    [view.backdrop],
  );
  // Dex fetcher mirrors the moves fetcher swap: backdrop → target dex, else canon.
  // The merged dex carries per-species learnsets used to build the reverse index.
  const dexFetcher = useMemo(
    () => (view.backdrop ? api.targetDex(view.backdrop) : api.dex),
    [view.backdrop],
  );
  const { data, error, status, isLoading, reload } = useResource<Move[]>(fetcher);
  const { data: dexData } = useResource<DexEntry[]>(dexFetcher);
  /** Row click → read-only sidebar. */
  const [selected, setSelected] = useState<Move | null>(null);
  /** "New move" → editor directly (no read-only step for a record not yet created). */
  const [editingNew, setEditingNew] = useState(false);
  /** Per-row pencil click → editor directly, skipping the read-only sidebar. */
  const [editDirect, setEditDirect] = useState<Move | null>(null);
  const [query, setQuery] = useState("");
  const [activeFlags, setActiveFlags] = useState<string[]>([]);
  const [editedFilter, setEditedFilter] = useState<MoveEditedFilter>("all");

  const moves = useMemo(() => data ?? [], [data]);
  const editedCount = useMemo(() => moves.filter(isMoveEdited).length, [moves]);

  // name→chrooked_id map built from the loaded moves list so we can normalize
  // learnset entries (which store the display name, e.g. "Ice Punch") to the
  // stable chrooked_id key ("icepunch") the MoveEditor lookup uses.
  const moveNameToId = useMemo((): Map<string, string> => {
    const map = new Map<string, string>();
    for (const m of moves) {
      map.set(m.name, m.chrooked_id);
    }
    return map;
  }, [moves]);

  // Reverse index: chrooked_id → species that have it in their learnset.
  // Built from the merged dex so Ruleset overrides are already applied (ac3).
  // Keyed by chrooked_id (not display name) to match the MoveEditor lookup.
  const learnedByIndex = useMemo((): Map<string, DexEntry[]> => {
    if (!dexData) return new Map();
    const index = new Map<string, DexEntry[]>();
    for (const species of dexData) {
      // Track which move keys we have already counted for this species so a mon
      // that learns the same move at multiple levels only appears once per move.
      const seenForSpecies = new Set<string>();
      for (const entry of species.learnset) {
        // Learnset stores display names; normalize to chrooked_id via the moves list.
        const key = moveNameToId.get(entry.move) ?? entry.move;
        if (seenForSpecies.has(key)) continue;
        seenForSpecies.add(key);
        const existing = index.get(key);
        if (existing) {
          existing.push(species);
        } else {
          index.set(key, [species]);
        }
      }
    }
    return index;
  }, [dexData, moveNameToId]);

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
      return (
        nameMatch && flagMatch && matchesMoveEditedFilter(move, editedFilter)
      );
    });
  }, [moves, query, activeFlags, editedFilter]);

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
            ? `${moves.length} moves`
            : `${filtered.length} of ${moves.length} moves`}
          <span className="tab-toolbar__edited" style={{ color: "var(--edited)" }}>
            {" · "}
            {editedCount} edited
            <span className="sr-only"> by the Ruleset</span>
          </span>
        </span>
        <button
          type="button"
          id="moves-new"
          className="btn btn--primary btn--new"
          onClick={() => setEditingNew(true)}
        >
          <span aria-hidden="true">+ </span>New move
        </button>
      </div>

      {moves.length === 0 ? (
        <EmptyView message="No moves yet. Build or regenerate the base snapshot, or create one." />
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
            <div
              id="moves-edited-filter"
              className="tab-segmented"
              role="group"
              aria-label="Filter by edited state"
            >
              {EDITED_FILTERS.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  id={`moves-edited-filter-${option.key}`}
                  className="tab-segmented__btn"
                  data-on={editedFilter === option.key}
                  aria-pressed={editedFilter === option.key}
                  onClick={() => setEditedFilter(option.key)}
                >
                  {option.label}
                </button>
              ))}
            </div>
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
                  <tr
                    key={move.chrooked_id}
                    id={`move-row-${move.chrooked_id}`}
                    data-edited={isMoveEdited(move)}
                    style={{ cursor: "pointer" }}
                    onClick={() => setSelected(move)}
                  >
                    <td className="tab-strong">
                      <EditedLed on={isMoveEdited(move)} />
                      {move.name}
                    </td>
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
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleFlag(flag);
                              }}
                            >
                              {flag}
                            </button>
                          ))}
                        </span>
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        id={`move-row-edit-${move.chrooked_id}`}
                        className="tab-row-edit"
                        aria-label={`Edit ${move.name}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditDirect(move);
                        }}
                      >
                        <FontAwesomeIcon icon={faPencil} aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

      {/* Read-only detail sidebar — opens when a row is clicked. */}
      {selected !== null && (
        <DetailSidebar
          entityKey={selected.chrooked_id}
          title={selected.name}
          edited={isMoveEdited(selected)}
          kindLabel="MOVE"
          tabs={[
            {
              id: "detail",
              label: "Detail",
              render: () => <MoveDetail move={selected} />,
            },
            {
              id: "learned-by",
              label: `Learned by (${(learnedByIndex.get(selected.chrooked_id) ?? []).length})`,
              render: () => (
                <ReverseLookupTab
                  species={learnedByIndex.get(selected.chrooked_id) ?? []}
                  rowIdPrefix="move-learner"
                  filterField="moves"
                  filterValue={selected.name}
                  onClose={() => setSelected(null)}
                />
              ),
            },
          ]}
          editView={
            <MoveEditor
              move={selected}
              onClose={() => setSelected(null)}
              onSaved={() => {
                reload();
                setSelected(null);
              }}
              embedded
            />
          }
          onClose={() => setSelected(null)}
        />
      )}

      {/* New move editor — opened directly without the read-only step. */}
      {editingNew && (
        <MoveEditor
          move={null}
          onClose={() => setEditingNew(false)}
          onSaved={() => {
            reload();
            setEditingNew(false);
          }}
        />
      )}

      {/* Per-row pencil → editor directly (skips the read-only sidebar). */}
      {editDirect !== null && (
        <MoveEditor
          move={editDirect}
          onClose={() => setEditDirect(null)}
          onSaved={() => {
            setEditDirect(null);
            reload();
          }}
        />
      )}
    </div>
  );
}
