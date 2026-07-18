import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faFilter,
  faClockRotateLeft,
  faPen,
  faXmark,
  faExpand,
  faCompress,
  faChevronLeft,
  faChevronRight,
} from "@fortawesome/free-solid-svg-icons";
import type { CanonicalMethod, DexEntry, KindKey } from "../types";
import { useUrlState } from "../hooks/useUrlState";
import { appendNameFilter } from "../lib/dexFilters";
import { STAT_ORDER, STAT_LABEL, bst, dexLabel, isEdited } from "../lib/format";
import { EditedLed } from "./EditedLed";
import { DexSprite } from "./DexSprite";
import { StatRow } from "./ledger/StatRow";
import { BstRow } from "./ledger/BstRow";
import { AbilityRow } from "./ledger/AbilityRow";
import { LearnsetSection } from "./ledger/LearnsetSection";
import { EvolutionSection } from "./ledger/EvolutionSection";
import { TypesRow } from "./ledger/TypesRow";
import { TypeMatchupsSection } from "./ledger/TypeMatchupsSection";
import { SpeciesEditor } from "./editors/SpeciesEditor";
import { ProposedColumn } from "./proposal/ProposedColumn";
import { LearnsetProposal } from "./proposal/LearnsetLineProposal";
import { abilitiesRenderer } from "./proposal/abilitiesRenderer";
import { suggestAbilityCall } from "./proposal/suggestCalls";
import {
  shouldExpandLedger,
  updateActiveSet,
} from "./proposal/activeProposals";
import "./detail-ledger.css";
import "./editors/editors.css";

/** Jump to a cross-linked entity's page and open its read-only detail (#28).
    `kind` picks the destination tab; `key` is the type name (type-chart) or the
    move/ability display name (the tab resolves it to its record). */
export type NavHandler = (kind: KindKey, key: string) => void;

type Props = {
  entry: DexEntry;
  onClose: () => void;
  /** Step to the previous (-1) / next (+1) species in the visible dex order.
      Bound to the header arrows and the ←/→ keys. */
  onStep: (delta: -1 | 1) => void;
  /** Refetch the dex after a save/delete so the merged view reflects the edit. */
  onSaved: () => void;
  /** Cross-link out of the profile to a type / move / ability (#28). */
  onNavigate: NavHandler;
  /** Known ability names (base + owned) for the species editor's comboboxes. */
  abilityOptions: readonly string[];
  /** Known move names for the learnset comboboxes. */
  moveOptions: readonly string[];
  /** Known species names for the evo-from combobox. */
  speciesOptions: readonly string[];
  /** Canonical evolution methods for the editor's Method dropdown. */
  evolutionMethods: readonly CanonicalMethod[];
  /** Active backdrop target id — passed to DexSprite for the target-sprite fallback. */
  backdropTargetId?: string | null;
  /** True when this species renders as the full-page ledger (vs the side panel). */
  full: boolean;
  /** Flip between the side panel and full-page ledger (also bound to `f`). */
  onToggleFull: () => void;
};

/**
 * The species detail as a mono ledger. The diff toggle (shown only when the
 * Ruleset edited this species) flips every overridden field from its clean
 * merged value to a base → now reading. The toggle defaults off: calm first,
 * the diff one tap away (Progressive Disclosure). "Edit" swaps the read-only
 * ledger for the {@link SpeciesEditor} in place.
 */
