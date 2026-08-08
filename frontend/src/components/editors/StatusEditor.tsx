/* Edit one status condition — name, player-facing description, and the plain
   language effect lines. `aka` rides along untouched so the engine symbol a
   reskin depends on survives an edit (frostbite keeps rejuv: FROZEN).
   Validation lands server-side and comes back as the loader's verbatim 422.
   There is no create or delete: the status set is closed, and adding one means
   teaching an engine a new condition, which is a Ruleset + applier job. */

import { useState } from "react";
import { api } from "../../api";
import { rowId } from "../../lib/rowId";
import type { Status } from "../../types";
import { useSubmit } from "../../hooks/useSubmit";
import { EditorDialog } from "./EditorDialog";
import { TextAreaField, TextField } from "./fields";
import { FormError } from "./FormFeedback";
import "./editors.css";

type Props = {
  status: Status;
  onClose: () => void;
  onSaved: () => void;
};

/** Rows carry a stable id so removing a middle row never reattaches state to
    the wrong one — same reason BehaviorEditor does it. */
type EffectRow = { _id: number; text: string };

type Form = {
  name: string;
  description: string;
  effects: EffectRow[];
};

function initialForm(status: Status): Form {
  return {
    name: status.name,
    description: status.description,
    effects: status.effects.map((text) => ({ _id: rowId(), text })),
  };
}

export function StatusEditor({ status, onClose, onSaved }: Props) {
  const { isSaving, error, run } = useSubmit();
  const [form, setForm] = useState<Form>(() => initialForm(status));

  const titleId = "status-editor-title";

  function patch(p: Partial<Form>) {
    setForm((f) => ({ ...f, ...p }));
  }

  function patchEffect(id: number, text: string) {
    setForm((f) => ({
      ...f,
      effects: f.effects.map((row) => (row._id === id ? { ...row, text } : row)),
    }));
  }

  function addEffect() {
    setForm((f) => ({ ...f, effects: [...f.effects, { _id: rowId(), text: "" }] }));
  }

  function removeEffect(id: number) {
    setForm((f) => ({ ...f, effects: f.effects.filter((row) => row._id !== id) }));
  }

  async function handleSave() {
    const payload: Status = {
      ...status,
      name: form.name.trim(),
      description: form.description.trim(),
      effects: form.effects.map((row) => row.text.trim()).filter((t) => t !== ""),
    };
    const ok = await run(() => api.putStatus(status.chrooked_id, payload));
    if (ok) {
      onSaved();
      onClose();
    }
  }

  return (
    <EditorDialog id="status-editor" titleId={titleId} onClose={onClose}>
      <header className="ledger__head">
        <div className="ledger__head-row">
          <span className="ledger__dex mono">STATUS</span>
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
          {status.name}
        </h2>
      </header>

      <form
        className="editor-form"
        aria-labelledby={titleId}
        onSubmit={(e) => {
          e.preventDefault();
          void handleSave();
        }}
      >
        <div className="editor-form__grid">
          <TextField
            id="status-editor-name"
            label="Name"
            value={form.name}
            onChange={(v) => patch({ name: v })}
          />
          <TextField
            id="status-editor-id"
            label="chrooked_id"
            hint="fixed"
            mono
            value={status.chrooked_id}
            readOnly
            onChange={() => undefined}
          />
          <TextAreaField
            id="status-editor-description"
            label="Description"
            full
            value={form.description}
            onChange={(v) => patch({ description: v })}
          />
        </div>

        <fieldset className="editor-form__set" id="status-editor-effects">
          <legend>Effects</legend>
          {form.effects.map((row, index) => (
            <div key={row._id} className="editor-form__row">
              <TextField
                id={`status-editor-effect-${index}`}
                label={`Effect ${index + 1}`}
                full
                value={row.text}
                onChange={(v) => patchEffect(row._id, v)}
              />
              <button
                type="button"
                className="btn btn--ghost"
                aria-label={`Remove effect ${index + 1}`}
                onClick={() => removeEffect(row._id)}
              >
                Remove
              </button>
            </div>
          ))}
          <button
            type="button"
            className="btn btn--ghost"
            id="status-editor-add-effect"
            onClick={addEffect}
          >
            + Add effect
          </button>
        </fieldset>

        {error !== null && (
          <FormError key={error} message={error} citing={null} />
        )}

        <div className="editor-form__actions">
          <button
            type="submit"
            className="btn btn--primary"
            id="status-editor-save"
            disabled={isSaving}
          >
            {isSaving ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </EditorDialog>
  );
}
