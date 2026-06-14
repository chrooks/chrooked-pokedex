import { useState } from "react";
import {
  buildFilterDefs,
  NUMERIC_OPERATORS,
  type FilterDef,
  type FilterEntry,
  type NumericOperator,
} from "../../lib/dexFilters";

type Props = {
  filter: FilterEntry[];
  onChange: (filter: FilterEntry[]) => void;
};

const MAX_FILTERS = 10;
// Static (buildFilterDefs ignores its arg); built once at module load.
const DEFS = buildFilterDefs([]);

function uid(): string {
  return crypto.randomUUID();
}

/** Human label for a pill, e.g. "ATK ≥ 100", "Type: Fire", "Name: char". */
function describe(def: FilterDef | undefined, value: string): string {
  if (!def) return value;
  if (def.method === "numeric") {
    const [op, num] = value.split("|");
    return `${def.label} ${op} ${num}`;
  }
  return `${def.label}: ${value}`;
}

/**
 * The filter builder: a compose row (field → operator/value → connector → add)
 * plus the row of pills it produces. Pills carry per-leaf AND/OR connectors, NOT
 * negation, and parenthesis grouping; they reorder by drag (mouse) or Alt+Arrow
 * (keyboard), honoring the keyboard-first principle. Applies to both views.
 */
