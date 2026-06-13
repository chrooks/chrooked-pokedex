/* Create or edit one human-owned behavior spec — the mechanic layer the seed
   never touches. A structured form: applies-to, then repeatable effect rows
   (each pinned to a neutral battle trigger from the closed vocabulary),
   acceptance test cases, notes, and engine hints. `aka` rides along untouched.
   Validation (a real trigger, at least one effect) lands server-side and comes
   back as the loader's verbatim 422. Rows carry stable ids so removing a middle
   row never reattaches focus/state to the wrong one. */

import { useState } from "react";
import { api } from "../../api";
import { rowId } from "../../lib/rowId";
import type { Behavior } from "../../types";
import { useSubmit } from "../../hooks/useSubmit";
import { EditorDialog } from "./EditorDialog";
import { SelectField, TextAreaField, TextField } from "./fields";
import { FormError } from "./FormFeedback";
import "./editors.css";

// Mirrors model/behavior_spec.py — the neutral battle hooks an effect attaches to.
const TRIGGERS = [
  "switch-in",
  "turn-order",
  "accuracy-check",
  "damage-calc",
  "on-hit",
  "on-contact",
  "status-apply",
  "stat-change",
  "turn-end",
  "faint",
] as const;

const APPLIES_TO = ["ability", "move"] as const;

type Props = {
  /** null = create a new behavior; otherwise edit this one. */
  behavior: Behavior | null;
  onClose: () => void;
  onSaved: () => void;
};

type EffectRow = { _id: number; summary: string; trigger: string; effect: string; when: string };
type TestRow = { _id: number; given: string; expect: string };
type NoteRow = { _id: number; text: string };
type HintRow = { _id: number; engine: string; hint: string };

type Form = {
  name: string;
  chrooked_id: string;
  applies_to: string;
  effects: EffectRow[];
  tests: TestRow[];
  notes: NoteRow[];
  hints: HintRow[];
};

