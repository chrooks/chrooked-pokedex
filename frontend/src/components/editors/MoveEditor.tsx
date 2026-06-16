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
import type { DexEntry, Move, MoveField, MoveWrite } from "../../types";
import { useSubmit } from "../../hooks/useSubmit";
import { useUrlState } from "../../hooks/useUrlState";
import { isMoveEdited, MOVE_FIELD_LABEL } from "../../lib/format";
import { EditedLed } from "../EditedLed";
import { EditorDialog } from "./EditorDialog";
import { NumberField, SelectField, TextAreaField, TextField } from "./fields";
import { FormError } from "./FormFeedback";
import "./editors.css";
import "../ledger/ledger-rows.css";

type Props = {
  /** null = create a new move; otherwise edit this one. */
  move: Move | null;
  /** Species whose merged learnsets include this move. Empty for a new move. */
  learnedBy: DexEntry[];
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

export function MoveEditor({ move, learnedBy, onClose, onSaved }: Props) {
  const isNew = move === null;
  const { isSaving, error, run } = useSubmit();
  const del = useSubmit();
  const [, updateView] = useUrlState();
  const [form, setForm] = useState<MoveForm>(() => initialForm(move));

  /** Navigate to the dex screen with the given species selected so the
      DetailLedger opens. Single source of truth: uses existing useUrlState. */
  function goToSpecies(species: DexEntry) {
    updateView({ kind: "dex", selected: species.chrooked_id });
    onClose();
  }

  const titleId = "move-editor-title";

  function set<K extends keyof MoveForm>(key: K, value: MoveForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSave() {
    const id = form.chrooked_id.trim();
    // The merged view carries server-recomputed flags (overridden_fields, base)
    // that the move loader rejects as unknown keys (422) — buildMove returns a
    // MoveWrite so only the Ruleset-owned record is sent. Editing a base-only
    // move upserts a Ruleset entry (mirrors species "edit base → make override").
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

  // base → now diff rows for an existing move. An overridden field that has a
  // base value reads `was → now`; a Ruleset-created move (empty base) has the
  // field flagged with no `was`, so it reads as new.
  const edited = move !== null && isMoveEdited(move);
  const currentOf: Partial<Record<MoveField, string>> =
    move !== null ? displayValues(move) : {};
  const diffRows = edited
    ? move.overridden_fields.map((field) => ({
        field,
        was:
          field in move.base
            ? formatValue(move.base[field as keyof typeof move.base])
            : undefined,
        now: currentOf[field] ?? "",
      }))
    : [];

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
          id="move-diff"
          className="ability-diff"
          aria-label="What the Ruleset changed"
        >
          {diffRows.map(({ field, was, now }) => (
            <div key={field} className="lrow lrow--ability" data-changed="true">
              <span className="lrow__label">{MOVE_FIELD_LABEL[field]}</span>
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
          id="move-learned-by"
          className="editor-section"
          aria-label="Species that learn this move"
        >
          <h3 className="editor-section__heading">
            Learned by
            {learnedBy.length > 0 && (
              <span className="reverse-lookup__count"> ({learnedBy.length})</span>
            )}
          </h3>
          {learnedBy.length === 0 ? (
            <p className="reverse-lookup__empty">No species learn this move.</p>
          ) : (
            <ul id="move-learned-by-list" className="reverse-lookup__list">
              {learnedBy.map((species) => (
                <li key={species.chrooked_id}>
                  <button
                    type="button"
                    id={`move-learner-${species.chrooked_id}`}
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

function buildMove(form: MoveForm, original: Move | null): MoveWrite {
  const emptyToNull = (value: number | ""): number | null =>
    value === "" ? null : value;
  // MoveWrite — the merge-view flags (overridden_fields, base) are deliberately
  // absent so the move loader accepts the payload (echoing them back is a 422).
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

/** The current (now) value of each move field as a display string, for the
    base→now diff. Behaviour-carrying fields the editor doesn't surface still get
    a readable rendering so an override on them reads correctly. */
function displayValues(move: Move): Partial<Record<MoveField, string>> {
  return {
    name: move.name,
    type: move.type,
    category: move.category,
    power: formatValue(move.power),
    accuracy: formatValue(move.accuracy),
    pp: formatValue(move.pp),
    description: move.description,
    effect: move.effect,
    argument: formatValue(move.argument),
    additional_effects: formatValue(move.additional_effects),
    flags: move.flags.join(", "),
    priority: formatValue(move.priority),
    target: move.target,
  };
}

/** Render any move field value as a short, neutral display string for the diff
    (numbers verbatim, null/empty as a dash, lists comma-joined, objects JSON). */
function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) {
    return value
      .map((item) => (typeof item === "object" ? JSON.stringify(item) : String(item)))
      .join(", ");
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
