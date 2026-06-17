import { useMemo, useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faPencil } from "@fortawesome/free-solid-svg-icons";
import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import { useUrlState } from "../../hooks/useUrlState";
import { useEntityView, type EntityParamKeys } from "../../hooks/useEntityView";
import { isAbilityEdited } from "../../lib/format";
import { evalEntries } from "../../lib/filterEngine";
import {
  ABILITY_REGISTRY,
  ABILITY_SORTABLE,
  ABILITY_SORT_COLUMNS,
} from "../../lib/abilityRegistry";
import { abilityCodec } from "../../lib/abilityViewCodec";
import { stableMultiSort } from "../../lib/sortEngine";
import type { Ability, DexEntry } from "../../types";
import { EditedLed } from "../EditedLed";
import { ErrorView, EmptyView } from "../StatusView";
import { EntityControls } from "../filters/EntityControls";
import { AbilityEditor } from "../editors/AbilityEditor";
import { DetailSidebar } from "../sidebar/DetailSidebar";
import { AbilityDetail } from "../sidebar/AbilityDetail";
import { ReverseLookupTab } from "../sidebar/ReverseLookupTab";
import "./tabs.css";
import "../editors/editors.css";

/** The Abilities entity owns its own namespaced URL params (D3). */
const ABILITY_PARAM_KEYS: EntityParamKeys = {
  filter: "afilter",
  sort: "asort",
  hide: "ahide",
};

/** The Abilities tab at species-dex parity: the FULL merged list (base ⊕
    Ruleset) as a def-list with an edited-LED per row, the shared control stack
    (boolean filter builder + sort row + Reset all) driven by the ability
    registry — no columns control, since the list is a def-list (D5). */
