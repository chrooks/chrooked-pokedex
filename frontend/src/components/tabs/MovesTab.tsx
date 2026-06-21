import { useMemo, useState } from "react";
import { PokeballSpinner } from "../PokeballSpinner";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faPencil } from "@fortawesome/free-solid-svg-icons";
import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import { useUrlState } from "../../hooks/useUrlState";
import { useEntityView, type EntityParamKeys } from "../../hooks/useEntityView";
import { isMoveEdited } from "../../lib/format";
import { evalEntries } from "../../lib/filterEngine";
import { MOVE_REGISTRY } from "../../lib/moveRegistry";
import {
  MOVE_COLUMNS,
  MOVE_SORT_COLUMNS,
  type MoveColumnKey,
} from "../../lib/moveColumns";
import { moveCodec } from "../../lib/moveViewCodec";
import { stableMultiSort, type SortKey } from "../../lib/sortEngine";
import type { DexEntry, Move } from "../../types";
import { EditedLed } from "../EditedLed";
import { TypeChip } from "../TypeChip";
import { ErrorView, EmptyView } from "../StatusView";
import { EntityControls } from "../filters/EntityControls";
import { MoveEditor } from "../editors/MoveEditor";
import { DetailSidebar } from "../sidebar/DetailSidebar";
import { MoveDetail } from "../sidebar/MoveDetail";
import { ReverseLookupTab } from "../sidebar/ReverseLookupTab";
import "./tabs.css";
import "../editors/editors.css";

/** The Moves entity owns its own namespaced URL params (D3) so its control state
    never bleeds into the dex or Abilities. */
const MOVE_PARAM_KEYS: EntityParamKeys = {
  filter: "mfilter",
  sort: "msort",
  hide: "mhide",
};

const SORTABLE = MOVE_COLUMNS.filter((c) => c.sortable).map((c) => ({
  key: c.key,
  label: c.label,
}));
const TOGGLEABLE = MOVE_COLUMNS.filter((c) => !c.locked).map((c) => ({
  key: c.key,
  label: c.label,
}));

/** The Moves tab at species-dex parity: the FULL merged list (base ⊕ Ruleset)
    with an edited-LED per row, the shared dex-parity control stack (boolean
    filter builder, sort row, columns toggle, Reset all) driven by the move
    registry, and per-Target backdrop awareness. */
type MovesTabProps = {
  backdropTargetId?: string | null;
};