export function DetailLedger({
  entry,
  onClose,
  onStep,
  onSaved,
  onNavigate,
  abilityOptions,
  moveOptions,
  speciesOptions,
  evolutionMethods,
  backdropTargetId,
  full,
  onToggleFull,
}: Props) {
  const [showDiff, setShowDiff] = useState(false);
  const [editing, setEditing] = useState(false);
  // Which proposal sections are mid-flow + whether the author manually collapsed
  // the panel — together decide the auto-expand (ac8 / P1). Logic in
  // activeProposals.ts (pure, unit-guarded).
  const [activeProposals, setActiveProposals] = useState<ReadonlySet<string>>(
    new Set(),
  );
  const [manuallyCollapsed, setManuallyCollapsed] = useState(false);
  const edited = isEdited(entry);
  const panelRef = useRef<HTMLElement>(null);
  const [view, update] = useUrlState();

  const handleProposalActive = useCallback(
    (sectionId: string, isActive: boolean) => {
      setActiveProposals((prev) => updateActiveSet(prev, sectionId, isActive));
    },
    [],
  );

  const hasActiveProposal = activeProposals.size > 0;
  const expanded = shouldExpandLedger(activeProposals, manuallyCollapsed);

  // "Add to filter": append a Name pill for this species to the dex filter and
  // drop back to the (now filtered) dex list. Dedup-safe via appendNameFilter, so
  // re-adding the same species is a no-op. Closes the profile so the list shows.
  function handleAddToFilter() {
    const next = appendNameFilter(view.filter, entry.name, crypto.randomUUID());
    update({ kind: "dex", filter: next, selected: null });
  }

  // On a species change (and first open): reset the diff/edit mode and move
  // focus into the dialog. One effect, all "react to the open species".
  useEffect(() => {
    setShowDiff(false);
    setEditing(false);
    setActiveProposals(new Set());
    setManuallyCollapsed(false);
    panelRef.current?.focus();
  }, [entry.chrooked_id]);

  // ←/→ step through the visible dex order while the read-only profile is
  // open. Off while editing, and ignored when the key lands in a field.
  useEffect(() => {
    if (editing) return;
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      const target = event.target as HTMLElement;
      if (["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
      event.preventDefault();
      onStep(event.key === "ArrowLeft" ? -1 : 1);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [editing, onStep]);

  const head = (
    <header className="ledger__head">
          <div className="ledger__head-row">
            <div className="ledger__head-id">
              {!editing && (
                <span className="ledger__steppers" role="group" aria-label="Browse species">
                  <button
                    type="button"
                    id="ledger-prev"
                    className="ledger__step"
                    onClick={() => onStep(-1)}
                    title="Previous species (←)"
                    aria-label="Previous species"
                  >
                    <FontAwesomeIcon icon={faChevronLeft} aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    id="ledger-next"
                    className="ledger__step"
                    onClick={() => onStep(1)}
                    title="Next species (→)"
                    aria-label="Next species"
                  >
                    <FontAwesomeIcon icon={faChevronRight} aria-hidden="true" />
                  </button>
                </span>
              )}
              <span className="ledger__dex mono">{dexLabel(entry.dex)}</span>
              {edited && <EditedLed on variant="tag" />}
            </div>
            <div className="ledger__head-actions">
              {!editing && (
                <div className="ledger__tools" role="group" aria-label="Species actions">
                  {hasActiveProposal && (
                    <button
                      type="button"
                      id="ledger-width-toggle"
                      className="ledger__tool"
                      aria-pressed={expanded}
                      title={
                        expanded
                          ? "Collapse the proposal panel"
                          : "Expand the proposal panel"
                      }
                      onClick={() => setManuallyCollapsed((v) => !v)}
                    >
                      <span aria-hidden="true">{expanded ? "⇥" : "⇤"}</span>
                      <span className="ledger__tool-label">
                        {expanded ? "Collapse" : "Expand"}
                      </span>
                    </button>
                  )}
                  <button
                    type="button"
                    id="ledger-add-to-filter"
                    className="ledger__tool"
                    onClick={handleAddToFilter}
                    title={`Filter the dex to ${entry.name}`}
                    aria-label={`Add ${entry.name} to the dex filter`}
                  >
                    <FontAwesomeIcon icon={faFilter} aria-hidden="true" />
                    <span className="ledger__tool-label">Filter</span>
                  </button>
                  <button
                    type="button"
                    id="entity-history-button"
                    className="ledger__tool"
                    onClick={() =>
                      update({ kind: "ledger", query: entry.chrooked_id, selected: null })
                    }
                    title={`Change history for ${entry.name}`}
                  >
                    <FontAwesomeIcon icon={faClockRotateLeft} aria-hidden="true" />
                    <span className="ledger__tool-label">History</span>
                  </button>
                  <button
                    type="button"
                    id="ledger-mode-toggle"
                    className="ledger__tool"
                    aria-pressed={full}
                    onClick={onToggleFull}
                    title={full ? "Back to side panel" : "Open full page (press f)"}
                  >
                    <FontAwesomeIcon
                      icon={full ? faCompress : faExpand}
                      aria-hidden="true"
                    />
                    <span className="ledger__tool-label">
                      {full ? "Side panel" : "Full page"}
                    </span>
                  </button>
                  <button
                    type="button"
                    id="ledger-edit"
                    className="ledger__tool ledger__tool--accent"
                    onClick={() => setEditing(true)}
                  >
                    <FontAwesomeIcon icon={faPen} aria-hidden="true" />
                    <span className="ledger__tool-label">Edit</span>
                  </button>
                </div>
              )}
              <button
                type="button"
                className="ledger__close"
                onClick={onClose}
                aria-label="Close detail"
                title="Close (Esc)"
              >
                <FontAwesomeIcon icon={faXmark} aria-hidden="true" />
              </button>
            </div>
          </div>
          <div className="ledger__title-row">
            <DexSprite
              chrookedId={entry.chrooked_id}
              dex={entry.dex}
              name={entry.name}
              backdropTargetId={backdropTargetId}
              size={128}
            />
            <div>
              <h2 className="ledger__name" id="ledger-title">
                {entry.name}
              </h2>
              <TypesRow
                now={entry.types}
                was={entry.base.types}
                showDiff={showDiff}
                onNavigate={editing ? undefined : onNavigate}
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
  );

  const body = editing ? (
    <SpeciesEditor
      entry={entry}
      onDone={() => setEditing(false)}
      onSaved={onSaved}
      abilityOptions={abilityOptions}
      moveOptions={moveOptions}
      speciesOptions={speciesOptions}
      evolutionMethods={evolutionMethods}
      backdropTargetId={backdropTargetId}
    />
  ) : (
    <DetailBody
      entry={entry}
      showDiff={showDiff}
      columns={full}
      onNavigate={onNavigate}
      onSaved={onSaved}
      abilityOptions={abilityOptions}
      moveOptions={moveOptions}
      onProposalActive={handleProposalActive}
      backdropTargetId={backdropTargetId}
    />
  );

  // Full page: a pane docked over the dex main area (the rail stays), body laid
  // out in responsive columns. Side panel: the overlay + scrim + narrow aside.
  if (full) {
    return (
      <aside
        className="ledger ledger--full"
        id="dex-detail"
        ref={panelRef}
        tabIndex={-1}
        role="region"
        aria-labelledby="ledger-title"
      >
        {head}
        <div className="ledger__body ledger__body--cols">{body}</div>
      </aside>
    );
  }

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
        className={`ledger${expanded ? " ledger--wide" : ""}`}
        id="dex-detail"
        data-expanded={expanded}
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ledger-title"
      >
        {head}
        {body}
      </aside>
    </div>
  );
}

type BodyProps = {
  entry: DexEntry;
  showDiff: boolean;
  /** Read-only-only cross-links out to types / moves / abilities (#28). */
  onNavigate: NavHandler;
  /** Refetch the dex after an Apply so the merged view reflects the change. */
  onSaved: () => void;
  /** Known ability names for the proposed-abilities slot selects. */
  abilityOptions: readonly string[];
  /** Known move names for the learnset proposal editor. */
  moveOptions: readonly string[];
  /** Report a section's active/idle proposal state up to the ledger (ac8). */
  onProposalActive: (sectionId: string, isActive: boolean) => void;
  backdropTargetId?: string | null;
  /** Full-page layout: split the sections into two columns instead of stacking. */
  columns: boolean;
};

/** Press `s` on a focused proposal section to open its `✦ suggest` input —
    keyboard-first (PRODUCT.md). Ignores `s` typed into a field. */
function handleSectionKey(
  event: KeyboardEvent<HTMLElement>,
  suggestButtonId: string,
) {
  if (event.key !== "s") return;
  const target = event.target as HTMLElement;
  if (
    target.tagName === "INPUT" ||
    target.tagName === "SELECT" ||
    target.tagName === "TEXTAREA"
  ) {
    return;
  }
  const button = document.getElementById(suggestButtonId);
  if (button) {
    event.preventDefault();
    (button as HTMLButtonElement).click();
  }
}

function DetailBody({
  entry,
  showDiff,
  onNavigate,
  onSaved,
  abilityOptions,
  moveOptions,
  onProposalActive,
  backdropTargetId,
  columns,
}: BodyProps) {
  const statsSection = (
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
  );

  const abilitiesSection = (
    <section
      className="ledger__section"
      aria-label="Abilities"
      tabIndex={0}
      onKeyDown={(e) => handleSectionKey(e, "proposal-abilities-suggest")}
    >
      <ProposedColumn
        entry={entry}
        renderer={abilitiesRenderer(abilityOptions, entry)}
        suggest={suggestAbilityCall}
        onApplied={onSaved}
        onActiveChange={onProposalActive}
      >
        <div className="ledger__abilities">
          {(["primary", "secondary", "hidden"] as const).map((slot) => (
            <AbilityRow
              key={slot}
              slot={slot}
              now={entry.abilities[slot]}
              was={entry.base.abilities?.[slot]}
              showDiff={showDiff}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      </ProposedColumn>
    </section>
  );

  const learnsetSection = (
    <section
      className="ledger__section"
      aria-label="Learnset"
      tabIndex={0}
      onKeyDown={(e) => handleSectionKey(e, "proposal-learnset-suggest")}
    >
      <LearnsetProposal
        entry={entry}
        moveOptions={moveOptions}
        onSaved={onSaved}
        onProposalActive={onProposalActive}
        backdropTargetId={backdropTargetId}
      >
        <LearnsetSection
          now={entry.learnset}
          was={entry.base.learnset}
          showDiff={showDiff}
          onNavigate={onNavigate}
          bare
        />
      </LearnsetProposal>
    </section>
  );

  const evolutionSection = (
    <EvolutionSection
      evolution={entry.evolution}
      evolvesInto={entry.evolves_into}
      onNavigate={onNavigate}
      backdropTargetId={backdropTargetId}
    />
  );

  const matchupsSection = (
    <TypeMatchupsSection types={entry.types} abilities={entry.abilities} />
  );

  // Full page: three purpose-sized columns instead of a stretched two-column
  // panel — vitals (stats + abilities + evolution) narrow, matchups mid,
  // learnset wide (it sets two-up internally to use the room). Panel: the
  // single-column stack.
  if (columns) {
    return (
      <>
        <div className="ledger__col ledger__col--vitals">
          {statsSection}
          {abilitiesSection}
          {evolutionSection}
        </div>
        <div className="ledger__col ledger__col--matchups">{matchupsSection}</div>
        <div className="ledger__col ledger__col--learnset">{learnsetSection}</div>
      </>
    );
  }

  return (
    <>
      {statsSection}
      {abilitiesSection}
      {matchupsSection}
      {learnsetSection}
      {evolutionSection}
    </>
  );
}
