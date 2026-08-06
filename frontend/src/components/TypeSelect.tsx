import { useId, useRef, useState } from "react";
import { TYPES } from "../lib/format";
import { TypeChip } from "./TypeChip";
import "./type-select.css";

type Props = {
  id: string;
  /** Current type display name, or "" when nothing is selected. */
  value: string;
  onChange: (value: string) => void;
  /** Offer a leading "None" option (secondary type slots). */
  allowNone?: boolean;
  /** Accessible name for the control. */
  label: string;
  /** "code" shows the 3-letter chip in the trigger; "full" shows the name. */
  variant?: "code" | "full";
  /** Extra class on the trigger button, to blend into a host shell. */
  className?: string;
};

const NONE = "";

/** Columns in the open list. Three keeps all 18 types on screen at once without
    the panel growing wider than the narrowest host (the detail sidebar). */
const COLUMNS = 3;

/**
 * A type picker that renders the franchise TypeChip for every option — the thing
 * a native <select> can't do, since <option> is text-only. Follows the app's
 * combobox+listbox idiom (see PartyPicker): focus stays on the trigger, arrow
 * keys move aria-activedescendant, mousedown picks before blur closes the list.
 */
export function TypeSelect({
  id,
  value,
  onChange,
  allowNone = false,
  label,
  variant = "full",
  className,
}: Props) {
  const options = allowNone ? [NONE, ...TYPES] : [...TYPES];
  const listboxId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(() => Math.max(0, options.indexOf(value)));

  // Balanced columns: 18 types become 6×3, and adding "None" reflows to 7×3
  // rather than leaving one option alone in a fourth column.
  const rows = Math.ceil(options.length / COLUMNS);

  function commit(next: string) {
    onChange(next);
    setOpen(false);
    buttonRef.current?.focus();
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "Escape") {
      setOpen(false);
      return;
    }
    if (!open && (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      setActive(Math.max(0, options.indexOf(value)));
      setOpen(true);
      return;
    }
    if (!open) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => (i + 1) % options.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => (i - 1 + options.length) % options.length);
    } else if (event.key === "Home") {
      event.preventDefault();
      setActive(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setActive(options.length - 1);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      commit(options[active]);
    }
  }

  return (
    <div className="type-select">
      <button
        ref={buttonRef}
        type="button"
        id={id}
        className={className ? `type-select__trigger ${className}` : "type-select__trigger"}
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-activedescendant={open ? `${listboxId}-opt-${active}` : undefined}
        aria-label={label}
        onClick={() => setOpen((o) => !o)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      >
        {value ? (
          <TypeChip type={value} variant={variant} />
        ) : (
          <span className="type-select__none">None</span>
        )}
        <span className="dexc-caret" aria-hidden="true" data-open={open || undefined}>
          ▾
        </span>
      </button>

      {open && (
        <ul
          className="type-select__list"
          id={listboxId}
          role="listbox"
          aria-label={label}
          style={{ "--rows": rows } as React.CSSProperties}
        >
          {options.map((option, index) => (
            <li
              key={option || "none"}
              id={`${listboxId}-opt-${index}`}
              role="option"
              aria-selected={option === value}
              className="type-select__option"
              data-active={index === active}
              // mousedown (not click) so the option is chosen before the trigger blurs.
              onMouseDown={(event) => {
                event.preventDefault();
                commit(option);
              }}
              onMouseEnter={() => setActive(index)}
            >
              {option ? (
                <TypeChip type={option} variant={variant} />
              ) : (
                <span className="type-select__none">None</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