export function MovesTab({ backdropTargetId }: MovesTabProps) {
  const [view, update] = useUrlState();
  const [controls, setControls] = useEntityView(moveCodec, MOVE_PARAM_KEYS);
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
  const { data: dexData, reload: reloadDex } =
    useResource<DexEntry[]>(dexFetcher);
  /** "New move" → editor directly (no read-only step for a record not yet created). */
  const [editingNew, setEditingNew] = useState(false);
  /** Whether the open sidebar should land in edit mode — set true by the per-row
      pencil so it opens on the [Fields | Distribution] tabs, false by a row click. */
  const [openInEdit, setOpenInEdit] = useState(false);

  const moves = useMemo(() => data ?? [], [data]);

  // The open read-only sidebar is URL-addressable (#28): `view.selected` (the
  // shared `id=` param) names the move. Species cross-links carry the DISPLAY
  // name; a row click writes the chrooked_id — so resolve against BOTH, case-
  // insensitively, and either form opens the right record (and survives reload).
  const selected = useMemo((): Move | null => {
    if (view.selected === null) return null;
    const key = view.selected.toLowerCase();
    return (
      moves.find(
        (m) =>
          m.chrooked_id.toLowerCase() === key ||
          m.name.toLowerCase() === key,
      ) ?? null
    );
  }, [view.selected, moves]);
  const openMove = (move: Move) => update({ selected: move.chrooked_id });
  const closeMove = () => update({ selected: null });
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

  const hiddenSet = useMemo(
    () => new Set(controls.hidden as MoveColumnKey[]),
    [controls.hidden],
  );

  // Live name-filter from the single rail search (ac9): `view.query` is the
  // shared search text, applied by name before the boolean filter. Enter in the
  // rail promotes the term to a Name pill on `mfilter` (handled in App).
  const railQuery = view.query.trim().toLowerCase();
  // The shared rail "Edited only" flag (ac12) ANDs with the query + builder
  // filter, exactly like the dex.
  const editedOnly = view.editedOnly;
  const filtered = useMemo(() => {
    let list = moves.filter((move) =>
      evalEntries(MOVE_REGISTRY, move, controls.filter),
    );
    if (editedOnly) list = list.filter(isMoveEdited);
    if (railQuery === "") return list;
    return list.filter((move) => move.name.toLowerCase().includes(railQuery));
  }, [moves, controls.filter, railQuery, editedOnly]);
  const rows = useMemo(
    () => stableMultiSort(filtered, controls.sort, MOVE_SORT_COLUMNS),
    [filtered, controls.sort],
  );

  // Clicking a sortable header drives the same multi-key sort state: a fresh
  // click sets that column asc; clicking the active primary flips direction;
  // shift-click appends a secondary key (dex-parity behavior).
  function onHeaderSort(field: MoveColumnKey, append: boolean) {
    const existing = controls.sort.find((s) => s.field === field);
    if (append) {
      if (existing) {
        setControls({
          sort: controls.sort.map((s) =>
            s.field === field
              ? { ...s, direction: s.direction === "asc" ? "desc" : "asc" }
              : s,
          ),
        });
      } else if (controls.sort.length < 3) {
        setControls({ sort: [...controls.sort, { field, direction: "asc" }] });
      }
      return;
    }
    const next: SortKey =
      existing && existing.direction === "asc"
        ? { field, direction: "desc" }
        : { field, direction: "asc" };
    setControls({ sort: [next] });
  }

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading)
    return (
      <div className="tab-loading">
        <PokeballSpinner label="Loading moves…" />
      </div>
    );

  return (
    <div className="tab" id="tab-moves">
      <div className="tab-toolbar">
        <span className="tab-toolbar__title">
          {rows.length === moves.length
            ? `${moves.length} moves`
            : `${rows.length} of ${moves.length} moves`}
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
          <EntityControls
            idPrefix="movesc"
            ariaLabel="Moves view controls"
            defs={MOVE_REGISTRY.defs}
            sortable={SORTABLE}
            columns={TOGGLEABLE}
            filter={controls.filter}
            sort={controls.sort}
            hidden={controls.hidden}
            onChange={setControls}
          />

          {rows.length === 0 ? (
            <EmptyView message="No moves match the current filter." />
          ) : (
            <table className="tab-table">
              <thead>
                <tr>
                  <th>Move</th>
                  {!hiddenSet.has("type") && <SortHeader col="type" sort={controls.sort} onSort={onHeaderSort} />}
                  {!hiddenSet.has("category") && <SortHeader col="category" sort={controls.sort} onSort={onHeaderSort} />}
                  {!hiddenSet.has("power") && <SortHeader col="power" numeric sort={controls.sort} onSort={onHeaderSort} />}
                  {!hiddenSet.has("accuracy") && <SortHeader col="accuracy" numeric sort={controls.sort} onSort={onHeaderSort} />}
                  {!hiddenSet.has("pp") && <SortHeader col="pp" numeric sort={controls.sort} onSort={onHeaderSort} />}
                  {!hiddenSet.has("flags") && <th>Tags</th>}
                  <th aria-label="Edit" />
                </tr>
              </thead>
              <tbody>
                {rows.map((move) => (
                  <tr
                    key={move.chrooked_id}
                    id={`move-row-${move.chrooked_id}`}
                    data-edited={isMoveEdited(move)}
                    style={{ cursor: "pointer" }}
                    onClick={() => {
                      openMove(move);
                      setOpenInEdit(false);
                    }}
                  >
                    <td className="tab-strong">
                      <EditedLed on={isMoveEdited(move)} />
                      {move.name}
                    </td>
                    {!hiddenSet.has("type") && (
                      <td>
                        <TypeChip type={move.type} variant="code" />
                      </td>
                    )}
                    {!hiddenSet.has("category") && <td className="tab-dim">{move.category}</td>}
                    {!hiddenSet.has("power") && <td className="tab-num mono">{move.power ?? "—"}</td>}
                    {!hiddenSet.has("accuracy") && <td className="tab-num mono">{move.accuracy ?? "—"}</td>}
                    {!hiddenSet.has("pp") && <td className="tab-num mono">{move.pp ?? "—"}</td>}
                    {!hiddenSet.has("flags") && (
                      <td>
                        {(move.flags ?? []).length === 0 ? (
                          <span className="tab-faint">—</span>
                        ) : (
                          <span className="move-tags">
                            {(move.flags ?? []).map((flag) => (
                              <span key={flag} className="move-tag">
                                {flag}
                              </span>
                            ))}
                          </span>
                        )}
                      </td>
                    )}
                    <td>
                      <button
                        type="button"
                        id={`move-row-edit-${move.chrooked_id}`}
                        className="tab-row-edit"
                        aria-label={`Edit ${move.name}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          openMove(move);
                          setOpenInEdit(true);
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
              // Read-mode reverse tab is navigate-only (D7) — readOnly forces the
              // browse list with no edit affordances; editing lives behind the
              // pencil's Distribution edit tab below.
              render: () => (
                <ReverseLookupTab
                  species={learnedByIndex.get(selected.chrooked_id) ?? []}
                  dexData={dexData ?? []}
                  rowIdPrefix="move-learner"
                  entityKind="move"
                  filterField="moves"
                  entityName={selected.name}
                  readOnly
                  backdropTargetId={backdropTargetId}
                  onSaved={() => {
                    reloadDex();
                    reload();
                  }}
                  onClose={() => closeMove()}
                />
              ),
            },
          ]}
          editTabs={[
            {
              id: "fields",
              label: "Fields",
              render: () => (
                <MoveEditor
                  move={selected}
                  onClose={() => closeMove()}
                  onSaved={() => {
                    reload();
                    closeMove();
                  }}
                  embedded
                />
              ),
            },
            {
              id: "distribution",
              label: "Distribution",
              // Distribution edit tab: the staged learned-by editor. Backdrop
              // (read-only fork preview) disables editing per ac5/D5.
              render: () => (
                <ReverseLookupTab
                  species={learnedByIndex.get(selected.chrooked_id) ?? []}
                  dexData={dexData ?? []}
                  rowIdPrefix="move-learner"
                  entityKind="move"
                  filterField="moves"
                  entityName={selected.name}
                  readOnly={view.backdrop !== null}
                  backdropTargetId={backdropTargetId}
                  onSaved={() => {
                    reloadDex();
                    reload();
                  }}
                  onClose={() => closeMove()}
                />
              ),
            },
          ]}
          initialEditing={openInEdit}
          onClose={() => closeMove()}
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
    </div>
  );
}

const HEADER_LABEL: Record<MoveColumnKey, string> = {
  led: "",
  name: "Move",
  type: "Type",
  category: "Cat",
  power: "Pow",
  accuracy: "Acc",
  pp: "PP",
  flags: "Tags",
};

type SortHeaderProps = {
  col: MoveColumnKey;
  numeric?: boolean;
  sort: SortKey[];
  onSort: (field: MoveColumnKey, append: boolean) => void;
};

/** A clickable, sort-aware column header. Click sorts (or flips); shift-click
    appends a secondary key. Shows the active direction arrow. */
function SortHeader({ col, numeric, sort, onSort }: SortHeaderProps) {
  const active = sort.find((s) => s.field === col);
  const arrow = active ? (active.direction === "asc" ? " ▲" : " ▼") : "";
  return (
    <th className={numeric ? "tab-num" : undefined}>
      <button
        type="button"
        id={`moves-th-${col}`}
        className="tab-th-sort"
        aria-label={`Sort by ${HEADER_LABEL[col]}${active ? `, ${active.direction}ending` : ""}`}
        onClick={(e) => onSort(col, e.shiftKey)}
      >
        {HEADER_LABEL[col]}
        <span aria-hidden="true">{arrow}</span>
      </button>
    </th>
  );
}
