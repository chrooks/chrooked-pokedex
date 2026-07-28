import { useEffect, useRef, useState } from "react";
import {
  deleteTeam,
  loadSavedTeams,
  saveTeam,
  type SavedTeams as SavedTeamsMap,
} from "../../lib/savedTeams";

type Props = {
  /** The current party, already encoded (encodeParty output) — what Save stores. */
  encodedParty: string;
  /** True when the party has at least one member (an empty party can't be saved). */
  canSave: boolean;
  /** Replace the current party from a saved team's encoded string. */
  onLoad: (encoded: string) => void;
};

/** How long the transient "Saved ✓" / "Loaded ✓" confirmation lingers. */
const FEEDBACK_MS = 2200;

type Feedback = { kind: "saved" | "loaded" | "deleted"; text: string } | null;

/**
 * Saved teams (ac8): two clear controls instead of tectonic's one dual-purpose
 * input — a "name this team" text field that only SAVES, and a dropdown of the
 * teams already saved that Load and Delete act on, so loading is a pick, never
 * retyping. Values live in localStorage as encodeParty() strings (the `team`
 * URL param already IS the share code, so there's no separate team-code flow).
 *
 * No blocking dialogs: Save of an empty name is simply disabled, confirmation is
 * a quiet aria-live line that fades, and Delete is a two-step button (Delete →
 * "Confirm?" → gone) instead of window.confirm. It sits under the picker as a
 * subdued strip so it never competes with adding Pokémon.
 */
export function SavedTeams({ encodedParty, canSave, onLoad }: Props) {
  const [teams, setTeams] = useState<SavedTeamsMap>({});
  const [name, setName] = useState("");
  /** The dropdown pick that Load/Delete act on; "" = nothing picked yet. */
  const [selected, setSelected] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  // Two-step delete: armed for the current selection; a second click confirms.
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const timerRef = useRef<number | null>(null);

  // Load once on mount. localStorage is only read client-side; a corrupt key
  // reads back as {} (the lib guards it), so this can't throw.
  useEffect(() => {
    setTeams(loadSavedTeams(window.localStorage));
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, []);

  function flash(next: Feedback) {
    setFeedback(next);
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => setFeedback(null), FEEDBACK_MS);
  }

  const trimmed = name.trim();
  const savedNames = Object.keys(teams).sort((a, b) => a.localeCompare(b));
  const hasTeams = savedNames.length > 0;
  const wouldOverwrite = trimmed !== "" && trimmed in teams;
  const hasSelection = selected !== "" && selected in teams;

  function handleSave() {
    if (trimmed === "" || !canSave) return;
    setTeams(saveTeam(window.localStorage, trimmed, encodedParty));
    // Reflect the fresh save in the dropdown so Load/Delete point at it.
    setSelected(trimmed);
    setName("");
    setConfirmingDelete(false);
    flash({ kind: "saved", text: `Saved “${trimmed}” ✓` });
  }

  function handleLoad() {
    const encoded = teams[selected];
    if (encoded === undefined) return;
    onLoad(encoded);
    setConfirmingDelete(false);
    flash({ kind: "loaded", text: `Loaded “${selected}” ✓` });
  }

  function handleDelete() {
    if (!hasSelection) return;
    if (!confirmingDelete) {
      setConfirmingDelete(true);
      return;
    }
    setTeams(deleteTeam(window.localStorage, selected));
    setConfirmingDelete(false);
    setSelected("");
    flash({ kind: "deleted", text: `Deleted “${selected}”` });
  }

  return (
    <section className="saved-teams" id="saved-teams" aria-label="Saved teams">
      <div className="saved-teams__row">
        <label className="saved-teams__field" htmlFor="saved-teams-name">
          <span className="saved-teams__label">Save team</span>
          <input
            id="saved-teams-name"
            className="saved-teams__input"
            type="text"
            autoComplete="off"
            placeholder="Name this team…"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <div className="saved-teams__actions">
          <button
            type="button"
            id="saved-teams-save"
            className="saved-teams__btn"
            onClick={handleSave}
            disabled={trimmed === "" || !canSave}
            title={
              !canSave
                ? "Add a Pokémon before saving"
                : trimmed === ""
                  ? "Name the team to save it"
                  : wouldOverwrite
                    ? `Overwrite “${trimmed}”`
                    : `Save this team as “${trimmed}”`
            }
          >
            {wouldOverwrite ? "Overwrite" : "Save"}
          </button>
        </div>

        <label className="saved-teams__field" htmlFor="saved-teams-select">
          <span className="saved-teams__label">Saved teams</span>
          <select
            id="saved-teams-select"
            className="saved-teams__input saved-teams__select"
            value={hasSelection ? selected : ""}
            disabled={!hasTeams}
            onChange={(event) => {
              setSelected(event.target.value);
              // A new pick disarms a pending delete so it can't fire on the
              // wrong team.
              setConfirmingDelete(false);
            }}
          >
            <option value="" disabled>
              {hasTeams ? "Pick a saved team…" : "No saved teams yet"}
            </option>
            {savedNames.map((teamName) => (
              <option key={teamName} value={teamName}>
                {teamName}
              </option>
            ))}
          </select>
        </label>

        <div className="saved-teams__actions">
          <button
            type="button"
            id="saved-teams-load"
            className="saved-teams__btn"
            onClick={handleLoad}
            disabled={!hasSelection}
            title={
              hasSelection
                ? `Load “${selected}” (replaces the current team)`
                : "Pick a saved team to load"
            }
          >
            Load
          </button>
          <button
            type="button"
            id="saved-teams-delete"
            className="saved-teams__btn saved-teams__btn--danger"
            onClick={handleDelete}
            disabled={!hasSelection}
            data-confirming={confirmingDelete}
            title={
              hasSelection
                ? confirmingDelete
                  ? `Click again to delete “${selected}”`
                  : `Delete “${selected}”`
                : "Pick a saved team to delete"
            }
          >
            {confirmingDelete && hasSelection ? "Confirm?" : "Delete"}
          </button>
        </div>
      </div>

      <span
        className="saved-teams__feedback"
        role="status"
        aria-live="polite"
        data-show={feedback !== null}
        data-kind={feedback?.kind}
      >
        {feedback?.text ?? ""}
      </span>
    </section>
  );
}
