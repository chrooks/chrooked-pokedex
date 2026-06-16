import { useId, useState } from "react";

/** A toggleable column offered by the panel: a stable key + a human label. */
export type ToggleableColumn = { key: string; label: string };

type Props = {
  /** The non-locked columns this entity can hide, in display order. */
  columns: ToggleableColumn[];
  /** A DOM-id stem so each surface's columns toggle carries distinct ids. */
  idPrefix?: string;
  hidden: string[];
  onChange: (hidden: string[]) => void;
};

/**
 * Column show/hide as a disclosure: a "Columns" button reveals a checkbox panel
 * of the data columns (the locked identity anchor stays locked, never offered).
 * Hiding a column also drops it from the sort, handled by the parent.
 */
export function ColumnsControl({ columns, idPrefix = "dexc", hidden, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const hiddenSet = new Set(hidden);
  const hiddenCount = hidden.length;

  function toggle(key: string) {
    onChange(
      hiddenSet.has(key) ? hidden.filter((k) => k !== key) : [...hidden, key],
    );
  }

  return (
    <div className="dexc-columns">
      <button
        type="button"
        className="btn btn--new"
        id={`${idPrefix}-columns-toggle`}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => setOpen((o) => !o)}
      >
        Columns
        {hiddenCount > 0 && <span className="dexc-columns__count">{hiddenCount} hidden</span>}
        <span className="dexc-caret" aria-hidden="true" data-open={open || undefined}>
          ▾
        </span>
      </button>
      {open && (
        <div className="dexc-columns__panel" id={panelId} role="group" aria-label="Toggle columns">
          {columns.map((c) => (
            <label key={c.key} className="dexc-check">
              <input
                type="checkbox"
                checked={!hiddenSet.has(c.key)}
                onChange={() => toggle(c.key)}
              />
              <span>{c.label}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
