/* Controlled form fields shared by the species / move / ability editors.
   Each renders a labelled, AA-legible input on the device's inset-well style,
   with an optional hint, an error slot, and a "changed from base" flag that the
   species editor uses to make Overrides visible as you type. */

import type { ChangeEvent, ReactNode } from "react";

type BaseProps = {
  id: string;
  label: string;
  hint?: ReactNode;
  error?: string | null;
  full?: boolean;
  changed?: boolean;
};

function FieldShell({
  id,
  label,
  hint,
  error,
  full,
  changed,
  children,
}: BaseProps & { children: ReactNode }) {
  return (
    <div className={full ? "field field--full" : "field"}>
      <label className="field__label" htmlFor={id}>
        {label}
        {hint && <span className="field__hint"> · {hint}</span>}
        {/* the "changed from base" state is color-coded on the input; this is
            its non-visual equivalent, announced with the field's label. */}
        {changed && <span className="sr-only"> (changed from base)</span>}
      </label>
      {children}
      {error && (
        <span className="field__error" id={`${id}-error`}>
          {error}
        </span>
      )}
    </div>
  );
}

type TextProps = BaseProps & {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  mono?: boolean;
  readOnly?: boolean;
};

export function TextField({ value, onChange, placeholder, mono, readOnly, ...rest }: TextProps) {
  return (
    <FieldShell {...rest}>
      <input
        id={rest.id}
        className={mono ? "field__input mono" : "field__input"}
        type="text"
        value={value}
        placeholder={placeholder}
        readOnly={readOnly}
        data-changed={rest.changed ? "true" : undefined}
        aria-invalid={rest.error ? "true" : undefined}
        aria-describedby={rest.error ? `${rest.id}-error` : undefined}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      />
    </FieldShell>
  );
}

type NumberProps = BaseProps & {
  value: number | "";
  onChange: (value: number | "") => void;
  min?: number;
  max?: number;
  placeholder?: string;
};

export function NumberField({ value, onChange, min, max, placeholder, ...rest }: NumberProps) {
  return (
    <FieldShell {...rest}>
      <input
        id={rest.id}
        className="field__input mono"
        type="number"
        inputMode="numeric"
        value={value}
        min={min}
        max={max}
        placeholder={placeholder}
        data-changed={rest.changed ? "true" : undefined}
        aria-invalid={rest.error ? "true" : undefined}
        aria-describedby={rest.error ? `${rest.id}-error` : undefined}
        onChange={(e: ChangeEvent<HTMLInputElement>) => {
          const raw = e.target.value;
          onChange(raw === "" ? "" : Number(raw));
        }}
      />
    </FieldShell>
  );
}

type SelectProps = BaseProps & {
  value: string;
  onChange: (value: string) => void;
  options: readonly string[];
};

export function SelectField({ value, onChange, options, ...rest }: SelectProps) {
  return (
    <FieldShell {...rest}>
      <select
        id={rest.id}
        className="field__select"
        value={value}
        aria-invalid={rest.error ? "true" : undefined}
        aria-describedby={rest.error ? `${rest.id}-error` : undefined}
        onChange={(e: ChangeEvent<HTMLSelectElement>) => onChange(e.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </FieldShell>
  );
}

type ComboProps = BaseProps & {
  value: string;
  onChange: (value: string) => void;
  /** Suggestions shown in the dropdown; any value can still be typed. */
  options: readonly string[];
  placeholder?: string;
};

/** A searchable combobox: a text input backed by a native <datalist>. The
    options are suggestions, not a closed set — a base-game ability or a custom
    type that isn't in the list still types through. */
export function ComboField({ value, onChange, options, placeholder, ...rest }: ComboProps) {
  const listId = `${rest.id}-list`;
  return (
    <FieldShell {...rest}>
      <input
        id={rest.id}
        className="field__input"
        type="text"
        list={listId}
        value={value}
        placeholder={placeholder}
        autoComplete="off"
        data-changed={rest.changed ? "true" : undefined}
        aria-invalid={rest.error ? "true" : undefined}
        aria-describedby={rest.error ? `${rest.id}-error` : undefined}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      />
      <datalist id={listId}>
        {options.map((option) => (
          <option key={option} value={option} />
        ))}
      </datalist>
    </FieldShell>
  );
}

type TextAreaProps = BaseProps & {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
};

export function TextAreaField({ value, onChange, placeholder, ...rest }: TextAreaProps) {
  return (
    <FieldShell {...rest}>
      <textarea
        id={rest.id}
        className="field__textarea"
        value={value}
        placeholder={placeholder}
        aria-invalid={rest.error ? "true" : undefined}
        aria-describedby={rest.error ? `${rest.id}-error` : undefined}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value)}
      />
    </FieldShell>
  );
}