export function BehaviorEditor({ behavior, onClose, onSaved }: Props) {
  const isNew = behavior === null;
  const { isSaving, error, run } = useSubmit();
  const del = useSubmit();
  const [form, setForm] = useState<Form>(() => initialForm(behavior));

  const titleId = "behavior-editor-title";

  function patch(p: Partial<Form>) {
    setForm((f) => ({ ...f, ...p }));
  }

  async function handleSave() {
    const id = form.chrooked_id.trim();
    const ok = await run(() => api.putBehavior(id, buildBehavior(form, behavior)));
    if (ok) {
      onSaved();
      onClose();
    }
  }

  async function handleDelete() {
    if (behavior === null) return;
    const ok = await del.run(() => api.deleteBehavior(behavior.chrooked_id));
    if (ok) {
      onSaved();
      onClose();
    }
  }

  const busy = isSaving || del.isSaving;

  return (
    <EditorDialog id="behavior-editor" titleId={titleId} onClose={onClose}>
      <header className="ledger__head">
        <div className="ledger__head-row">
          <span className="ledger__dex mono">BEHAVIOR</span>
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
          {isNew ? "New behavior" : behavior.name}
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
            id="behavior-name"
            label="Name"
            value={form.name}
            onChange={(v) => patch({ name: v })}
          />
          <TextField
            id="behavior-id"
            label="chrooked_id"
            hint={isNew ? "the file name" : "fixed"}
            mono
            value={form.chrooked_id}
            readOnly={!isNew}
            onChange={(v) => patch({ chrooked_id: v })}
          />
          <SelectField
            id="behavior-applies"
            label="Applies to"
            full
            value={form.applies_to}
            options={APPLIES_TO}
            onChange={(v) => patch({ applies_to: v })}
          />
        </div>

        {/* Effects ----------------------------------------------------------- */}
        <section className="editor-section" aria-labelledby="behavior-effects-heading">
          <h3 className="editor-section__heading" id="behavior-effects-heading">
            Effects
          </h3>
          <div className="row-list">
            {form.effects.map((effect, i) => (
              <div key={effect._id} className="row-list__row">
                <div className="row-list__body">
                  <TextField
                    id={`effect-${effect._id}-summary`}
                    label="Summary"
                    full
                    value={effect.summary}
                    onChange={(v) => patchEffect(setForm, i, { summary: v })}
                  />
                  <SelectField
                    id={`effect-${effect._id}-trigger`}
                    label="Trigger"
                    full
                    value={effect.trigger}
                    options={TRIGGERS}
                    onChange={(v) => patchEffect(setForm, i, { trigger: v })}
                  />
                  <TextField
                    id={`effect-${effect._id}-when`}
                    label="When"
                    hint="optional condition"
                    full
                    value={effect.when}
                    onChange={(v) => patchEffect(setForm, i, { when: v })}
                  />
                  <TextAreaField
                    id={`effect-${effect._id}-effect`}
                    label="Effect"
                    full
                    value={effect.effect}
                    onChange={(v) => patchEffect(setForm, i, { effect: v })}
                  />
                </div>
                <button
                  type="button"
                  className="row-list__remove"
                  aria-label={`Remove effect ${i + 1}`}
                  onClick={() => removeAt(setForm, "effects", i)}
                >
                  ×
                </button>
              </div>
            ))}
            <button
              type="button"
              className="row-list__add"
              aria-label="Add effect"
              onClick={() =>
                patch({
                  effects: [
                    ...form.effects,
                    { _id: rowId(), summary: "", trigger: TRIGGERS[3], effect: "", when: "" },
                  ],
                })
              }
            >
              + Add effect
            </button>
          </div>
        </section>

        {/* Test cases -------------------------------------------------------- */}
        <section className="editor-section" aria-labelledby="behavior-tests-heading">
          <h3 className="editor-section__heading" id="behavior-tests-heading">
            Test cases
          </h3>
          <div className="row-list">
            {form.tests.map((test, i) => (
              <div key={test._id} className="row-list__row">
                <div className="row-list__body">
                  <TextField
                    id={`test-${test._id}-given`}
                    label="Given"
                    full
                    value={test.given}
                    onChange={(v) => patchTest(setForm, i, { given: v })}
                  />
                  <TextField
                    id={`test-${test._id}-expect`}
                    label="Expect"
                    full
                    value={test.expect}
                    onChange={(v) => patchTest(setForm, i, { expect: v })}
                  />
                </div>
                <button
                  type="button"
                  className="row-list__remove"
                  aria-label={`Remove test case ${i + 1}`}
                  onClick={() => removeAt(setForm, "tests", i)}
                >
                  ×
                </button>
              </div>
            ))}
            <button
              type="button"
              className="row-list__add"
              aria-label="Add test case"
              onClick={() =>
                patch({ tests: [...form.tests, { _id: rowId(), given: "", expect: "" }] })
              }
            >
              + Add test case
            </button>
          </div>
        </section>

        {/* Notes ------------------------------------------------------------- */}
        <section className="editor-section" aria-labelledby="behavior-notes-heading">
          <h3 className="editor-section__heading" id="behavior-notes-heading">
            Notes
          </h3>
          <div className="row-list">
            {form.notes.map((note, i) => (
              <div key={note._id} className="row-list__row row-list__row--inline">
                <div className="row-list__body">
                  <TextField
                    id={`note-${note._id}`}
                    label={`Note ${i + 1}`}
                    full
                    value={note.text}
                    onChange={(v) =>
                      patch({
                        notes: form.notes.map((n, j) =>
                          j === i ? { ...n, text: v } : n,
                        ),
                      })
                    }
                  />
                </div>
                <button
                  type="button"
                  className="row-list__remove"
                  aria-label={`Remove note ${i + 1}`}
                  onClick={() => removeAt(setForm, "notes", i)}
                >
                  ×
                </button>
              </div>
            ))}
            <button
              type="button"
              className="row-list__add"
              aria-label="Add note"
              onClick={() => patch({ notes: [...form.notes, { _id: rowId(), text: "" }] })}
            >
              + Add note
            </button>
          </div>
        </section>

        {/* Engine hints ------------------------------------------------------ */}
        <section className="editor-section" aria-labelledby="behavior-hints-heading">
          <h3 className="editor-section__heading" id="behavior-hints-heading">
            Engine hints
          </h3>
          <div className="row-list">
            {form.hints.map((hint, i) => (
              <div key={hint._id} className="row-list__row">
                <div className="row-list__body">
                  <TextField
                    id={`hint-${hint._id}-engine`}
                    label="Engine"
                    hint="e.g. pokeemerald"
                    full
                    value={hint.engine}
                    onChange={(v) => patchHint(setForm, i, { engine: v })}
                  />
                  <TextAreaField
                    id={`hint-${hint._id}-hint`}
                    label="Hint"
                    full
                    value={hint.hint}
                    onChange={(v) => patchHint(setForm, i, { hint: v })}
                  />
                </div>
                <button
                  type="button"
                  className="row-list__remove"
                  aria-label={`Remove engine hint ${i + 1}`}
                  onClick={() => removeAt(setForm, "hints", i)}
                >
                  ×
                </button>
              </div>
            ))}
            <button
              type="button"
              className="row-list__add"
              aria-label="Add engine hint"
              onClick={() =>
                patch({ hints: [...form.hints, { _id: rowId(), engine: "", hint: "" }] })
              }
            >
              + Add engine hint
            </button>
          </div>
        </section>

        {(error !== null || del.error !== null) && (
          <FormError
            key={`${error ?? ""}|${del.error ?? ""}`}
            message={error ?? del.error ?? ""}
            citing={null}
          />
        )}

        <div className="editor-actions">
          {!isNew && (
            <button
              type="button"
              className="btn btn--danger"
              aria-label={`Delete behavior ${behavior.name}`}
              disabled={busy}
              onClick={() => void handleDelete()}
            >
              Delete
            </button>
          )}
          <span className="editor-actions__spacer" />
          <button type="button" className="btn" disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {isSaving ? "Saving…" : "Save behavior"}
          </button>
        </div>
      </form>
    </EditorDialog>
  );
}

