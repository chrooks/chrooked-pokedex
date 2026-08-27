/* The BLIND switch: does this suggest call design from the creature's lore with
   its identity withheld, or from everything the model already knows about it?

   Blind fetches the same researched sources the lore modes always did, then
   anonymizes the profile and holds back the prior art for whatever is being
   suggested — the species' name, and the current typing / abilities / learnset
   that the model would otherwise just hand back. The trap it exists to defeat:
   a model that recognizes the species reaches for its canon kit.

   It replaced a three-way off / lore / lore-condensed control. Those modes are
   still valid on the API; the workbench stopped offering them because the author
   never reached for them, and blind subsumes the useful half (it is lore-on by
   construction — the anonymized profile IS its input).

   Honest about its limits: anonymization removes the reflex, not the
   possibility. A distinctive design origin can still identify a creature, and
   the title says so rather than promising secrecy.

   A sibling of the editors' ScopeToggle: same radiogroup/radio shape, same
   `data-on` styling hook. Deliberately colorless — --chrome is device structure
   and --edited means "the Ruleset touched this", and a sourcing mode is
   neither. */

import type { LoreMode } from "../../types";

const OPTIONS: { mode: LoreMode; id: string; label: string; title: string }[] = [
  {
    mode: "off",
    id: "mk-lore-off",
    label: "off",
    title: "No lookup — the model answers from memory, prior art and all.",
  },
  {
    mode: "blind",
    id: "mk-lore-blind",
    label: "blind",
    title:
      "Read the real sources, strip the creature's identity from them, and withhold " +
      "its current kit — design from what it IS. Best-effort: a distinctive design " +
      "origin can still give the creature away.",
  },
];

interface Props {
  mode: LoreMode;
  onChange: (mode: LoreMode) => void;
  /** Held still while a call is in flight — the control describes what is running. */
  disabled?: boolean;
}

export function LoreControl({ mode, onChange, disabled = false }: Props) {
  // `full` and `condensed` can still arrive from a restored URL or an older
  // session. Neither has a segment any more, so they rest on `off` rather than
  // leaving the group with nothing checked.
  const shown: LoreMode = mode === "blind" ? "blind" : "off";
  return (
    <div
      className="mk-lore"
      id="mk-lore-control"
      role="radiogroup"
      aria-label="Lore sourcing"
    >
      <span className="mk-lore__label mono">lore</span>
      {OPTIONS.map((option) => (
        <button
          key={option.mode}
          type="button"
          id={option.id}
          className="mk-lore__seg mono"
          role="radio"
          aria-checked={shown === option.mode}
          data-on={shown === option.mode}
          disabled={disabled}
          title={option.title}
          onClick={() => onChange(option.mode)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
