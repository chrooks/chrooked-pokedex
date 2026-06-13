/* Create or edit one Ruleset-owned move. Moves are stored whole (not as
   Overrides), so the editor round-trips the entire record — the headline fields
   are editable; the behaviour-carrying fields (effect / argument /
   additional_effects / flags / aka) ride along untouched from the loaded move
   so a quick power tweak never strips a move's mechanic or engine symbol.

   Slice 2a edits the common fields; the behaviour fields get a dedicated editor
   in 2b. Delete runs the citation guard: a move cited by a learnset returns 409,
   and the footer turns into a "Delete anyway" confirm naming the citing species. */

import { useState } from "react";
import { api } from "../../api";
import type { Move } from "../../types";
import { useSubmit } from "../../hooks/useSubmit";
import { EditorDialog } from "./EditorDialog";
import { NumberField, SelectField, TextAreaField, TextField } from "./fields";
import { FormError } from "./FormFeedback";
import "./editors.css";

type Props = {
  /** null = create a new move; otherwise edit this one. */
  move: Move | null;
  onClose: () => void;
  onSaved: () => void;
};

const CATEGORIES = ["physical", "special", "status"] as const;

type MoveForm = {
  name: string;
  chrooked_id: string;
  type: string;
  category: string;
  power: number | "";
  accuracy: number | "";
  pp: number | "";
  priority: number | "";
  target: string;
  description: string;
};

export function MoveEditor({ move, onClose, onSaved }: Props) {
  const isNew = move === null;
  const { isSaving, error, run } = useSubmit();
  const del = useSubmit();
  const [form, setForm] = useState<MoveForm>(() => initialForm(move));

  const titleId = "move-editor-title";

  function set<K extends keyof MoveForm>(key: K, value: MoveForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSave() {
    const id = form.chrooked_id.trim();
    const ok = await run(() => api.putMove(id, buildMove(form, move)));
    if (ok) {
      onSaved();
      onClose();
    }
  }

  async function handleDelete(confirm: boolean) {
    if (move === null) return;
    const ok = await del.run(() => api.deleteMove(move.chrooked_id, confirm));
    if (ok) {
      onSaved();
      onClose();
    }
  }

  const busy = isSaving || del.isSaving;

  return (
    <EditorDialog id="move-editor" titleId={titleId} onClose={onClose}>
      <header className="ledger__head">
        <div className="ledger__head-row">
          <span className="ledger__dex mono">MOVE</span>
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
          {isNew ? "New move" : move.name}
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
            id="move-name"
            label="Name"
            value={form.name}
            onChange={(v) => set("name", v)}
          />
          <TextField
            id="move-id"
            label="chrooked_id"
            hint={isNew ? "the file name" : "fixed"}
            mono
            value={form.chrooked_id}
            readOnly={!isNew}
            onChange={(v) => set("chrooked_id", v)}
          />
          <TextField
            id="move-type"
            label="Type"
            value={form.type}
            onChange={(v) => set("type", v)}
          />
          <SelectField
            id="move-category"
            label="Category"
            value={form.category}
            options={CATEGORIES}
            onChange={(v) => set("category", v)}
          />
          <NumberField
            id="move-power"
            label="Power"
            hint="blank = —"
            min={0}
            value={form.power}
            onChange={(v) => set("power", v)}
          />
          <NumberField
            id="move-accuracy"
            label="Accuracy"
            min={0}
            max={100}
            value={form.accuracy}
            onChange={(v) => set("accuracy", v)}
          />
          <NumberField
            id="move-pp"
            label="PP"
            min={0}
            value={form.pp}
            onChange={(v) => set("pp", v)}
          />
          <NumberField
            id="move-priority"
            label="Priority"
            value={form.priority}
            onChange={(v) => set("priority", v)}
          />
          <TextField
            id="move-target"
            label="Target"
            full
            value={form.target}
            onChange={(v) => set("target", v)}
          />
          <TextAreaField
            id="move-description"
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
            {isSaving ? "Saving…" : "Save move"}
          </button>
        </div>
      </form>
    </EditorDialog>
  );
}

function initialForm(move: Move | null): MoveForm {
  return {
    name: move?.name ?? "",
    chrooked_id: move?.chrooked_id ?? "",
    type: move?.type ?? "",
    category: move?.category ?? "physical",
    power: move?.power ?? "",
    accuracy: move?.accuracy ?? "",
    pp: move?.pp ?? "",
    priority: move?.priority ?? 0,
    target: move?.target ?? "selected",
    description: move?.description ?? "",
  };
}

function buildMove(form: MoveForm, original: Move | null): Move {
  const emptyToNull = (value: number | ""): number | null =>
    value === "" ? null : value;
  return {
    name: form.name.trim(),
    chrooked_id: form.chrooked_id.trim(),
    aka: original?.aka ?? {},
    type: form.type.trim(),
    category: form.category as Move["category"],
    power: emptyToNull(form.power),
    accuracy: emptyToNull(form.accuracy),
    pp: emptyToNull(form.pp),
    description: form.description.trim(),
    // behaviour-carrying fields ride along untouched (2b owns their editor)
    effect: original?.effect ?? "hit",
    argument: original?.argument ?? null,
    additional_effects: original?.additional_effects ?? [],
    flags: original?.flags ?? [],
    priority: form.priority === "" ? 0 : form.priority,
    target: form.target.trim() || "selected",
  };
}
