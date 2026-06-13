import { useEffect, useRef, useState } from "react";
import type { DexEntry } from "../types";
import { STAT_ORDER, STAT_LABEL, bst, dexLabel, isEdited } from "../lib/format";
import { spriteUrl } from "../lib/sprites";
import { EditedLed } from "./EditedLed";
import { StatRow } from "./ledger/StatRow";
import { BstRow } from "./ledger/BstRow";
import { AbilityRow } from "./ledger/AbilityRow";
import { LearnsetSection } from "./ledger/LearnsetSection";
import { EvolutionSection } from "./ledger/EvolutionSection";
import { TypesRow } from "./ledger/TypesRow";
import { SpeciesEditor } from "./editors/SpeciesEditor";
import "./detail-ledger.css";
import "./editors/editors.css";

type Props = {
  entry: DexEntry;
  onClose: () => void;
  /** Refetch the dex after a save/delete so the merged view reflects the edit. */
  onSaved: () => void;
  /** Known ability names (base + owned) for the species editor's comboboxes. */
  abilityOptions: readonly string[];
};

/**
 * The species detail as a mono ledger. The diff toggle (shown only when the
 * Ruleset edited this species) flips every overridden field from its clean
 * merged value to a base → now reading. The toggle defaults off: calm first,
 * the diff one tap away (Progressive Disclosure). "Edit" swaps the read-only
 * ledger for the {@link SpeciesEditor} in place.
 */
export function DetailLedger({ entry, onClose, onSaved, abilityOptions }: Props) {
  const [showDiff, setShowDiff] = useState(false);
  const [editing, setEditing] = useState(false);
  const edited = isEdited(entry);
  const panelRef = useRef<HTMLElement>(null);
  const sprite = spriteUrl(entry.chrooked_id, entry.dex);

  // On a species change (and first open): reset the diff/edit mode and move
  // focus into the dialog. One effect, all "react to the open species".
  useEffect(() => {
    setShowDiff(false);
    setEditing(false);
    panelRef.current?.focus();
  }, [entry.chrooked_id]);

  return (
    <div className="ledger-overlay">
      <button
        type="button"
        className="ledger-overlay__scrim"
        aria-label="Close detail"
        tabIndex={-1}
        onClick={onClose}
      />
      <aside
        className="ledger"
        id="dex-detail"
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ledger-title"
      >
        <header className="ledger__head">
          <div className="ledger__head-row">
            <span className="ledger__dex mono">{dexLabel(entry.dex)}</span>
            <div className="ledger__head-actions">
              {edited && <EditedLed on variant="tag" />}
              {!editing && (
                <button
                  type="button"
                  className="ledger__edit"
                  onClick={() => setEditing(true)}
                >
                  Edit
                </button>
              )}
              <button type="button" className="ledger__close" onClick={onClose}>
                Close <kbd className="mono">Esc</kbd>
              </button>
            </div>
          </div>
          <div className="ledger__title-row">
            {sprite !== null && (
              <img
                className="ledger__sprite"
                src={sprite}
                alt={entry.name}
                width={88}
                height={88}
                decoding="async"
              />
            )}
            <div>
              <h2 className="ledger__name" id="ledger-title">
                {entry.name}
              </h2>
              <TypesRow
                now={entry.types}
                was={entry.base.types}
                showDiff={showDiff}
              />
            </div>
          </div>

          {edited && !editing && (
            <button
              type="button"
              className="ledger__diff-toggle"
              data-on={showDiff}
              aria-pressed={showDiff}
              onClick={() => setShowDiff((v) => !v)}
            >
              <span className="ledger__diff-lamp" aria-hidden="true" />
              {showDiff ? "Showing base → now" : "Show what changed"}
            </button>
          )}
        </header>

        {editing ? (
          <SpeciesEditor
            entry={entry}
            onDone={() => setEditing(false)}
            onSaved={onSaved}
            abilityOptions={abilityOptions}
          />
        ) : (
          <DetailBody entry={entry} showDiff={showDiff} />
        )}
      </aside>
    </div>
  );
}

type BodyProps = { entry: DexEntry; showDiff: boolean };

function DetailBody({ entry, showDiff }: BodyProps) {
  return (
    <>
      <section className="ledger__section" aria-label="Base stats">
          <h3 className="ledger__heading">Base stats</h3>
          <div className="ledger__stats">
            {STAT_ORDER.map((key) => (
              <StatRow
                key={key}
                label={STAT_LABEL[key]}
                now={entry.stats[key]}
                was={entry.base.stats?.[key]}
                showDiff={showDiff}
              />
            ))}
            <BstRow
              now={bst(entry.stats)}
              was={entry.base.stats ? bst(entry.base.stats) : undefined}
              showDiff={showDiff}
            />
          </div>
        </section>

        <section className="ledger__section" aria-label="Abilities">
          <h3 className="ledger__heading">Abilities</h3>
          <div className="ledger__abilities">
            {(["primary", "secondary", "hidden"] as const).map((slot) => (
              <AbilityRow
                key={slot}
                slot={slot}
                now={entry.abilities[slot]}
                was={entry.base.abilities?.[slot]}
                showDiff={showDiff}
              />
            ))}
          </div>
        </section>

        <LearnsetSection
          now={entry.learnset}
          was={entry.base.learnset}
          showDiff={showDiff}
        />

        <EvolutionSection evolution={entry.evolution} />
    </>
  );
}
