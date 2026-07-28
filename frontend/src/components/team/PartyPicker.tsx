import { useId, useMemo, useRef, useState } from "react";
import type { DexEntry } from "../../types";
import { DexSprite } from "../DexSprite";
import { TypeChip } from "../TypeChip";

type Props = {
  entries: readonly DexEntry[];
  /** chrooked_ids already on the team — their options grey out (no duplicates).
      Note: the picker stays enabled even at 6/6; a fresh pick then opens the
      full-team replace dialog (ac10), so the input never dead-ends. */
  partyIds: ReadonlySet<string>;
  onAdd: (id: string) => void;
  backdropTargetId: string | null;
};

/** How many matches the dropdown shows at once — enough to scan, capped so the
    list never runs off the screen. */
const MAX_RESULTS = 40;

/**
 * A search-to-add combobox over the whole dex. Typing filters species by name;
 * each result carries its sprite and type chips so the pick is a real Pokédex
 * choice, not a bare name. Arrow keys move the active option, Enter adds it,
 * Escape closes — the input keeps focus after an add so a team fills in one flow.
 */
export function PartyPicker({ entries, partyIds, onAdd, backdropTargetId }: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listboxId = useId();

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (q === "") return [];
    return entries
      .filter((entry) => entry.name.toLowerCase().includes(q))
      .slice(0, MAX_RESULTS);
  }, [entries, query]);

  const showList = open && results.length > 0;

  function add(entry: DexEntry) {
    // Already on the team: no duplicates. The option is styled disabled, so this
    // guards the keyboard path (Enter on a duplicate is a no-op).
    if (partyIds.has(entry.chrooked_id)) return;
    onAdd(entry.chrooked_id);
    setQuery("");
    setActive(0);
    setOpen(false);
    inputRef.current?.focus();
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(results.length - 1, i + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (event.key === "Enter") {
      if (showList && results[active]) {
        event.preventDefault();
        add(results[active]);
      }
    } else if (event.key === "Escape") {
      if (open) {
        event.preventDefault();
        event.stopPropagation();
        setOpen(false);
      }
    }
  }

  const activeId = showList ? `${listboxId}-opt-${active}` : undefined;

  return (
    <div className="party-picker" id="party-picker">
      <div className="party-picker__field">
        <span className="party-picker__icon mono" aria-hidden="true">
          +
        </span>
        <input
          ref={inputRef}
          id="party-picker-input"
          type="text"
          className="party-picker__input"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listboxId}
          aria-activedescendant={activeId}
          aria-autocomplete="list"
          autoComplete="off"
          placeholder="Add a Pokémon to your team…"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            setActive(0);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
        {query !== "" && (
          <button
            type="button"
            className="party-picker__clear"
            aria-label="Clear search"
            // Fire before the input's blur so the click isn't swallowed.
            onMouseDown={(event) => {
              event.preventDefault();
              setQuery("");
              inputRef.current?.focus();
            }}
          >
            ✕
          </button>
        )}
      </div>

      {showList && (
        <ul className="party-picker__list" id={listboxId} role="listbox" aria-label="Search results">
          {results.map((entry, index) => {
            const duplicate = partyIds.has(entry.chrooked_id);
            return (
              <li
                key={entry.chrooked_id}
                id={`${listboxId}-opt-${index}`}
                role="option"
                aria-selected={index === active}
                aria-disabled={duplicate}
                className="party-picker__option"
                data-active={index === active}
                data-duplicate={duplicate}
                // mousedown (not click) so the option is chosen before the input blurs.
                onMouseDown={(event) => {
                  event.preventDefault();
                  add(entry);
                }}
                onMouseEnter={() => setActive(index)}
              >
                <DexSprite
                  chrookedId={entry.chrooked_id}
                  dex={entry.dex}
                  name={entry.name}
                  backdropTargetId={backdropTargetId}
                  size={36}
                />
                <span className="party-picker__option-name">{entry.name}</span>
                {duplicate ? (
                  <span className="party-picker__option-tag">On team</span>
                ) : (
                  <span className="party-picker__option-types">
                    {entry.types.map((type) => (
                      <TypeChip key={type} type={type} variant="code" />
                    ))}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
