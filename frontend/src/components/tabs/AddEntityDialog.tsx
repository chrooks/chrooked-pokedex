/* The shared "add an entity" dialog used by BOTH the Moves and Abilities tabs so
   the two stay identical in shape. One EditorDialog shell with a Manual | Generate
   segmented toggle (the makeover .mk-mode language):

     - Manual   → the entity's own editor, embedded (create-only).
     - Generate → the AI create panel (create-only).

   On a successful create BY EITHER PANE the same dialog swaps its body to an
   optional distribute step: a "Created {Name}." line, the matching distribute
   panel prefilled + locked to that entity, and a Done button. Both panes report
   the created name through the same GenerateHelpers.onCreated → the createdRef
   guard keeps the dialog open past the editor's own onClose. (Manual editors fire
   onSaved(name) then onClose() back-to-back, exactly like the create panels.)

   The tab supplies the three panes as render slots; this component owns the toggle
   and the created-name → distribute-step transition. */

import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { EditorDialog } from "../editors/EditorDialog";
import type { DistRow } from "../makeover/distributionDraft";
import "../editors/editors.css";
import "../makeover/makeover.css";

/** Helpers handed to the Generate slot so the create panel can advance the dialog. */
export type GenerateHelpers = {
  /** Report the created entity's name — swaps the body to the distribute step.
      An optional proposed distribution (the generate-ability create-time plan) is
      carried forward so the distribute step opens with those rows prefilled. */
  onCreated: (name: string, distribution?: readonly DistRow[]) => void;
  /** Cancel with no create closes the dialog; a no-op once a create has landed
      (the create panels call onCreated then onClose back-to-back). */
  onCancel: () => void;
};

type Props = {
  id: string;
  titleId: string;
  /** Uppercase kind for the readout header, e.g. "MOVE" / "ABILITY". */
  kindLabel: string;
  /** Sans title for the header, e.g. "Add a move". */
  title: string;
  onClose: () => void;
  renderManual: (helpers: GenerateHelpers) => ReactNode;
  renderGenerate: (helpers: GenerateHelpers) => ReactNode;
  /** Render the distribute step. `initialRows` is the create panel's proposed
      distribution (present only for the generate-ability flow), for prefilling. */
  renderDistribute: (
    createdName: string,
    onDone: () => void,
    initialRows?: readonly DistRow[],
  ) => ReactNode;
};

const MODES = [
  { id: "manual", label: "manual" },
  { id: "generate", label: "generate" },
] as const;
type Mode = (typeof MODES)[number]["id"];

export function AddEntityDialog({
  id,
  titleId,
  kindLabel,
  title,
  onClose,
  renderManual,
  renderGenerate,
  renderDistribute,
}: Props) {
  const [mode, setMode] = useState<Mode>("manual");
  const [createdName, setCreatedName] = useState<string | null>(null);
  // The AI's create-time distribution, carried forward to prefill the distribute
  // step (generate-ability flow); undefined for manual creates and moves.
  const [createdDist, setCreatedDist] = useState<readonly DistRow[] | undefined>(undefined);
  // The create panels fire onCreated then onClose synchronously; a ref lets the
  // onCancel wrapper see the create before the state update flushes and skip the
  // close, so the dialog stays open on the distribute step.
  const createdRef = useRef(false);

  const helpers: GenerateHelpers = {
    onCreated: (name, distribution) => {
      createdRef.current = true;
      setCreatedName(name);
      setCreatedDist(distribution);
    },
    onCancel: () => {
      if (createdRef.current) return;
      onClose();
    },
  };

  return (
    <EditorDialog id={id} titleId={titleId} onClose={onClose}>
      <header className="ledger__head">
        <div className="ledger__head-row">
          <span className="ledger__dex mono">
            {createdName !== null ? "DISTRIBUTE" : `ADD ${kindLabel}`}
          </span>
          <button type="button" className="ledger__close" aria-label="Close" onClick={onClose}>
            Close <kbd className="mono" aria-hidden="true">Esc</kbd>
          </button>
        </div>
        <h2 className="ledger__name" id={titleId}>
          {title}
        </h2>
      </header>

      {createdName !== null ? (
        <div className="mk-create" id={`${id}-distribute-step`}>
          <p className="mk-create__sub mono" id={`${id}-created-note`}>
            Created {createdName}. Distribute it now, or you're done.
          </p>
          {renderDistribute(createdName, onClose, createdDist)}
          <div className="mk-stage__actions">
            <button
              type="button"
              className="mk-btn mk-btn--ghost mono"
              id={`${id}-done`}
              onClick={onClose}
            >
              DONE
            </button>
          </div>
        </div>
      ) : (
        <>
          <div
            className="mk-mode"
            role="group"
            aria-label={`${kindLabel} create mode`}
            id={`${id}-mode`}
          >
            {MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                id={`${id}-mode-${m.id}`}
                className="mk-mode__btn mono"
                data-active={mode === m.id}
                aria-pressed={mode === m.id}
                onClick={() => setMode(m.id)}
              >
                {m.label}
              </button>
            ))}
          </div>
          {mode === "manual" ? renderManual(helpers) : renderGenerate(helpers)}
        </>
      )}
    </EditorDialog>
  );
}
