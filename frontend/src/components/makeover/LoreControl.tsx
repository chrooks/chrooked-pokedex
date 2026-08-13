/* The lore-lookup switch: does this suggest call read real sources first, or
   answer from the model's memory? Three ways, off resting — `off`, `lore` (the
   fetched text raw, capped), `lore (condensed)` (one extra call condenses it
   first). The two on-modes are an experiment the author is running, so both are
   one click apart rather than hidden behind a setting.

   A sibling of the editors' ScopeToggle: same radiogroup/radio shape, same
   `data-on` styling hook, same label-plus-segmented-well layout — this is the
   makeover-side member of that family, not a new species. Deliberately
   colorless: the on-segment inverts --text-dim, because --chrome is device
   structure and --edited means "the Ruleset touched this", and a lookup mode is
   neither. */

import type { LoreMode } from "../../types";

const OPTIONS: { mode: LoreMode; id: string; label: string; title: string }[] = [
  {
    mode: "off",
    id: "mk-lore-off",
    label: "off",
    title: "No lookup — the model answers from memory.",
  },
  {
    mode: "full",
    id: "mk-lore-full",
    label: "lore",
    title: "Read the dex entries and the origin section, and inject them raw (capped).",
  },
  {
    mode: "condensed",
    id: "mk-lore-condensed",
    label: "lore (condensed)",
    title: "Read the same sources, then condense them to a brief before injecting.",
  },
];

interface Props {
  mode: LoreMode;
  onChange: (mode: LoreMode) => void;
  /** Held still while a call is in flight — the control describes what is running. */
  disabled?: boolean;
}

export function LoreControl({ mode, onChange, disabled = false }: Props) {
  return (
    <div className="mk-lore" id="mk-lore-control" role="radiogroup" aria-label="Lore lookup">
      <span className="mk-lore__label mono">lore</span>
      <div className="mk-lore__options">
        {OPTIONS.map((option) => (
          <button
            key={option.mode}
            type="button"
            id={option.id}
            className="mk-lore__option mono"
            role="radio"
            aria-checked={mode === option.mode}
            data-on={mode === option.mode}
            disabled={disabled}
            title={option.title}
            onClick={() => onChange(option.mode)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
