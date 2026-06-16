/* A tab panel listing species that reference a given move or ability, with
   sprite thumbnails and click-to-navigate behaviour. Used by MovesTab and
   AbilitiesTab as the second tab inside DetailSidebar. */

import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faFilter } from "@fortawesome/free-solid-svg-icons";
import { useUrlState } from "../../hooks/useUrlState";
import { spriteUrl } from "../../lib/sprites";
import type { DexEntry } from "../../types";
import "../editors/editors.css";

type Props = {
  /** Species to display — already deduplicated by the caller's reverse index. */
  species: DexEntry[];
  /** Button id prefix, e.g. "move-learner" → id="move-learner-bulbasaur". */
  rowIdPrefix: string;
  /** The filter field that corresponds to this reverse list ("moves" or "abilities"). */
  filterField: "moves" | "abilities";
  /** The display name of the move/ability being viewed — used as the filter value. */
  filterValue: string;
  /** Called after navigating to a species so the sidebar can close. */
  onClose: () => void;
};

export function ReverseLookupTab({
  species,
  rowIdPrefix,
  filterField,
  filterValue,
  onClose,
}: Props) {
  const [, updateView] = useUrlState();

  function handleClick(entry: DexEntry) {
    updateView({ kind: "dex", selected: entry.chrooked_id });
    onClose();
  }

  function handleFilterInDex() {
    const entry = {
      kind: "filter" as const,
      id: crypto.randomUUID(),
      field: filterField,
      value: filterValue,
      connector: "AND" as const,
      negated: false,
    };
    updateView({ kind: "dex", filter: [entry], selected: null, query: "" });
    onClose();
  }

  return (
    <div id="reverse-lookup-tab" className="editor-section" style={{ border: "none" }}>
      <div className="reverse-lookup__header">
        <span className="reverse-lookup__count">
          ({species.length} species)
        </span>
        {species.length > 0 && (
          <button
            type="button"
            id="reverse-filter-in-dex"
            className="reverse-lookup__filter-btn"
            onClick={handleFilterInDex}
            title={`Filter dex by ${filterValue}`}
          >
            <FontAwesomeIcon icon={faFilter} aria-hidden="true" />
            {" Filter in dex"}
          </button>
        )}
      </div>

      {species.length === 0 ? (
        <p className="reverse-lookup__empty">No species found.</p>
      ) : (
        <ul id="reverse-lookup-list" className="reverse-lookup__list" style={{ maxHeight: "none" }}>
          {species.map((entry) => {
            const src = spriteUrl(entry.chrooked_id, entry.dex);
            return (
              <li key={entry.chrooked_id}>
                <button
                  type="button"
                  id={`${rowIdPrefix}-${entry.chrooked_id}`}
                  className="reverse-lookup__species-btn"
                  onClick={() => handleClick(entry)}
                >
                  {src !== null && src !== undefined && (
                    <img
                      src={src}
                      alt={entry.name}
                      width={32}
                      height={32}
                      decoding="async"
                      loading="lazy"
                      style={{ verticalAlign: "middle", marginRight: "var(--space-1)" }}
                    />
                  )}
                  {entry.name}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
