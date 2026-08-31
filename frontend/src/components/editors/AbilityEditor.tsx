/* Create or edit one Ruleset-owned ability (data only — the mechanic lives in a
   behavior spec, edited in 2b). aka rides along from the loaded ability so an
   edit doesn't strip the engine symbol. Delete runs the citation guard: an
   ability a species' slot still cites returns 409, and the footer becomes a
   "Delete anyway" confirm naming the citing species. */

import { useEffect, useState } from "react";
import { api } from "../../api";
import type { Ability, AbilityField, AbilityWrite, Behavior } from "../../types";
import { useSubmit } from "../../hooks/useSubmit";
import { isAbilityEdited, ABILITY_FIELD_LABEL } from "../../lib/format";
import { EditedLed } from "../EditedLed";
import { EditorDialog } from "./EditorDialog";
import { TextAreaField, TextField } from "./fields";
import { FormError } from "./FormFeedback";
import "./editors.css";
import "../ledger/ledger-rows.css";

type Props = {
  /** null = create a new ability; otherwise edit this one. */
  ability: Ability | null;
  onClose: () => void;
  /** Fired on a successful save. Carries the saved ability's display name so a
      host flow (the tab Add dialog) can advance to a distribute step for it;
      callers that don't need it ignore the argument. */
  onSaved: (savedName?: string) => void;
  /** When true the editor renders without the overlay/header chrome — it is
      already hosted inside a DetailSidebar shell. */
  embedded?: boolean;
};

type AbilityForm = {
  name: string;
  chrooked_id: string;
  description: string;
  /** Which behaviors this ability is built from. Empty = its own behavior.
      One non-self entry is an alias; two or more is a combo. One control
      serves both — they differ only by how many entries the list has. */
  behaviors: string[];
};

