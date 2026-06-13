/* Create or edit one Ruleset-owned ability (data only — the mechanic lives in a
   behavior spec, edited in 2b). aka rides along from the loaded ability so an
   edit doesn't strip the engine symbol. Delete runs the citation guard: an
   ability a species' slot still cites returns 409, and the footer becomes a
   "Delete anyway" confirm naming the citing species. */

import { useState } from "react";
import { api } from "../../api";
import type { Ability } from "../../types";
import { useSubmit } from "../../hooks/useSubmit";
import { EditorDialog } from "./EditorDialog";
import { TextAreaField, TextField } from "./fields";
import { FormError } from "./FormFeedback";
import "./editors.css";

type Props = {
  /** null = create a new ability; otherwise edit this one. */
  ability: Ability | null;
  onClose: () => void;
  onSaved: () => void;
};

type AbilityForm = { name: string; chrooked_id: string; description: string };

export function AbilityEditor({ ability, onClose, onSaved }: Props) {
  const isNew = ability === null;
  const { isSaving, error, run } = useSubmit();
  const del = useSubmit();
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
    const payload: Ability = {
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

  return (
    <EditorDialog id="ability-editor" titleId={titleId} onClose={onClose}>
      <header className="ledger__head">
        <div className="ledger__head-row">
          <span className="ledger__dex mono">ABILITY</span>
          <button type="button" className="ledger__close" onClick={onClose}>
            Close <kbd className="mono">Esc</kbd>
          </button>
        </div>
        <h2 className="ledger__name" id={titleId}>
          {isNew ? "New ability" : ability.name}
        </h2>
      </header>

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
