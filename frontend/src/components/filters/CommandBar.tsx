import { useEffect, useMemo, useRef, useState } from "react";
import type { FilterDef, FilterEntry } from "../../lib/filterEngine";
import {
  formatQuery,
  parseQuery,
  parseTerm,
  suggest,
  tokenize,
  type Suggestion,
} from "../../lib/filterQuery";

type Props = {
  defs: FilterDef[];
  idPrefix: string;
  filter: FilterEntry[];
  onChange: (filter: FilterEntry[]) => void;
  /** Leave the command bar and go back to the query line. */
  onExit: () => void;
};

const MAX_ROWS = 7;

function uid(): string {
  return crypto.randomUUID();
}

/**
 * The command bar: the same expression as one typed query. Committed terms
 * render as tokens ahead of the caret and the input holds ONLY the term being
 * typed, so a term is a token or text but never both at once.
 *
 * The bar owns its text while focused and re-derives it from the filter
 * otherwise — that way the query line and the bar stay two faces of one state
 * without either fighting the other for the caret.
 */
export function CommandBar({ defs, idPrefix, filter, onChange, onExit }: Props) {
  /** The committed terms, as text. The filter is derived from these. */
  const [terms, setTerms] = useState<string[]>(() => queryTerms(filter, defs));
  const [partial, setPartial] = useState("");
  const [active, setActive] = useState(0);
  /** The dropdown only means anything while the input owns the keys — a blurred
      bar showing "↵ accept" is a lie, and Enter/Escape would go to the browser. */
  const [focused, setFocused] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const dirty = useRef(false);

  // Adopt outside edits (a saved expression applied, Reset all) but never
  // clobber what the human is mid-way through typing.
  useEffect(() => {
    if (dirty.current) {
      dirty.current = false;
      return;
    }
    setTerms(queryTerms(filter, defs));
  }, [filter, defs]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Escape leaves command mode from anywhere, not just the input — otherwise a
  // stray click parks focus on the body and Escape falls through to the browser
  // (exiting fullscreen on macOS instead of exiting the mode).
  useEffect(() => {
    function onDocKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      onExit();
    }
    document.addEventListener("keydown", onDocKey);
    return () => document.removeEventListener("keydown", onDocKey);
  }, [onExit]);

  const rows = useMemo(() => suggest(partial, defs).slice(0, MAX_ROWS), [partial, defs]);
  const problems = useMemo(
    () =>
      terms
        .map((term) => ({ term, parsed: parseTerm(term, defs) }))
        .filter((t) => !isStructural(t.term) && !t.parsed.ok),
    [terms, defs],
  );

  /** Push the committed terms through the parser and up as the new filter. */
  function commitTerms(next: string[]) {
    setTerms(next);
    dirty.current = true;
    onChange(parseQuery(next.join(" "), defs, uid).entries);
  }

  function commitPartial(text = partial) {
    const trimmed = text.trim();
    if (trimmed === "") return;
    commitTerms([...terms, ...tokenize(trimmed)]);
    setPartial("");
    setActive(0);
  }

  function accept(row: Suggestion) {
    // A completion ending in a space is a whole term; anything else is a stem
    // that stays in the box for the value to be typed.
    if (row.complete.endsWith(" ")) commitPartial(row.complete);
    else setPartial(row.complete);
    setActive(0);
    inputRef.current?.focus();
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" && rows.length) {
      event.preventDefault();
      setActive((i) => (i + 1) % rows.length);
    } else if (event.key === "ArrowUp" && rows.length) {
      event.preventDefault();
      setActive((i) => (i - 1 + rows.length) % rows.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (rows[active]) accept(rows[active]);
      else commitPartial();
    } else if (event.key === "Backspace" && partial === "" && terms.length) {
      // Backspace at the start pulls the last token back in to edit, rather
      // than deleting a whole term the caret is not on.
      event.preventDefault();
      setPartial(terms[terms.length - 1]);
      commitTerms(terms.slice(0, -1));
    }
    // Escape is handled at the document level so it works even when the input
    // has lost focus.
  }

  return (
    <div className="cmdbar" id={`${idPrefix}-cmdbar`}>
      <div
        className="cmdbar__field"
        onClick={(e) => {
          if (e.target === e.currentTarget) inputRef.current?.focus();
        }}
      >
        <span className="cmdbar__slash" aria-hidden="true">
          /
        </span>

        {terms.map((term, index) => (
          <Token
            key={`${term}-${index}`}
            term={term}
            defs={defs}
            onRemove={() => commitTerms(terms.filter((_, i) => i !== index))}
          />
        ))}

        <input
          ref={inputRef}
          id={`${idPrefix}-cmdbar-input`}
          className="cmdbar__input"
          type="text"
          role="combobox"
          aria-expanded={focused && rows.length > 0}
          aria-autocomplete="list"
          aria-controls={`${idPrefix}-cmdbar-list`}
          aria-label="Filter query"
          placeholder={terms.length === 0 ? "field:value — try name:fros" : ""}
          spellCheck={false}
          autoComplete="off"
          value={partial}
          onChange={(e) => {
            // A space ends the term, the way it does in a shell.
            if (/\s$/.test(e.target.value)) commitPartial(e.target.value);
            else {
              setPartial(e.target.value);
              setActive(0);
            }
          }}
          onKeyDown={onKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
        />
      </div>

      {focused && rows.length > 0 && (
        <ul className="cmdbar__drop" id={`${idPrefix}-cmdbar-list`} role="listbox">
          {rows.map((row, index) => (
            <li key={row.code} role="option" aria-selected={index === active}>
              <button
                type="button"
                className="cmdbar__row"
                data-active={index === active || undefined}
                // mousedown so the row is chosen before the input blurs.
                onMouseDown={(e) => {
                  e.preventDefault();
                  accept(row);
                }}
                onMouseEnter={() => setActive(index)}
              >
                <code>{row.code}</code>
                <span className="cmdbar__hint">{row.hint}</span>
              </button>
            </li>
          ))}
          <li className="cmdbar__foot">
            <span>
              <kbd>↑↓</kbd> move
            </span>
            <span>
              <kbd>↵</kbd> accept
            </span>
            <span>
              <kbd>-</kbd> exclude
            </span>
            <span>
              <kbd>or</kbd> widen
            </span>
            <span>
              <kbd>esc</kbd> back to tokens
            </span>
          </li>
        </ul>
      )}

      {problems.length > 0 && (
        <p className="cmdbar__problems" role="status">
          {problems.map((p) => (
            <span key={p.term} className="cmdbar__problem">
              <code>{p.term}</code> — {!p.parsed.ok && p.parsed.reason}
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

/** `or` / `and` / parens carry structure, not a predicate — they are never a
    problem to report, and they render as a quiet joiner rather than a token. */
function isStructural(term: string): boolean {
  const lower = term.toLowerCase();
  return lower === "or" || lower === "and" || term === "(" || term === ")";
}

function Token({
  term,
  defs,
  onRemove,
}: {
  term: string;
  defs: FilterDef[];
  onRemove: () => void;
}) {
  if (isStructural(term)) {
    return (
      <span className="cmdbar__join" data-or={term.toLowerCase() === "or" || undefined}>
        {term}
      </span>
    );
  }

  const parsed = parseTerm(term, defs);
  const negated = term.startsWith("-");
  const body = negated ? term.slice(1) : term;
  const cut = body.search(/[:><=]/);
  const key = cut === -1 ? body : body.slice(0, cut);
  const rest = cut === -1 ? "" : body.slice(cut);

  return (
    <span className="cmdbar__tok" data-neg={negated || undefined} data-bad={!parsed.ok || undefined}>
      {negated && (
        <span className="cmdbar__tok-neg" aria-hidden="true">
          −
        </span>
      )}
      <b>{key}</b>
      <em>{rest}</em>
      <button
        type="button"
        className="cmdbar__tok-x"
        aria-label={`Remove ${term}`}
        onMouseDown={(e) => {
          e.preventDefault();
          onRemove();
        }}
      >
        <span aria-hidden="true">×</span>
      </button>
    </span>
  );
}

/** The filter as the term list the bar edits, with `or` kept as its own token so
    a joiner survives a round-trip through the bar. */
function queryTerms(filter: FilterEntry[], defs: FilterDef[]): string[] {
  const text = formatQuery(filter, defs);
  return text === "" ? [] : tokenize(text);
}