export function FilterBuilder({ filter, onChange }: Props) {
  const defs = DEFS;
  const [field, setField] = useState(defs[0].field);
  const [op, setOp] = useState<NumericOperator>("≥");
  const [value, setValue] = useState("");
  const [connector, setConnector] = useState<"AND" | "OR">("AND");

  const def = defs.find((d) => d.field === field);
  const filterCount = filter.filter((e) => e.kind === "filter").length;
  const atCap = filterCount >= MAX_FILTERS;

  function pickField(nextField: string) {
    setField(nextField);
    const nextDef = defs.find((d) => d.field === nextField);
    // Seed select fields with their first option so "Add" is one click.
    setValue(nextDef?.method === "select" ? (nextDef.values?.[0] ?? "") : "");
  }

  function addFilter() {
    if (!def || atCap) return;
    let stored: string;
    if (def.method === "numeric") {
      const num = value.trim();
      if (num === "" || Number.isNaN(Number(num))) return;
      stored = `${op}|${num}`;
    } else if (def.method === "select") {
      stored = value || (def.values?.[0] ?? "");
      if (stored === "") return;
    } else {
      stored = value.trim();
      if (stored === "") return;
    }
    onChange([
      ...filter,
      {
        kind: "filter",
        id: uid(),
        field,
        value: stored,
        connector: filter.length ? connector : "AND",
        negated: false,
      },
    ]);
    if (def.method !== "select") setValue("");
  }

  function addParens() {
    onChange([
      ...filter,
      { kind: "paren", id: uid(), paren: "(", connector: filter.length ? connector : "AND" },
      { kind: "paren", id: uid(), paren: ")", connector: "AND" },
    ]);
  }

  function patch(id: string, change: Partial<FilterEntry>) {
    onChange(filter.map((e) => (e.id === id ? ({ ...e, ...change } as FilterEntry) : e)));
  }
  function remove(id: string) {
    onChange(filter.filter((e) => e.id !== id));
  }
  function reorder(from: number, to: number) {
    if (to < 0 || to >= filter.length || from === to) return;
    const next = filter.slice();
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    onChange(next);
  }

  return (
    <div className="dexc-filter" id="dex-filter-builder">
      <div className="dexc-row">
        <span className="dexc-label">Filter</span>
        <select
          id="dexc-field"
          className="dexc-select"
          aria-label="Filter field"
          value={field}
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
              id="dexc-op"
              className="dexc-select dexc-select--op"
              aria-label="Operator"
              value={op}
              onChange={(e) => setOp(e.target.value as NumericOperator)}
            >
              {NUMERIC_OPERATORS.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
            <input
              id="dexc-value-num"
              className="dexc-input dexc-input--num"
              type="number"
              inputMode="numeric"
              placeholder="0"
              aria-label="Value"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addFilter()}
            />
          </>
        )}
        {def?.method === "select" && (
          <select
            id="dexc-value-select"
            className="dexc-select"
            aria-label={`${def.label} value`}
            value={value || def.values?.[0] || ""}
            onChange={(e) => setValue(e.target.value)}
          >
            {def.values?.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        )}
        {def?.method === "text" && (
          <input
            id="dexc-value-text"
            className="dexc-input"
            type="text"
            placeholder="contains…"
            aria-label="Value"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addFilter()}
          />
        )}

        {filter.length > 0 && (
          <button
            type="button"
            className="dexc-conn dexc-conn--compose"
            aria-label={`Join the next filter with ${connector}; click to switch`}
            onClick={() => setConnector((c) => (c === "AND" ? "OR" : "AND"))}
            data-or={connector === "OR" || undefined}
          >
            {connector}
          </button>
        )}
        <button
          type="button"
          className="btn btn--new"
          id="dexc-add"
          onClick={addFilter}
          disabled={atCap}
          title={atCap ? `Filter cap of ${MAX_FILTERS} reached` : undefined}
        >
          <span aria-hidden="true">+ </span>Add filter
        </button>
        <button
          type="button"
          className="btn btn--new dexc-paren-add"
          id="dexc-add-parens"
          onClick={addParens}
          aria-label="Add a parenthesis group"
        >
          ( )
        </button>
      </div>

      {filter.length > 0 && (
        <ul className="dexc-pills" aria-label="Active filters">
          <li className="sr-only">Use Alt plus Left or Right Arrow to reorder a focused filter.</li>
          {filter.map((entry, index) => (
            <PillItem
              key={entry.id}
              entry={entry}
              index={index}
              isFirst={index === 0}
              def={defs.find((d) => d.field === (entry.kind === "filter" ? entry.field : ""))}
              onToggleConnector={() =>
                patch(entry.id, {
                  connector: entry.connector === "AND" ? "OR" : "AND",
                } as Partial<FilterEntry>)
              }
              onToggleNegate={() =>
                entry.kind === "filter" && patch(entry.id, { negated: !entry.negated } as Partial<FilterEntry>)
              }
              onRemove={() => remove(entry.id)}
              onReorder={reorder}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

type PillItemProps = {
  entry: FilterEntry;
  index: number;
  isFirst: boolean;
  def: FilterDef | undefined;
  onToggleConnector: () => void;
  onToggleNegate: () => void;
  onRemove: () => void;
  onReorder: (from: number, to: number) => void;
};

function PillItem({
  entry,
  index,
  isFirst,
  def,
  onToggleConnector,
  onToggleNegate,
  onRemove,
  onReorder,
}: PillItemProps) {
  function onKeyDown(e: React.KeyboardEvent) {
    // Keyboard reorder: Alt+Arrow moves the focused pill (drag alternative).
    if (e.altKey && e.key === "ArrowLeft") {
      e.preventDefault();
      onReorder(index, index - 1);
    } else if (e.altKey && e.key === "ArrowRight") {
      e.preventDefault();
      onReorder(index, index + 1);
    }
  }

  const isParen = entry.kind === "paren";
  const body = isParen ? entry.paren : describe(def, entry.value);

  return (
    <li
      className="dexc-pillwrap"
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
          aria-label={`Connector ${entry.connector}; click to switch`}
          onClick={onToggleConnector}
          data-or={entry.connector === "OR" || undefined}
        >
          {entry.connector}
        </button>
      )}
      <span
        className="dexc-pill"
        data-paren={isParen || undefined}
        data-negated={(!isParen && entry.kind === "filter" && entry.negated) || undefined}
        tabIndex={0}
        role="group"
        aria-label={`${isParen ? "Parenthesis" : "Filter"} ${body}, reorder with Alt and arrow keys`}
        aria-keyshortcuts="Alt+ArrowLeft Alt+ArrowRight"
        onKeyDown={onKeyDown}
        title="Drag, or Alt+Arrow to reorder"
      >
        {!isParen && entry.kind === "filter" && (
          <button
            type="button"
            className="dexc-not"
            aria-label="Negate this filter"
            aria-pressed={entry.negated}
            onClick={onToggleNegate}
          >
            not
          </button>
        )}
        <span className="dexc-pill__body">{body}</span>
        <button
          type="button"
          className="dexc-pill__x"
          aria-label={`Remove ${isParen ? "parenthesis" : body}`}
          onClick={onRemove}
        >
          <span aria-hidden="true">×</span>
        </button>
      </span>
    </li>
  );
}