export function AbilityEditor({ ability, onClose, onSaved, embedded = false }: Props) {
  const isNew = ability === null;
  const { isSaving, error, run } = useSubmit();
  const del = useSubmit();
  const [form, setForm] = useState<AbilityForm>(() => ({
    name: ability?.name ?? "",
    chrooked_id: ability?.chrooked_id ?? "",
    description: ability?.description ?? "",
    behaviors: ability?.behaviors ?? [],
  }));
  const [allBehaviors, setAllBehaviors] = useState<Behavior[]>([]);

  useEffect(() => {
    const ctrl = new AbortController();
    api
      .behaviors(ctrl.signal)
      .then((rows) => setAllBehaviors(rows.filter((b) => b.applies_to === "ability")))
      .catch(() => {
        /* the picker degrades to empty; saving without parts still works */
      });
    return () => ctrl.abort();
  }, []);

  const titleId = "ability-editor-title";

  function toggleBehavior(id: string) {
    setForm((f) => ({
      ...f,
      behaviors: f.behaviors.includes(id)
        ? f.behaviors.filter((b) => b !== id)
        : [...f.behaviors, id],
    }));
  }

  function set<K extends keyof AbilityForm>(key: K, value: AbilityForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSave() {
    const id = form.chrooked_id.trim();
    // The merged view carries server-recomputed flags (overridden_fields, base)
    // that the ability loader rejects as unknown keys (422) — strip them and PUT
    // only the Ruleset-owned fields. Editing a base-only ability upserts a
    // Ruleset entry (mirrors species "edit base → make override").
    const payload: AbilityWrite = {
      name: form.name.trim(),
      chrooked_id: id,
      description: form.description.trim(),
      aka: ability?.aka ?? {},
      behaviors: form.behaviors,
    };
    const ok = await run(() => api.putAbility(id, payload));
    if (ok) {
      onSaved(form.name.trim());
      onClose();
    }
  }

  async function handleDelete(confirm: boolean) {
    if (ability === null) return;
    const ok = await del.run(() => api.deleteAbility(ability.chrooked_id, confirm));
    if (ok) {
      onSaved();
      onClose();
    }
  }

  const busy = isSaving || del.isSaving;

  // base → now diff rows for an existing ability. An overridden field that has a
  // base value reads `was → now`; a Ruleset-created ability (empty base) has the
  // field flagged with no `was`, so it reads as new.
  const edited = ability !== null && isAbilityEdited(ability);
  const currentOf: Record<AbilityField, string> = {
    name: ability?.name ?? "",
    description: ability?.description ?? "",
  };
  const diffRows = edited
    ? ability.overridden_fields.map((field) => ({
        field,
        was: ability.base[field],
        now: currentOf[field],
      }))
    : [];

  const formBody = (
    <>
      {!embedded && (
        <header className="ledger__head">
          <div className="ledger__head-row">
            <span className="ledger__dex mono">ABILITY</span>
            <button
              type="button"
              className="ledger__close"
              aria-label="Close editor"
              onClick={onClose}
            >
              Close <kbd className="mono" aria-hidden="true">Esc</kbd>
            </button>
          </div>
          <h2 className="ledger__name" id={titleId}>
            {isNew ? "New ability" : ability.name}
            {edited && (
              <>
                {" "}
                <EditedLed on variant="tag" />
              </>
            )}
          </h2>
        </header>
      )}

      {edited && (
        <section
          id="ability-diff"
          className="ability-diff"
          aria-label="What the Ruleset changed"
        >
          {diffRows.map(({ field, was, now }) => (
            <div key={field} className="lrow lrow--ability" data-changed="true">
              <span className="lrow__label">{ABILITY_FIELD_LABEL[field]}</span>
              {was !== undefined ? (
                <span
                  className="lrow__diff"
                  aria-label={`was ${was || "none"}, now ${now || "none"}`}
                >
                  <span className="lrow__was" aria-hidden="true">
                    {was || "—"}
                  </span>
                  <span className="lrow__arrow" aria-hidden="true">
                    →
                  </span>
                  <span className="lrow__now" aria-hidden="true">
                    {now || "—"}
                  </span>
                </span>
              ) : (
                <span className="lrow__value">
                  {now || <span className="lrow__empty">—</span>}
                  <span className="ability-diff__new">new</span>
                </span>
              )}
            </div>
          ))}
        </section>
      )}

      <form
        className="editor-form"
        onSubmit={(e) => {
          e.preventDefault();
          void handleSave();
        }}
      >
        <div className="editor-form__grid">
          <TextField
            id="ability-name"
            label="Name"
            value={form.name}
            onChange={(v) => set("name", v)}
          />
          <TextField
            id="ability-id"
            label="chrooked_id"
            hint={isNew ? "the file name" : "fixed"}
            mono
            value={form.chrooked_id}
            readOnly={!isNew}
            onChange={(v) => set("chrooked_id", v)}
          />
          <TextAreaField
            id="ability-description"
            label="Description"
            full
            value={form.description}
            onChange={(v) => set("description", v)}
          />
          <fieldset id="ability-behaviors" className="editor-form__full field">
            <legend className="field__label">
              Behaviors
              <span className="field__hint">
                {" · "}
                leave empty to use this ability&apos;s own behavior
              </span>
            </legend>
            <p id="ability-behaviors-summary" className="field__hint">
              {form.behaviors.length === 0
                ? "Uses its own behavior."
                : form.behaviors.length === 1
                  ? `Alias — behaves exactly as ${form.behaviors[0]}.`
                  : `Combo — built from ${form.behaviors.join(" + ")}.`}
            </p>
            <div className="ability-behaviors__options" role="group"
                 aria-describedby="ability-behaviors-summary">
              {allBehaviors.map((b) => (
                <label
                  key={b.chrooked_id}
                  className="ability-behaviors__option"
                  htmlFor={`ability-behavior-${b.chrooked_id}`}
                >
                  <input
                    id={`ability-behavior-${b.chrooked_id}`}
                    type="checkbox"
                    checked={form.behaviors.includes(b.chrooked_id)}
                    onChange={() => toggleBehavior(b.chrooked_id)}
                  />
                  <span>{b.name}</span>
                  <span className="mono field__hint">{b.chrooked_id}</span>
                </label>
              ))}
            </div>
          </fieldset>
        </div>

        {(error !== null || del.error !== null) && (
          <FormError
            key={`${error ?? ""}|${del.error ?? ""}|${(del.citing ?? []).join(",")}`}
            message={error ?? del.error ?? ""}
            citing={del.citing}
          />
        )}

        <div className="editor-actions">
          {!isNew &&
            (del.citing !== null ? (
              <button
                type="button"
                className="btn btn--danger"
                disabled={busy}
                onClick={() => void handleDelete(true)}
              >
                Delete anyway
              </button>
            ) : (
              <button
                type="button"
                className="btn btn--danger"
                disabled={busy}
                onClick={() => void handleDelete(false)}
              >
                Delete
              </button>
            ))}
          <span className="editor-actions__spacer" />
          <button type="button" className="btn" disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {isSaving ? "Saving…" : "Save ability"}
          </button>
        </div>
      </form>
    </>
  );

  if (embedded) {
    return formBody;
  }

  return (
    <EditorDialog id="ability-editor" titleId={titleId} onClose={onClose}>
      {formBody}
    </EditorDialog>
  );
}
