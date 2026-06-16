/* Create or edit one Ruleset-owned ability (data only — the mechanic lives in a
   behavior spec, edited in 2b). aka rides along from the loaded ability so an
   edit doesn't strip the engine symbol. Delete runs the citation guard: an
   ability a species' slot still cites returns 409, and the footer becomes a
   "Delete anyway" confirm naming the citing species. */

import { useState } from "react";
import { api } from "../../api";
import type { Ability, AbilityField, AbilityWrite, DexEntry } from "../../types";
import { useSubmit } from "../../hooks/useSubmit";
import { useUrlState } from "../../hooks/useUrlState";
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
  /** Species that have this ability in any slot (primary, secondary, hidden).
      Empty for a new ability. */
  usedBy: DexEntry[];
  onClose: () => void;
  onSaved: () => void;
};

type AbilityForm = { name: string; chrooked_id: string; description: string };

export function AbilityEditor({ ability, usedBy, onClose, onSaved }: Props) {
  const isNew = ability === null;
  const { isSaving, error, run } = useSubmit();
  const del = useSubmit();
  const [, updateView] = useUrlState();
  const [form, setForm] = useState<AbilityForm>(() => ({
    name: ability?.name ?? "",
    chrooked_id: ability?.chrooked_id ?? "",
    description: ability?.description ?? "",
  }));

  const titleId = "ability-editor-title";

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
    };
    const ok = await run(() => api.putAbility(id, payload));
    if (ok) {
      onSaved();
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

  /** Navigate to the dex screen with the given species selected so the
      DetailLedger opens. Single source of truth: uses existing useUrlState. */
  function goToSpecies(species: DexEntry) {
    updateView({ kind: "dex", selected: species.chrooked_id });
    onClose();
  }

  return (
    <EditorDialog id="ability-editor" titleId={titleId} onClose={onClose}>
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

      {!isNew && (
        <section
          id="ability-used-by"
          className="editor-section"
          aria-label="Species that have this ability"
        >
          <h3 className="editor-section__heading">
            Used by
            {usedBy.length > 0 && (
              <span className="reverse-lookup__count"> ({usedBy.length})</span>
            )}
          </h3>
          {usedBy.length === 0 ? (
            <p className="reverse-lookup__empty">No species have this ability.</p>
          ) : (
            <ul id="ability-used-by-list" className="reverse-lookup__list">
              {usedBy.map((species) => (
                <li key={species.chrooked_id}>
                  <button
                    type="button"
                    id={`ability-user-${species.chrooked_id}`}
                    className="reverse-lookup__species-btn"
                    onClick={() => goToSpecies(species)}
                  >
                    {species.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
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
    </EditorDialog>
  );
}