// --- row mutation helpers (functional updates; never mutate state) ---------- #

type RowKey = "effects" | "tests" | "notes" | "hints";

function removeAt(setForm: SetForm, key: RowKey, index: number) {
  setForm((f) => ({ ...f, [key]: f[key].filter((_, i) => i !== index) }));
}

function patchEffect(setForm: SetForm, index: number, p: Partial<EffectRow>) {
  setForm((f) => ({
    ...f,
    effects: f.effects.map((e, i) => (i === index ? { ...e, ...p } : e)),
  }));
}

function patchTest(setForm: SetForm, index: number, p: Partial<TestRow>) {
  setForm((f) => ({
    ...f,
    tests: f.tests.map((t, i) => (i === index ? { ...t, ...p } : t)),
  }));
}

function patchHint(setForm: SetForm, index: number, p: Partial<HintRow>) {
  setForm((f) => ({
    ...f,
    hints: f.hints.map((h, i) => (i === index ? { ...h, ...p } : h)),
  }));
}

type SetForm = React.Dispatch<React.SetStateAction<Form>>;

// --- init + build ----------------------------------------------------------- #

function initialForm(behavior: Behavior | null): Form {
  if (behavior === null) {
    return {
      name: "",
      chrooked_id: "",
      applies_to: "ability",
      effects: [{ _id: rowId(), summary: "", trigger: "damage-calc", effect: "", when: "" }],
      tests: [],
      notes: [],
      hints: [],
    };
  }
  return {
    name: behavior.name,
    chrooked_id: behavior.chrooked_id,
    applies_to: behavior.applies_to,
    effects: behavior.effects.map((e) => ({
      _id: rowId(),
      summary: e.summary,
      trigger: e.trigger,
      effect: e.effect,
      when: e.when ?? "",
    })),
    tests: behavior.test_cases.map((t) => ({
      _id: rowId(),
      given: t.given,
      expect: t.expect,
    })),
    notes: behavior.notes.map((text) => ({ _id: rowId(), text })),
    hints: Object.entries(behavior.engine_hints).map(([engine, hint]) => ({
      _id: rowId(),
      engine,
      hint,
    })),
  };
}

function buildBehavior(form: Form, original: Behavior | null): Behavior {
  return {
    name: form.name.trim(),
    chrooked_id: form.chrooked_id.trim(),
    applies_to: form.applies_to as Behavior["applies_to"],
    aka: original?.aka ?? {},
    effects: form.effects.map((e) => ({
      summary: e.summary.trim(),
      trigger: e.trigger,
      effect: e.effect.trim(),
      when: e.when.trim() || null,
    })),
    test_cases: form.tests
      .filter((t) => t.given.trim() || t.expect.trim())
      .map((t) => ({ given: t.given.trim(), expect: t.expect.trim() })),
    notes: form.notes.map((n) => n.text.trim()).filter((n) => n.length > 0),
    engine_hints: Object.fromEntries(
      form.hints
        .filter((h) => h.engine.trim().length > 0)
        .map((h) => [h.engine.trim(), h.hint.trim()]),
    ),
  };
}
