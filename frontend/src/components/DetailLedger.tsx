import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  faPlus,
  faCheck,
  faWandMagicSparkles,
  faClone,
} from "@fortawesome/free-solid-svg-icons";
import type { CanonicalMethod, DexEntry, KindKey } from "../types";
import { useUrlState } from "../hooks/useUrlState";
import type { DesignStage } from "../lib/makeoverStages";
import { appendNameFilter } from "../lib/dexFilters";
import { MAX_PARTY, replacePartyMember } from "../lib/teamViewCodec";
import { ReplaceDialog } from "./team/ReplaceDialog";
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
import "./proposal/proposal.css";
import "./detail-ledger.css";
import "./editors/editors.css";

/** Jump to a cross-linked entity's page and open its read-only detail (#28).
    `kind` picks the destination tab; `key` is the type name (type-chart) or the
    move/ability display name (the tab resolves it to its record). */
export type NavHandler = (kind: KindKey, key: string) => void;

/** Move name (lowercased) → its type + damage category, so the profile learnset
    can color by type, bold STAB, and italicize the mon's attacking category. */
export type MoveMeta = ReadonlyMap<string, { type: string; category: string }>;

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
  /** Move name (lowercased) → type + category, used to tint/bold/italicize learnset rows. */
  moveMeta: MoveMeta;
  /** Known species names for the evo-from combobox. */
  speciesOptions: readonly string[];
  /** Canonical evolution methods for the editor's Method dropdown. */
  evolutionMethods: readonly CanonicalMethod[];
  /** Active backdrop target id — passed to DexSprite for the target-sprite fallback. */
  backdropTargetId?: string | null;
  /** The full merged dex — used to resolve the current party's ids to entries for
      the full-team replace dialog (ac10). */
  dexEntries: readonly DexEntry[];
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
  moveMeta,
  speciesOptions,
  evolutionMethods,
  backdropTargetId,
  dexEntries,
  full,
  onToggleFull,
}: Props) {
  const [showDiff, setShowDiff] = useState(false);
  const [editing, setEditing] = useState(false);
  // Open when a full-team add needs a swap decision (ac10).
  const [replacing, setReplacing] = useState(false);
  const edited = isEdited(entry);
  const panelRef = useRef<HTMLElement>(null);
  const [view, update] = useUrlState();

  // A section's ✦ suggest deep-links into the Makeover Workbench pre-selected
  // to just that stage — one suggest UX everywhere (the workbench's), instead
  // of a parallel inline flow. An EMPTY seed is the mirror-only wizard.
  const handleSuggest = useCallback(
    (stages: readonly DesignStage[]) =>
      update({
        makeover: entry.chrooked_id,
        makeoverStage: null,
        makeoverSelect: [...stages],
      }),
    [update, entry.chrooked_id],
  );

  // "Add to filter": append a Name pill for this species to the dex filter and
  // drop back to the (now filtered) dex list. Dedup-safe via appendNameFilter, so
  // re-adding the same species is a no-op. Closes the profile so the list shows.
  function handleAddToFilter() {
    const next = appendNameFilter(view.filter, entry.name, crypto.randomUUID());
    update({ kind: "dex", filter: next, selected: null });
  }

  // "Add to team" (ac9): append this species to the Team tab's party. Identity
  // is the same chrooked_id the team codec uses, so `onTeam` also drives the
  // button's confirmed state — clicking add flips it to "On the team ✓" and the
  // control disables, no separate transient needed.
  const onTeam = view.party.some((member) => member.id === entry.chrooked_id);
  const teamFull = view.party.length >= MAX_PARTY;
  // Only a duplicate hard-disables the button now. A full team no longer dead-ends
  // a fresh species — the click opens the replace dialog (ac10) instead.
  const addToTeamDisabled = onTeam;

  // Resolve the current party's ids to entries for the replace dialog's member
  // buttons (sprite + name), keeping each member's true party slot index.
  const partyMembers = useMemo(() => {
    const byId = new Map(dexEntries.map((e) => [e.chrooked_id, e]));
    return view.party
      .map((member, partyIndex) => {
        const memberEntry = byId.get(member.id);
        return memberEntry ? { partyIndex, entry: memberEntry } : null;
      })
      .filter((m): m is { partyIndex: number; entry: DexEntry } => m !== null);
  }, [dexEntries, view.party]);

  function handleAddToTeam() {
    if (onTeam) return;
    if (teamFull) {
      setReplacing(true);
      return;
    }
    update({ party: [...view.party, { id: entry.chrooked_id, ability: null }] });
  }

  function handleReplace(partyIndex: number) {
    update({ party: replacePartyMember(view.party, partyIndex, entry.chrooked_id) });
    setReplacing(false);
  }

  // On a species change (and first open): reset the diff/edit mode and move
  // focus into the dialog. One effect, all "react to the open species".
  useEffect(() => {
    setShowDiff(false);
    setEditing(false);
    setReplacing(false);
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
                    id="ledger-add-to-team"
                    className="ledger__tool"
                    onClick={handleAddToTeam}
                    disabled={addToTeamDisabled}
                    data-on-team={onTeam}
                    aria-pressed={onTeam}
                    title={
                      onTeam
                        ? `${entry.name} is on your team`
                        : teamFull
                          ? `Team is full — swap ${entry.name} in for a member`
                          : `Add ${entry.name} to your team`
                    }
                  >
                    <FontAwesomeIcon
                      icon={onTeam ? faCheck : faPlus}
                      aria-hidden="true"
                    />
                    <span className="ledger__tool-label">
                      {onTeam ? "On the team" : teamFull ? "Swap into team…" : "Add to team"}
                    </span>
                  </button>
                  <button
                    type="button"
                    id="ledger-mirror"
                    className="ledger__tool"
                    onClick={() => handleSuggest([])}
                    title={`Mirror ${entry.name}'s kit across its evolution line`}
                  >
                    <FontAwesomeIcon icon={faClone} aria-hidden="true" />
                    <span className="ledger__tool-label">Mirror</span>
                  </button>
                  <button
                    type="button"
                    id="ledger-makeover"
                    className="ledger__tool ledger__tool--accent"
                    onClick={() =>
                      update({
                        makeover: entry.chrooked_id,
                        makeoverStage: null,
                        makeoverSelect: null,
                      })
                    }
                    title={`Open the makeover workbench for ${entry.name}`}
                  >
                    <FontAwesomeIcon icon={faWandMagicSparkles} aria-hidden="true" />
                    <span className="ledger__tool-label">Makeover</span>
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
      moveMeta={moveMeta}
      onSuggest={handleSuggest}
      backdropTargetId={backdropTargetId}
    />
  );

  // The full-team replace dialog (ac10). Portals to <body>, so it renders the
  // same from either the full-page or side-panel branch and clears this ledger's
  // own overlay when open.
  const replaceDialogEl =
    replacing && partyMembers.length > 0 ? (
      <ReplaceDialog
        incoming={entry}
        members={partyMembers}
        onReplace={handleReplace}
        onClose={() => setReplacing(false)}
        backdropTargetId={backdropTargetId ?? null}
      />
    ) : null;

  // Full page: a pane docked over the dex main area (the rail stays), body laid
  // out in responsive columns. Side panel: the overlay + scrim + narrow aside.
  if (full) {
    return (
      <>
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
        {replaceDialogEl}
      </>
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
        className="ledger"
        id="dex-detail"
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ledger-title"
      >
        {head}
        {body}
      </aside>
      {replaceDialogEl}
    </div>
  );
}

type BodyProps = {
  entry: DexEntry;
  showDiff: boolean;
  /** Read-only-only cross-links out to types / moves / abilities (#28). */
  onNavigate: NavHandler;
  /** Move name (lowercased) → type + category, used to tint/bold/italicize rows. */
  moveMeta: MoveMeta;
  /** Deep-link into the Makeover Workbench seeded to exactly these stages. */
  onSuggest: (stages: readonly DesignStage[]) => void;
  /** Active backdrop target id — the evolution strip's target-sprite fallback. */
  backdropTargetId?: string | null;
  /** Full-page layout: split the sections into two columns instead of stacking. */
  columns: boolean;
};

/** The mon's attacking category: "physical" if Atk beats SpA, "special" if SpA
    beats Atk, null on a tie (no clear attacking side to italicize). */
function attackCategory(stats: Record<string, number>): "physical" | "special" | null {
  if (stats.atk > stats.spa) return "physical";
  if (stats.spa > stats.atk) return "special";
  return null;
}

/** Press `s` on a focused section to fire its `✦ suggest` deep link —
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
  moveMeta,
  onSuggest,
  backdropTargetId,
  columns,
}: BodyProps) {
  // A section heading with the ✦ suggest affordance: click (or `s` on the
  // focused section) deep-links into the workbench seeded to that one stage.
  const suggestHead = (label: string, stage: DesignStage) => (
    <div className="proposal__head">
      <h3 className="ledger__heading">{label}</h3>
      <button
        type="button"
        id={`ledger-suggest-${stage}`}
        className="proposal__suggest"
        onClick={() => onSuggest([stage])}
        aria-label={`Suggest ${label.toLowerCase()} for ${entry.name} in the makeover workbench`}
      >
        <span aria-hidden="true">✦</span> suggest
      </button>
    </div>
  );

  const statsSection = (
    <section
      className="ledger__section"
      aria-label="Base stats"
      tabIndex={0}
      onKeyDown={(e) => handleSectionKey(e, "ledger-suggest-stats")}
    >
      {suggestHead("Base stats", "stats")}
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
      onKeyDown={(e) => handleSectionKey(e, "ledger-suggest-abilities")}
    >
      {suggestHead("Abilities", "abilities")}
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
    </section>
  );

  const learnsetSection = (
    <section
      className="ledger__section"
      aria-label="Learnset"
      tabIndex={0}
      onKeyDown={(e) => handleSectionKey(e, "ledger-suggest-learnset")}
    >
      {suggestHead("Learnset", "learnset")}
      <LearnsetSection
        now={entry.learnset}
        was={entry.base.learnset}
        showDiff={showDiff}
        onNavigate={onNavigate}
        moveMeta={moveMeta}
        speciesTypes={entry.types}
        attackCategory={attackCategory(entry.stats)}
        bare
      />
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
