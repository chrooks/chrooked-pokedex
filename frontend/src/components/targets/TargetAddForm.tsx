/* Register a new Target fork: label, absolute path, engine. The server resolves
   and validates the path (422 if it is missing or not a git repo); we surface
   its verbatim message in the Error State. A controlled inline form rather than
   a dialog — adding a fork is the primary action on an empty panel. */

import { useState } from "react";
import { api, ApiError } from "../../api";
import type { EngineKey } from "../../types";
import {
  ENGINES,
  engineLabel,
  isAddDraftReady,
  normalizeDraft,
  type AddTargetDraft,
} from "../../lib/targets";

type Props = {
  onAdded: () => void;
};

const EMPTY: AddTargetDraft = { label: "", path: "", engine: "pokeemerald" };

export function TargetAddForm({ onAdded }: Props) {
  const [draft, setDraft] = useState<AddTargetDraft>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  function set<K extends keyof AddTargetDraft>(key: K, value: AddTargetDraft[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  async function handleSubmit() {
    if (!isAddDraftReady(draft)) return;
    setIsSaving(true);
    setError(null);
    try {
      await api.addTarget(normalizeDraft(draft));
      setDraft(EMPTY);
      onAdded();
    } catch (caught: unknown) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not register the target.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  const ready = isAddDraftReady(draft);

  return (
    <form
      className="target-add"
      id="target-add-form"
      onSubmit={(event) => {
        event.preventDefault();
        void handleSubmit();
      }}
    >
      <div className="target-add__row">
        <label className="target-add__field">
          <span className="target-add__label">Label</span>
          <input
            id="target-add-label"
            className="target-add__input"
            type="text"
            placeholder="Dreamstone"
            value={draft.label}
            onChange={(event) => set("label", event.target.value)}
          />
        </label>
        <label className="target-add__field target-add__field--path">
          <span className="target-add__label">Absolute path to the game directory</span>
          <input
            id="target-add-path"
            className="target-add__input mono"
            type="text"
            placeholder="/Users/you/ROMs/dreamstone"
            value={draft.path}
            onChange={(event) => set("path", event.target.value)}
          />
        </label>
        <label className="target-add__field">
          <span className="target-add__label">Engine</span>
          <select
            id="target-add-engine"
            className="target-add__input"
            value={draft.engine}
            onChange={(event) => set("engine", event.target.value as EngineKey)}
          >
            {ENGINES.map((engine) => (
              <option key={engine} value={engine}>
                {engineLabel(engine)}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          id="targets-add-button"
          className="btn btn--primary target-add__submit"
          disabled={!ready || isSaving}
        >
          {isSaving ? "Adding…" : "Add target"}
        </button>
      </div>

      {error !== null && (
        <p className="target-add__error" id="target-add-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