export function AbilitiesTab() {
  const [view, update] = useUrlState();
  const [controls, setControls] = useEntityView(abilityCodec, ABILITY_PARAM_KEYS);
  // Swap the fetcher to the Target's backdrop (fork ⊕ Ruleset) when one is set;
  // otherwise read the base ⊕ Ruleset canon. Memoized by backdrop id so
  // useResource sees a stable fetcher and refetches only when the backdrop flips.
  const fetcher = useMemo(
    () => (view.backdrop ? api.targetAbilities(view.backdrop) : api.abilities),
    [view.backdrop],
  );
  // Dex fetcher mirrors the abilities fetcher swap: backdrop → target dex, else
  // canon. The merged dex carries per-species ability slots for the reverse index.
  const dexFetcher = useMemo(
    () => (view.backdrop ? api.targetDex(view.backdrop) : api.dex),
    [view.backdrop],
  );
  const { data, error, status, isLoading, reload } =
    useResource<Ability[]>(fetcher);
  const { data: dexData, reload: reloadDex } =
    useResource<DexEntry[]>(dexFetcher);
  /** "New ability" → editor directly (no read-only step for a new record). */
  const [editingNew, setEditingNew] = useState(false);
  /** Whether the open sidebar should land in edit mode — set true by the per-row
      pencil so it opens on the [Fields | Distribution] tabs, false by a row click
      (read-only first). */
  const [openInEdit, setOpenInEdit] = useState(false);

  const abilities = useMemo(() => data ?? [], [data]);

  // The open read-only sidebar is URL-addressable (#28): `view.selected` (the
  // shared `id=` param) names the ability. Species cross-links carry the DISPLAY
  // name; a row click writes the chrooked_id — resolve against BOTH, case-
  // insensitively, so either form opens the right record (and survives reload).
  const selected = useMemo((): Ability | null => {
    if (view.selected === null) return null;
    const key = view.selected.toLowerCase();
    return (
      abilities.find(
        (a) =>
          a.chrooked_id.toLowerCase() === key ||
          a.name.toLowerCase() === key,
      ) ?? null
    );
  }, [view.selected, abilities]);
  const openAbility = (ability: Ability) =>
    update({ selected: ability.chrooked_id });
  const closeAbility = () => update({ selected: null });
  const editedCount = useMemo(
    () => abilities.filter(isAbilityEdited).length,
    [abilities],
  );

  // name→chrooked_id map built from the loaded abilities list so we can normalize
  // ability slot values (which store display names, e.g. "Snow Warning") to the
  // stable chrooked_id key ("snowwarning") the AbilityEditor lookup uses.
  const abilityNameToId = useMemo((): Map<string, string> => {
    const map = new Map<string, string>();
    for (const a of abilities) {
      map.set(a.name, a.chrooked_id);
    }
    return map;
  }, [abilities]);

  // Reverse index: chrooked_id → species that have it in ANY slot (primary,
  // secondary, hidden). Built from the merged dex so overrides are applied (ac3).
  // Keyed by chrooked_id (not display name) to match the AbilityEditor lookup.
  const usedByIndex = useMemo((): Map<string, DexEntry[]> => {
    if (!dexData) return new Map();
    const index = new Map<string, DexEntry[]>();
    for (const species of dexData) {
      const slots = [
        species.abilities.primary,
        species.abilities.secondary,
        species.abilities.hidden,
      ];
      const seen = new Set<string>();
      for (const slot of slots) {
        if (slot !== null) {
          // Ability slots store display names; normalize to chrooked_id via the abilities list.
          const key = abilityNameToId.get(slot) ?? slot;
          if (!seen.has(key)) {
            seen.add(key);
            const existing = index.get(key);
            if (existing) {
              existing.push(species);
            } else {
              index.set(key, [species]);
            }
          }
        }
      }
    }
    return index;
  }, [dexData, abilityNameToId]);

  // Live name-filter from the single rail search (ac9): `view.query` is the
  // shared search text, applied by name before the boolean filter. Enter in the
  // rail promotes the term to a Name pill on `afilter` (handled in App).
  const railQuery = view.query.trim().toLowerCase();
  // The shared rail "Edited only" flag (ac12) ANDs with the query + builder
  // filter, exactly like the dex.
  const editedOnly = view.editedOnly;
  const filtered = useMemo(() => {
    let list = abilities.filter((a) =>
      evalEntries(ABILITY_REGISTRY, a, controls.filter),
    );
    if (editedOnly) list = list.filter(isAbilityEdited);
    if (railQuery === "") return list;
    return list.filter((a) => a.name.toLowerCase().includes(railQuery));
  }, [abilities, controls.filter, railQuery, editedOnly]);
  const rows = useMemo(
    () => stableMultiSort(filtered, controls.sort, ABILITY_SORT_COLUMNS),
    [filtered, controls.sort],
  );

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading) return <p className="tab-loading">Loading abilities…</p>;

  return (
    <div className="tab" id="tab-abilities">
      <div className="tab-toolbar">
        <span className="tab-toolbar__title">
          {rows.length === abilities.length
            ? `${abilities.length} abilities`
            : `${rows.length} of ${abilities.length} abilities`}
          <span className="tab-toolbar__edited" style={{ color: "var(--edited)" }}>
            {" · "}
            {editedCount} edited
            <span className="sr-only"> by the Ruleset</span>
          </span>
        </span>
        <button
          type="button"
          id="abilities-new"
          className="btn btn--primary btn--new"
          onClick={() => setEditingNew(true)}
        >
          <span aria-hidden="true">+ </span>New ability
        </button>
      </div>

      {abilities.length === 0 ? (
        <EmptyView message="No abilities yet. Build or regenerate the base snapshot, or create one." />
      ) : (
        <>
          <EntityControls
            idPrefix="abilc"
            ariaLabel="Abilities view controls"
            defs={ABILITY_REGISTRY.defs}
            sortable={ABILITY_SORTABLE}
            columns={[]}
            filter={controls.filter}
            sort={controls.sort}
            hidden={controls.hidden}
            onChange={setControls}
          />

          {rows.length === 0 ? (
            <EmptyView message="No abilities match the current filter." />
          ) : (
            <dl className="tab-deflist">
              {rows.map((ability) => (
                <div
                  key={ability.chrooked_id}
                  id={`ability-row-${ability.chrooked_id}`}
                  className="tab-deflist__item"
                  data-edited={isAbilityEdited(ability)}
                  style={{ cursor: "pointer" }}
                  onClick={() => {
                    openAbility(ability);
                    setOpenInEdit(false);
                  }}
                >
                  <div className="tab-deflist__head">
                    <dt className="tab-strong">
                      <EditedLed on={isAbilityEdited(ability)} />
                      {ability.name}
                    </dt>
                    <button
                      type="button"
                      id={`ability-row-edit-${ability.chrooked_id}`}
                      className="tab-row-edit"
                      aria-label={`Edit ${ability.name}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        openAbility(ability);
                        setOpenInEdit(true);
                      }}
                    >
                      <FontAwesomeIcon icon={faPencil} aria-hidden="true" />
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
        </>
      )}

      {/* Read-only detail sidebar — opens when a row is clicked. */}
      {selected !== null && (
        <DetailSidebar
          entityKey={selected.chrooked_id}
          title={selected.name}
          edited={isAbilityEdited(selected)}
          kindLabel="ABILITY"
          tabs={[
            {
              id: "detail",
              label: "Detail",
              render: () => <AbilityDetail ability={selected} />,
            },
            {
              id: "used-by",
              label: `Used by (${(usedByIndex.get(selected.chrooked_id) ?? []).length})`,
              // Read-mode reverse tab is navigate-only (D7) — readOnly forces the
              // browse list with no edit affordances; editing lives behind the
              // pencil's Distribution edit tab below.
              render: () => (
                <ReverseLookupTab
                  species={usedByIndex.get(selected.chrooked_id) ?? []}
                  dexData={dexData ?? []}
                  rowIdPrefix="ability-user"
                  entityKind="ability"
                  filterField="abilities"
                  entityName={selected.name}
                  readOnly
                  onSaved={() => {
                    reloadDex();
                    reload();
                  }}
                  onClose={() => closeAbility()}
                />
              ),
            },
          ]}
          editTabs={[
            {
              id: "fields",
              label: "Fields",
              render: () => (
                <AbilityEditor
                  ability={selected}
                  onClose={() => closeAbility()}
                  onSaved={() => {
                    reload();
                    closeAbility();
                  }}
                  embedded
                />
              ),
            },
            {
              id: "distribution",
              label: "Distribution",
              // Distribution edit tab: the staged used-by editor. Backdrop
              // (read-only fork preview) disables editing per ac5/D5.
              render: () => (
                <ReverseLookupTab
                  species={usedByIndex.get(selected.chrooked_id) ?? []}
                  dexData={dexData ?? []}
                  rowIdPrefix="ability-user"
                  entityKind="ability"
                  filterField="abilities"
                  entityName={selected.name}
                  readOnly={view.backdrop !== null}
                  onSaved={() => {
                    reloadDex();
                    reload();
                  }}
                  onClose={() => closeAbility()}
                />
              ),
            },
          ]}
          initialEditing={openInEdit}
          onClose={() => closeAbility()}
        />
      )}

      {/* New ability editor — opened directly without the read-only step. */}
      {editingNew && (
        <AbilityEditor
          ability={null}
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
