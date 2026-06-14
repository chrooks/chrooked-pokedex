import { useId, useState } from "react";
import { COLUMNS, type ColumnKey } from "../../lib/dexColumns";

type Props = {
  hidden: ColumnKey[];
  onChange: (hidden: ColumnKey[]) => void;
};

// led/dex/name are the locked identity anchor; only data columns toggle.
const TOGGLEABLE = COLUMNS.filter((c) => !c.locked);

/**
 * Column show/hide as a disclosure: a "Columns" button reveals a checkbox panel
 * of the data columns (the LED/№/Name identity anchor stays locked, never
 * offered). Hiding a column also drops it from the sort, handled by the parent.
 */
export function ColumnsControl({ hidden, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const hiddenSet = new Set(hidden);
  const hiddenCount = hidden.length;

  function toggle(key: ColumnKey) {
    onChange(
      hiddenSet.has(key) ? hidden.filter((k) => k !== key) : [...hidden, key],
    );
  }

  return (
    <div className="dexc-columns">
      <button
        type="button"
        className="btn btn--new"
        id="dexc-columns-toggle"
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
          {TOGGLEABLE.map((c) => (
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
