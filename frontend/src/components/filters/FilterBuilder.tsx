import { useEffect, useRef, useState } from "react";
import {
  NUMERIC_OPERATORS,
  type FilterDef,
  type FilterEntry,
  type NumericOperator,
} from "../../lib/filterEngine";
import { decodeFilter, encodeFilter } from "../../lib/dexViewCodec";
import {
  deleteExpression,
  expressionsFor,
  saveExpression,
  type SavedExpressions,
} from "../../lib/savedFilters";
import { CategoryChip, type Category } from "../CategoryChip";
import { TypeChip } from "../TypeChip";
import { TypeSelect } from "../TypeSelect";

type Props = {
  /** The active entity's filterable fields (dex / move / ability). */
  defs: FilterDef[];
  /** A DOM-id stem so the dex, moves, and abilities builders carry distinct ids. */
  idPrefix?: string;
  filter: FilterEntry[];
  onChange: (filter: FilterEntry[]) => void;
};

const MAX_FILTERS = 10;
const CATEGORY_VALUES = new Set(["physical", "special", "status"]);

function uid(): string {
  return crypto.randomUUID();
}

/* ---------------------------------------------------------------------------
   Stored-value codec. A FilterEntry keeps one packed string per field method
   ("≥|100", "weak|Water", "Level|≥|45"). Reading and writing it lives HERE, in
   one pair of functions, so the token, the editor, and the field menu can never
   disagree about what a value means.
   --------------------------------------------------------------------------- */

/** The editable pieces of a stored value, whatever the field's method. */
type ValueParts = {
  /** The relation operator: a numeric op, a type relation op, or "". */
  op: string;
  /** The chosen option for a select / selectnum field. */
  choice: string;
  /** The free text of a text field, or the numeric clause of numeric/selectnum. */
  text: string;
};

function readValue(def: FilterDef | undefined, stored: string): ValueParts {
  if (!def) return { op: "", choice: "", text: stored };
  if (def.method === "numeric") {
    const [op, num] = stored.split("|");
    return { op: op ?? "≥", choice: "", text: num ?? "" };
  }
  if (def.method === "selectnum") {
    const [choice, op, num] = stored.split("|");
    return { op: op ?? "≥", choice: choice ?? "", text: num ?? "" };
  }
  if (def.method === "select") {
    if (!def.operators) return { op: "", choice: stored, text: "" };
    const bar = stored.indexOf("|");
    return bar === -1
      ? { op: def.operators[0]?.op ?? "", choice: stored, text: "" }
      : { op: stored.slice(0, bar), choice: stored.slice(bar + 1), text: "" };
  }
  return { op: "", choice: "", text: stored };
}

function writeValue(def: FilterDef | undefined, parts: ValueParts): string {
  if (!def) return parts.text;
  if (def.method === "numeric") return `${parts.op}|${parts.text}`;
  if (def.method === "selectnum") {
    const wantsNumber = def.numericValues?.includes(parts.choice) ?? false;
    const clause = parts.text.trim();
    return wantsNumber && clause !== "" && !Number.isNaN(Number(clause))
      ? `${parts.choice}|${parts.op}|${clause}`
      : parts.choice;
  }
  if (def.method === "select") {
    return def.operators ? `${parts.op}|${parts.choice}` : parts.choice;
  }
  return parts.text;
}

/** The value a newly-added filter starts with, so one click yields a real term. */
function seedValue(def: FilterDef): string {
  if (def.method === "numeric") return "≥|";
  if (def.method === "selectnum") return def.values?.[0] ?? "";
  if (def.method === "select") {
    const choice = def.values?.[0] ?? "";
    return def.operators ? `${def.operators[0].op}|${choice}` : choice;
  }
  return "";
}

/** The operator a token displays: "~" for text, the relation for everything else. */
function displayOperator(def: FilterDef | undefined, parts: ValueParts): string {
  if (!def) return ":";
  if (def.method === "text") return "~";
  if (def.method === "numeric") return parts.op;
  if (def.method === "select" && def.operators) {
    return def.operators.find((o) => o.op === parts.op)?.label ?? parts.op;
  }
  return ":";
}

