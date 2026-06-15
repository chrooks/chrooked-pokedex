import { useMemo, useState } from "react";
import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import { useUrlState } from "../../hooks/useUrlState";
import {
  isAbilityEdited,
  matchesAbilityEditedFilter,
  type AbilityEditedFilter,
} from "../../lib/format";
import type { Ability } from "../../types";
import { EditedLed } from "../EditedLed";
import { ErrorView, EmptyView } from "../StatusView";
import { AbilityEditor } from "../editors/AbilityEditor";
import "./tabs.css";
import "../editors/editors.css";

/** The three Edited-filter segments, mirroring the dex's edited toggle but with
    an explicit base-only option for browsing untouched abilities. */
const EDITED_FILTERS: { key: AbilityEditedFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "edited", label: "Edited" },
  { key: "base", label: "Not edited" },
];

/** The Abilities tab at species-dex parity: the FULL merged list (base ⊕
    Ruleset) with an edited-LED per row and an Edited filter, a base→now diff in
    the editor, and per-Target backdrop awareness. In backdrop mode the list
    swaps to the selected fork's abilities ⊕ Ruleset. */
export function AbilitiesTab() {
  const [view] = useUrlState();
  // Swap the fetcher to the Target's backdrop (fork ⊕ Ruleset) when one is set;
  // otherwise read the base ⊕ Ruleset canon. Memoized by backdrop id so
  // useResource sees a stable fetcher and refetches only when the backdrop flips.
  const fetcher = useMemo(
    () => (view.backdrop ? api.targetAbilities(view.backdrop) : api.abilities),
    [view.backdrop],
  );
  const { data, error, status, isLoading, reload } =
    useResource<Ability[]>(fetcher);
  const [editing, setEditing] = useState<{ ability: Ability | null } | null>(
    null,
  );
  const [query, setQuery] = useState("");
  const [editedFilter, setEditedFilter] = useState<AbilityEditedFilter>("all");

  const abilities = useMemo(() => data ?? [], [data]);
  const editedCount = useMemo(
    () => abilities.filter(isAbilityEdited).length,
    [abilities],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return abilities.filter((ability) => {
      const nameMatch = q === "" || ability.name.toLowerCase().includes(q);
      return nameMatch && matchesAbilityEditedFilter(ability, editedFilter);
    });
  }, [abilities, query, editedFilter]);

  if (error !== null) return <ErrorView message={error} status={status} />;
  if (isLoading) return <p className="tab-loading">Loading abilities…</p>;

  return (
    <div className="tab" id="tab-abilities">
      <div className="tab-toolbar">
        <span className="tab-toolbar__title">
          {filtered.length === abilities.length
            ? `${abilities.length} abilities`
            : `${filtered.length} of ${abilities.length} abilities`}
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
          onClick={() => setEditing({ ability: null })}
        >
          <span aria-hidden="true">+ </span>New ability
        </button>
      </div>

      {abilities.length === 0 ? (
        <EmptyView message="No abilities yet. Build or regenerate the base snapshot, or create one." />
      ) : (
        <>
          <div className="tab-filterbar">
            <input
              type="search"
              className="tab-search"
              placeholder="Search abilities by name"
              aria-label="Search abilities by name"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div
              id="abilities-edited-filter"
              className="tab-segmented"
              role="group"
              aria-label="Filter by edited state"
            >
              {EDITED_FILTERS.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  id={`abilities-edited-filter-${option.key}`}
                  className="tab-segmented__btn"
                  data-on={editedFilter === option.key}
                  aria-pressed={editedFilter === option.key}
                  onClick={() => setEditedFilter(option.key)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {filtered.length === 0 ? (
            <EmptyView message="No abilities match the current filter." />
          ) : (
            <dl className="tab-deflist">
              {filtered.map((ability) => (
                <div
                  key={ability.chrooked_id}
                  id={`ability-row-${ability.chrooked_id}`}
                  className="tab-deflist__item"
                  data-edited={isAbilityEdited(ability)}
                >
                  <div className="tab-deflist__head">
                    <dt className="tab-strong">
                      <EditedLed on={isAbilityEdited(ability)} />
                      {ability.name}
                    </dt>
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
        </>
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
