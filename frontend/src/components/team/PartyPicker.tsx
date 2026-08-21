import { useRef } from "react";

type Props = {
  query: string;
  onQuery: (query: string) => void;
  /** How many species the pool currently shows — the honest count for a search
      that narrowed 1451 down to a handful. */
  resultCount: number;
  /** Enter on the field adds the pool's first result, so a team fills without
      leaving the keyboard. */
  onSubmit: () => void;
};

/**
 * The Team pool's search field. It narrows the card pool below it by name or dex
 * № — the same predicate the dex rail's search uses (`matchesQuery`) — and the
 * filter pills beside it are the dex's own filter builder. No dropdown: the pool
 * itself is the result list, so an overlay would only cover it.
 */
export function PartyPicker({ query, onQuery, resultCount, onSubmit }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="party-picker" id="party-picker">
      <div className="party-picker__field">
        <span className="party-picker__icon mono" aria-hidden="true">
          /
        </span>
        <input
          ref={inputRef}
          id="party-picker-input"
          type="search"
          className="party-picker__input"
          autoComplete="off"
          placeholder="Search species by name or №…"
          aria-label="Search the available species pool"
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              onSubmit();
            } else if (event.key === "Escape" && query !== "") {
              event.preventDefault();
              event.stopPropagation();
              onQuery("");
            }
          }}
        />
        <span className="party-picker__count mono" aria-live="polite">
          {resultCount}
        </span>
        {query !== "" && (
          <button
            type="button"
            className="party-picker__clear"
            aria-label="Clear search"
            onClick={() => {
              onQuery("");
              inputRef.current?.focus();
            }}
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}