/** Plain-text rendering of a token, for aria labels and titles. */
function describe(def: FilterDef | undefined, value: string): string {
  const parts = readValue(def, value);
  const label = def?.label ?? "";
  const op = displayOperator(def, parts);
  if (def?.method === "selectnum") {
    const clause = parts.text ? ` ${parts.op} ${parts.text}` : "";
    return `${label} ${op} ${parts.choice}${clause}`;
  }
  const shown = def?.method === "text" || def?.method === "numeric" ? parts.text : parts.choice;
  return `${label} ${op} ${shown}`.trim();
}

/* ------------------------------------------------------------------------- */

/**
 * The filter bar: the active query rendered as ONE readable line of tokens, and
 * nothing else until you ask for something. There is no standing compose row —
 * a token IS its own editor (click it), and "+ filter" summons the field menu
 * where the new token will land.
 *
 * The state model is unchanged: a flat FilterEntry[] carrying per-leaf AND/OR
 * connectors, negation, and parenthesis grouping. Tokens reorder by drag (mouse)
 * or Alt+Arrow (keyboard), honoring the keyboard-first principle.
 */
export function FilterBuilder({ defs, idPrefix = "dexc", filter, onChange }: Props) {
  /** Which token's editor is open, "add" for the field menu, "saved" for the
      saved-expression menu, "save" for the name box, or null. */
  const [open, setOpen] = useState<string | "add" | "saved" | "save" | null>(null);
  const [saved, setSaved] = useState<SavedExpressions>(() =>
    expressionsFor(window.localStorage, idPrefix),
  );
  const lineRef = useRef<HTMLDivElement>(null);

  const filterCount = filter.filter((e) => e.kind === "filter").length;
  const atCap = filterCount >= MAX_FILTERS;
  const savedNames = Object.keys(saved);

  // One outside-click/Escape handler for both the editor and the field menu, so
  // an open popover never survives a click into the dex behind it.
  useEffect(() => {
    if (open === null) return;
    function onDown(event: MouseEvent) {
      if (!lineRef.current?.contains(event.target as Node)) setOpen(null);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(null);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function patch(id: string, change: Partial<FilterEntry>) {
    onChange(filter.map((e) => (e.id === id ? ({ ...e, ...change } as FilterEntry) : e)));
  }
  function remove(id: string) {
    onChange(filter.filter((e) => e.id !== id));
    setOpen(null);
  }
  function reorder(from: number, to: number) {
    if (to < 0 || to >= filter.length || from === to) return;
    const next = filter.slice();
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    onChange(next);
  }

  function addFilter(def: FilterDef) {
    if (atCap) return;
    const id = uid();
    onChange([
      ...filter,
      {
        kind: "filter",
        id,
        field: def.field,
        value: seedValue(def),
        connector: filter.length ? "AND" : "AND",
        negated: false,
      },
    ]);
    // Land straight in the new token's editor: adding a filter and setting its
    // value are one intention, not two.
    setOpen(id);
  }

  function addParens() {
    onChange([
      ...filter,
      { kind: "paren", id: uid(), paren: "(", connector: filter.length ? "AND" : "AND" },
      { kind: "paren", id: uid(), paren: ")", connector: "AND" },
    ]);
    setOpen(null);
  }

  /* --- Saved expressions. The stored value is encodeFilter()'s output, so a
     saved expression is the same string the URL carries — one format, not two.
     Applying one REPLACES the line: a saved expression is a whole query, and
     merging it into whatever is already there would silently build a third
     expression the human never wrote. */

  function saveCurrent(name: string) {
    const next = saveExpression(window.localStorage, idPrefix, name, encodeFilter(filter));
    setSaved(next[idPrefix] ?? {});
    setOpen(null);
  }

  function applySaved(name: string) {
    const encoded = saved[name];
    if (encoded === undefined) return;
    // Re-key on apply so two tokens from the same saved expression can never
    // collide with a token already carrying that id.
    onChange(decodeFilter(encoded).map((entry) => ({ ...entry, id: uid() })));
    setOpen(null);
  }

  function removeSaved(name: string) {
    const next = deleteExpression(window.localStorage, idPrefix, name);
    setSaved(next[idPrefix] ?? {});
  }

  return (
    <div className="dexc-filter" id={`${idPrefix}-filter-builder`}>
      <div className="dexc-query" ref={lineRef}>
        <div
          className="dexc-line"
          id={`${idPrefix}-query`}
          role="group"
          aria-label="Active filters"
          data-empty={filter.length === 0 || undefined}
        >
          {filter.length === 0 && <span className="dexc-line__none">No filters</span>}
          <span className="sr-only">
            Use Alt plus Left or Right Arrow to reorder a focused filter.
          </span>

          {filter.map((entry, index) => (
            <TokenItem
              key={entry.id}
              entry={entry}
              index={index}
              isFirst={index === 0}
              idPrefix={idPrefix}
              defs={defs}
              isOpen={open === entry.id}
              onOpen={() => setOpen((o) => (o === entry.id ? null : entry.id))}
              onClose={() => setOpen(null)}
              onPatch={(change) => patch(entry.id, change)}
              onToggleConnector={() =>
                patch(entry.id, {
                  connector: entry.connector === "AND" ? "OR" : "AND",
                } as Partial<FilterEntry>)
              }
              onRemove={() => remove(entry.id)}
              onReorder={reorder}
            />
          ))}

          <span className="dexc-add">
            <button
              type="button"
              className="dexc-add__btn"
              id={`${idPrefix}-add`}
              aria-expanded={open === "add"}
              aria-haspopup="menu"
              disabled={atCap}
              title={atCap ? `Filter cap of ${MAX_FILTERS} reached` : undefined}
              onClick={() => setOpen((o) => (o === "add" ? null : "add"))}
            >
              <span aria-hidden="true">+ </span>filter
            </button>
            {open === "add" && <FieldMenu defs={defs} idPrefix={idPrefix} onPick={addFilter} />}
          </span>
        </div>

        <div className="dexc-query__side">
          <button
            type="button"
            className="dexc-clear"
            id={`${idPrefix}-add-parens`}
            aria-label="Add a parenthesis group"
            title="Group the terms between the brackets"
            onClick={addParens}
          >
            ( )
          </button>

          {(savedNames.length > 0 || filter.length > 0) && (
            <span className="dexc-saved">
              {savedNames.length > 0 && (
                <button
                  type="button"
                  className="dexc-clear"
                  id={`${idPrefix}-saved`}
                  aria-expanded={open === "saved"}
                  aria-haspopup="menu"
                  onClick={() => setOpen((o) => (o === "saved" ? null : "saved"))}
                >
                  Saved <span className="dexc-saved__n">{savedNames.length}</span>
                </button>
              )}
              {filter.length > 0 && (
                <button
                  type="button"
                  className="dexc-clear"
                  id={`${idPrefix}-save`}
                  aria-expanded={open === "save"}
                  title="Save this expression under a name"
                  onClick={() => setOpen((o) => (o === "save" ? null : "save"))}
                >
                  Save
                </button>
              )}

              {open === "save" && (
                <SaveBox
                  idPrefix={idPrefix}
                  existing={savedNames}
                  onSave={saveCurrent}
                  onCancel={() => setOpen(null)}
                />
              )}
              {open === "saved" && (
                <SavedMenu
                  idPrefix={idPrefix}
                  saved={saved}
                  onApply={applySaved}
                  onDelete={removeSaved}
                />
              )}
            </span>
          )}

          {filter.length > 0 && (
            <button
              type="button"
              className="dexc-clear"
              id={`${idPrefix}-clear-filter`}
              onClick={() => {
                onChange([]);
                setOpen(null);
              }}
            >
              Clear
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------------- */

type TokenProps = {
  entry: FilterEntry;
  index: number;
  isFirst: boolean;
  idPrefix: string;
  defs: FilterDef[];
  isOpen: boolean;
  onOpen: () => void;
  onClose: () => void;
  onPatch: (change: Partial<FilterEntry>) => void;
  onToggleConnector: () => void;
  onRemove: () => void;
  onReorder: (from: number, to: number) => void;
};

function TokenItem({
  entry,
  index,
  isFirst,
  idPrefix,
  defs,
  isOpen,
  onOpen,
  onClose,
  onPatch,
  onToggleConnector,
  onRemove,
  onReorder,
}: TokenProps) {
  const isParen = entry.kind === "paren";
  const def = isParen ? undefined : defs.find((d) => d.field === entry.field);
  const text = isParen ? entry.paren : describe(def, entry.value);

  function onKeyDown(e: React.KeyboardEvent) {
    // Keyboard reorder: Alt+Arrow moves the focused token (the drag alternative).
    if (e.altKey && e.key === "ArrowLeft") {
      e.preventDefault();
      onReorder(index, index - 1);
    } else if (e.altKey && e.key === "ArrowRight") {
      e.preventDefault();
      onReorder(index, index + 1);
    }
  }

  return (
    <span
      className="dexc-tokwrap"
      draggable
      onDragStart={(e) => e.dataTransfer.setData("text/plain", String(index))}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        const from = Number(e.dataTransfer.getData("text/plain"));
        if (!Number.isNaN(from)) onReorder(from, index);
      }}
    >
      {!isFirst && (
        <button
          type="button"
          className="dexc-conn"
          aria-label={`Joined with ${entry.connector}; click to switch`}
          onClick={onToggleConnector}
          data-or={entry.connector === "OR" || undefined}
        >
          {entry.connector}
        </button>
      )}

      <span
        className="dexc-tok"
        data-paren={isParen || undefined}
        data-negated={(!isParen && entry.kind === "filter" && entry.negated) || undefined}
        onKeyDown={onKeyDown}
      >
        {isParen ? (
          <span
            className="dexc-tok__body"
            tabIndex={0}
            role="group"
            aria-label={`Parenthesis ${text}, reorder with Alt and arrow keys`}
            aria-keyshortcuts="Alt+ArrowLeft Alt+ArrowRight"
            title="Drag, or Alt+Arrow to reorder"
          >
            {text}
          </span>
        ) : (
          <button
            type="button"
            className="dexc-tok__body"
            aria-expanded={isOpen}
            aria-label={`${entry.negated ? "Excluding " : ""}${text} — edit; reorder with Alt and arrow keys`}
            aria-keyshortcuts="Alt+ArrowLeft Alt+ArrowRight"
            title="Click to edit · drag, or Alt+Arrow to reorder"
            onClick={onOpen}
          >
            <TokenBody def={def} entry={entry} />
          </button>
        )}

        <button
          type="button"
          className="dexc-tok__x"
          aria-label={`Remove ${isParen ? "parenthesis" : text}`}
          onClick={onRemove}
        >
          <span aria-hidden="true">×</span>
        </button>
      </span>

      {isOpen && entry.kind === "filter" && (
        <TokenEditor
          entry={entry}
          def={def}
          defs={defs}
          idPrefix={idPrefix}
          onPatch={onPatch}
          onClose={onClose}
        />
      )}
    </span>
  );
}

/** The token's readable face: FIELD · operator · value, with the franchise chip
    standing in for a bare type or category name. */
function TokenBody({ def, entry }: { def: FilterDef | undefined; entry: FilterEntry }) {
  if (entry.kind !== "filter") return null;
  const parts = readValue(def, entry.value);
  const op = displayOperator(def, parts);

  let value: React.ReactNode;
  if (def?.field === "type") {
    value = <TypeChip type={parts.choice} variant="code" />;
  } else if (def?.field === "category" && CATEGORY_VALUES.has(parts.choice)) {
    value = <CategoryChip category={parts.choice as Category} variant="full" />;
  } else if (def?.method === "selectnum") {
    const clause = parts.text ? ` ${parts.op} ${parts.text}` : "";
    value = `${parts.choice}${clause}`;
  } else if (def?.method === "text" || def?.method === "numeric") {
    value = parts.text || "…";
  } else {
    value = parts.choice;
  }

  return (
    <>
      {entry.negated && (
        <span className="dexc-tok__neg" aria-hidden="true">
          ≠
        </span>
      )}
      <span className="dexc-tok__field">{def?.label ?? entry.field}</span>
      <span className="dexc-tok__op">{op}</span>
      <span className="dexc-tok__value">{value}</span>
    </>
  );
}

/* ------------------------------------------------------------------------- */

type EditorProps = {
  entry: Extract<FilterEntry, { kind: "filter" }>;
  def: FilterDef | undefined;
  defs: FilterDef[];
  idPrefix: string;
  onPatch: (change: Partial<FilterEntry>) => void;
  onClose: () => void;
};

/**
 * The compose row, summoned at the token it edits instead of standing at the top
 * of the screen forever. Every control writes through to the entry immediately,
 * so a text field still filters as you type.
 */
function TokenEditor({ entry, def, defs, idPrefix, onPatch, onClose }: EditorProps) {
  const first = useRef<HTMLButtonElement>(null);
  const parts = readValue(def, entry.value);

  useEffect(() => {
    first.current?.focus();
  }, []);

  function setParts(change: Partial<ValueParts>) {
    onPatch({ value: writeValue(def, { ...parts, ...change }) });
  }

  function pickField(nextField: string) {
    const nextDef = defs.find((d) => d.field === nextField);
    if (!nextDef) return;
    onPatch({ field: nextField, value: seedValue(nextDef) });
  }

  const wantsNumber =
    def?.method === "selectnum" && (def.numericValues?.includes(parts.choice) ?? false);

  return (
    <div className="dexc-editor" role="group" aria-label="Edit filter">
      <button
        ref={first}
        type="button"
        className="dexc-not"
        aria-label="Exclude what this filter matches"
        aria-pressed={entry.negated}
        onClick={() => onPatch({ negated: !entry.negated })}
      >
        not
      </button>

      <select
        id={`${idPrefix}-field`}
        className="dexc-select"
        aria-label="Filter field"
        value={entry.field}
        onChange={(e) => pickField(e.target.value)}
      >
        {defs.map((d) => (
          <option key={d.field} value={d.field}>
            {d.label}
          </option>
        ))}
      </select>

      {def?.method === "numeric" && (
        <>
          <select
            id={`${idPrefix}-op`}
            className="dexc-select dexc-select--op"
            aria-label="Operator"
            value={parts.op}
            onChange={(e) => setParts({ op: e.target.value as NumericOperator })}
          >
            {NUMERIC_OPERATORS.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
          <input
            id={`${idPrefix}-value-num`}
            className="dexc-input dexc-input--num"
            type="number"
            inputMode="numeric"
            placeholder="0"
            aria-label="Value"
            autoFocus
            value={parts.text}
            onChange={(e) => setParts({ text: e.target.value })}
            onKeyDown={(e) => e.key === "Enter" && onClose()}
          />
        </>
      )}

      {def?.method === "select" && def.field === "type" && (
        <>
          {def.operators && (
            <select
              id={`${idPrefix}-type-op`}
              className="dexc-select"
              aria-label="Type relation"
              value={parts.op}
              onChange={(e) => setParts({ op: e.target.value })}
            >
              {def.operators.map((o) => (
                <option key={o.op} value={o.op}>
                  {o.label}
                </option>
              ))}
            </select>
          )}
          <TypeSelect
            id={`${idPrefix}-value-type`}
            label={`${def.label} value`}
            value={parts.choice || def.values?.[0] || ""}
            variant="code"
            onChange={(v) => setParts({ choice: v })}
          />
        </>
      )}

      {def?.method === "select" && def.field !== "type" && (
        <select
          id={`${idPrefix}-value-select`}
          className="dexc-select"
          aria-label={`${def.label} value`}
          value={parts.choice || def.values?.[0] || ""}
          onChange={(e) => setParts({ choice: e.target.value })}
        >
          {def.values?.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
      )}

      {def?.method === "selectnum" && (
        <>
          <select
            id={`${idPrefix}-value-kind`}
            className="dexc-select"
            aria-label={`${def.label} kind`}
            value={parts.choice || def.values?.[0] || ""}
            onChange={(e) => setParts({ choice: e.target.value })}
          >
            {def.values?.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
          {wantsNumber && (
            <>
              <select
                id={`${idPrefix}-kind-op`}
                className="dexc-select dexc-select--op"
                aria-label="Operator"
                value={parts.op}
                onChange={(e) => setParts({ op: e.target.value as NumericOperator })}
              >
                {NUMERIC_OPERATORS.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
              <input
                id={`${idPrefix}-kind-num`}
                className="dexc-input dexc-input--num"
                type="number"
                inputMode="numeric"
                placeholder="any"
                aria-label="Value (optional)"
                value={parts.text}
                onChange={(e) => setParts({ text: e.target.value })}
                onKeyDown={(e) => e.key === "Enter" && onClose()}
              />
            </>
          )}
        </>
      )}

      {def?.method === "text" && (
        <input
          id={`${idPrefix}-value-text`}
          className="dexc-input"
          type="text"
          placeholder="contains…"
          aria-label="Value"
          autoFocus
          value={parts.text}
          onChange={(e) => setParts({ text: e.target.value })}
          onKeyDown={(e) => e.key === "Enter" && onClose()}
        />
      )}

      <button type="button" className="dexc-clear" onClick={onClose}>
        Done
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------------- */

/** Name the current expression. Enter saves, Escape backs out. Naming an
    existing expression overwrites it, and the button says so rather than
    failing quietly or silently growing a near-duplicate. */
function SaveBox({
  idPrefix,
  existing,
  onSave,
  onCancel,
}: {
  idPrefix: string;
  existing: string[];
  onSave: (name: string) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const trimmed = name.trim();
  const overwrites = existing.includes(trimmed);

  return (
    <div className="dexc-editor dexc-editor--right" role="group" aria-label="Save this expression">
      <input
        id={`${idPrefix}-save-name`}
        className="dexc-input"
        type="text"
        placeholder="Name this expression…"
        aria-label="Expression name"
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && trimmed !== "") onSave(trimmed);
          if (e.key === "Escape") onCancel();
        }}
      />
      <button
        type="button"
        className="dexc-clear"
        id={`${idPrefix}-save-confirm`}
        disabled={trimmed === ""}
        onClick={() => onSave(trimmed)}
      >
        {overwrites ? "Overwrite" : "Save"}
      </button>
    </div>
  );
}

/** The saved expressions for this entity. Clicking a name replaces the line
    with it; the × forgets it. */
function SavedMenu({
  idPrefix,
  saved,
  onApply,
  onDelete,
}: {
  idPrefix: string;
  saved: SavedExpressions;
  onApply: (name: string) => void;
  onDelete: (name: string) => void;
}) {
  return (
    <div className="dexc-menu dexc-menu--right" role="menu" id={`${idPrefix}-saved-menu`}>
      <p className="dexc-menu__group">Saved expressions</p>
      {Object.keys(saved).map((name) => (
        <span key={name} className="dexc-menu__row">
          <button
            type="button"
            role="menuitem"
            className="dexc-menu__item"
            onClick={() => onApply(name)}
          >
            <span>{name}</span>
          </button>
          <button
            type="button"
            className="dexc-menu__x"
            aria-label={`Forget the expression ${name}`}
            onClick={() => onDelete(name)}
          >
            <span aria-hidden="true">×</span>
          </button>
        </span>
      ))}
    </div>
  );
}

/** The field menu: every filterable field, grouped by what you do with it, so
    "which fields can I filter on?" is one glance instead of a dropdown crawl. */
function FieldMenu({
  defs,
  idPrefix,
  onPick,
}: {
  defs: FilterDef[];
  idPrefix: string;
  onPick: (def: FilterDef) => void;
}) {
  const groups: { name: string; defs: FilterDef[] }[] = [
    { name: "Text", defs: defs.filter((d) => d.method === "text") },
    {
      name: "Category",
      defs: defs.filter((d) => d.method === "select" || d.method === "selectnum"),
    },
    { name: "Numbers", defs: defs.filter((d) => d.method === "numeric") },
  ];

  return (
    <div className="dexc-menu" role="menu" id={`${idPrefix}-field-menu`}>
      {groups
        .filter((g) => g.defs.length > 0)
        .map((group) => (
          <div key={group.name}>
            <p className="dexc-menu__group">{group.name}</p>
            {group.defs.map((d) => (
              <button
                key={d.field}
                type="button"
                role="menuitem"
                className="dexc-menu__item"
                onClick={() => onPick(d)}
              >
                <span>{d.label}</span>
                <span className="dexc-menu__hint">
                  {d.method === "text" ? "~" : d.method === "numeric" ? "≥" : "is"}
                </span>
              </button>
            ))}
          </div>
        ))}
    </div>
  );
}
