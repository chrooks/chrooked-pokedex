/* A tab panel listing the species that reference a given move or ability, with
   sprite thumbnails, click-to-navigate, and (issue #30) INLINE distribution
   editing: stage level / slot / add / remove changes, then Save writes each
   touched species once via putSpecies over the merged learnset / abilities (D6).

   Editing is disabled in backdrop / read-only mode (D5) — the tab falls back to
   the original navigate-only list. The pure override-building and merge logic
   lives in lib/distributionEdits.ts (unit-tested); this file owns the staged
   state, the controls, and the Save orchestration. */

import { useMemo, useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faFilter } from "@fortawesome/free-solid-svg-icons";
import { api } from "../../api";
import { useUrlState } from "../../hooks/useUrlState";
import { DexSprite } from "../DexSprite";
import {
  ABILITY_SLOTS,
  abilityOverridePayload,
  buildAbilitiesOverride,
  buildLearnsetOverride,
  currentLevel,
  currentSlot,
  moveOverridePayload,
  replacementInSlot,
  type AbilityPending,
  type AbilitySlot,
  type MovePending,
} from "../../lib/distributionEdits";
import type { DexEntry } from "../../types";
import { FormError } from "../editors/FormFeedback";
import "../editors/editors.css";

type Props = {
  /** Species currently in the distribution — from the caller's reverse index. */
  species: DexEntry[];
  /** The FULL merged dex, for the add-a-species typeahead + per-species merge. */
  dexData: DexEntry[];
  /** Button id prefix, e.g. "move-learner" → id="move-learner-bulbasaur". */
  rowIdPrefix: string;
  /** "moves" (level edits) or "abilities" (slot edits). */
  entityKind: "move" | "ability";
  /** The filter field for the "Filter in dex" cross-link. */
  filterField: "moves" | "abilities";
  /** The DISPLAY name of the move / ability being viewed. */
  entityName: string;
  /** Backdrop / read-only mode disables every edit affordance (D5). */
  readOnly: boolean;
  /** When a backdrop target is active, DexSprite uses the target's own art. */
  backdropTargetId?: string | null;
  /** Called after a successful Save so the parent reloads + rebuilds the index. */
  onSaved: () => void;
  /** Called after navigating to a species so the sidebar can close. */
  onClose: () => void;
};

/** One staged change keyed by chrooked_id. `isNew` flags an added species (not
    currently in the distribution) so the UI can mark it and offer Discard-as-
    drop instead of revert-to-present. */
type Pending =
  | { isNew: boolean; move: MovePending }
  | { isNew: boolean; ability: AbilityPending };

const DEFAULT_LEVEL = 1;

export function ReverseLookupTab({
  species,
  dexData,
  rowIdPrefix,
  entityKind,
  filterField,
  entityName,
  readOnly,
  backdropTargetId,
  onSaved,
  onClose,
}: Props) {
  const [, updateView] = useUrlState();
  const [pending, setPending] = useState<Map<string, Pending>>(new Map());
  const [addQuery, setAddQuery] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [failures, setFailures] = useState<string[]>([]);

  // chrooked_id → DexEntry over the whole dex, so an added species resolves to
  // its merged values for the override build, and rows can render sprites.
  const byId = useMemo(() => {
    const map = new Map<string, DexEntry>();
    for (const entry of dexData) map.set(entry.chrooked_id, entry);
    return map;
  }, [dexData]);

  // Species ids already in the distribution (so the typeahead can exclude them).
  const presentIds = useMemo(
    () => new Set(species.map((s) => s.chrooked_id)),
    [species],
  );

  // The rendered rows = current distribution ⊕ pending adds. A pending removal of
  // a present species keeps the row (shown struck-through) so the change is
  // visible and reversible before Save.
  const rows = useMemo(() => {
    const added: DexEntry[] = [];
    for (const [id, change] of pending) {
      if (change.isNew && !presentIds.has(id)) {
        const entry = byId.get(id);
        if (entry) added.push(entry);
      }
    }
    return [...species, ...added];
  }, [species, pending, presentIds, byId]);

  const dirtyCount = pending.size;

  function setPendingFor(id: string, change: Pending | null) {
    setPending((prev) => {
      const next = new Map(prev);
      if (change === null) next.delete(id);
      else next.set(id, change);
      return next;
    });
  }

  function handleClick(entry: DexEntry) {
    // Navigate to the species' dex profile in ONE atomic update. Do NOT also call
    // onClose() here: onClose maps to the parent's `update({ selected: null })`,
    // a second URL write that would immediately wipe the `id=` we just set (both
    // the move/ability sidebar and the dex profile share the `selected`/`id=`
    // param). Switching to kind=dex unmounts the move/ability tab + its sidebar,
    // so the close is implicit. (handleFilterInDex already expresses selected:null
    // in its single update, so it keeps its onClose for symmetry.)
    updateView({ kind: "dex", selected: entry.chrooked_id });
  }

  function handleFilterInDex() {
    const entry = {
      kind: "filter" as const,
      id: crypto.randomUUID(),
      field: filterField,
      value: entityName,
      connector: "AND" as const,
      negated: false,
    };
    updateView({ kind: "dex", filter: [entry], selected: null, query: "" });
    onClose();
  }

  function handleDiscard() {
    setPending(new Map());
    setFailures([]);
  }

  // Save: for each touched species, fetch its raw Override (to keep aka +
  // passthrough fields, D6), build the new override from merged values + the
  // staged change, and PUT once. Failures are collected per species and surfaced;
  // they keep their pending entry so the user can retry (ac6).
  async function handleSave() {
    setIsSaving(true);
    setFailures([]);
    const stillPending = new Map<string, Pending>();
    const errors: string[] = [];

    for (const [id, change] of pending) {
      const entry = byId.get(id);
      if (!entry) {
        errors.push(`${id}: species not found in dex`);
        stillPending.set(id, change);
        continue;
      }
      try {
        const raw = await api
          .speciesOverride(entry.chrooked_id)
          .catch(() => null);
        if ("move" in change) {
          const learnset = buildLearnsetOverride(entry, entityName, change.move);
          await api.putSpecies(
            entry.chrooked_id,
            moveOverridePayload(entry, raw, learnset),
          );
        } else {
          const abilities = buildAbilitiesOverride(
            entry,
            entityName,
            change.ability,
          );
          await api.putSpecies(
            entry.chrooked_id,
            abilityOverridePayload(entry, raw, abilities),
          );
        }
      } catch (caught: unknown) {
        const message =
          caught instanceof Error ? caught.message : "Unexpected error";
        errors.push(`${entry.name}: ${message}`);
        stillPending.set(id, change);
      }
    }

    setPending(stillPending);
    setFailures(errors);
    setIsSaving(false);
    if (errors.length === 0) onSaved();
  }

  // --- Add-a-species typeahead candidates (exclude those already present /
  //     already pending-added), matched by name substring (ac3). ---
  const query = addQuery.trim().toLowerCase();
  const candidates = useMemo(() => {
    if (query === "") return [];
    return dexData
      .filter(
        (entry) =>
          !presentIds.has(entry.chrooked_id) &&
          !(pending.get(entry.chrooked_id)?.isNew ?? false) &&
          entry.name.toLowerCase().includes(query),
      )
      .slice(0, 8);
  }, [dexData, query, presentIds, pending]);

  function handleAdd(entry: DexEntry) {
    const change: Pending =
      entityKind === "move"
        ? { isNew: true, move: { type: "level", level: DEFAULT_LEVEL } }
        : { isNew: true, ability: { type: "slot", slot: "primary" } };
    setPendingFor(entry.chrooked_id, change);
    setAddQuery("");
  }

  return (
    <div
      id="reverse-lookup-tab"
      className="editor-section"
      style={{ border: "none" }}
    >
      <div className="reverse-lookup__header">
        <span className="reverse-lookup__count">({rows.length} species)</span>
        {rows.length > 0 && (
          <button
            type="button"
            id="reverse-filter-in-dex"
            className="reverse-lookup__filter-btn"
            onClick={handleFilterInDex}
            title={`Filter dex by ${entityName}`}
          >
            <FontAwesomeIcon icon={faFilter} aria-hidden="true" />
            {" Filter in dex"}
          </button>
        )}
      </div>

      {!readOnly && (
        <div className="dist-add" id="dist-add">
          <label className="sr-only" htmlFor="dist-add-input">
            Add a species
          </label>
          <input
            id="dist-add-input"
            className="field__input"
            type="text"
            value={addQuery}
            placeholder={`Add a species that ${
              entityKind === "move"
                ? "doesn't learn this move"
                : "lacks this ability"
            }…`}
            autoComplete="off"
            onChange={(e) => setAddQuery(e.target.value)}
          />
          {candidates.length > 0 && (
            <ul className="dist-add__list" id="dist-add-list">
              {candidates.map((entry) => (
                <li key={entry.chrooked_id}>
                  <button
                    type="button"
                    id={`dist-add-${entry.chrooked_id}`}
                    className="dist-add__option"
                    onClick={() => handleAdd(entry)}
                  >
                    {entry.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {rows.length === 0 ? (
        <p className="reverse-lookup__empty">No species found.</p>
      ) : readOnly ? (
        <ReadOnlyList
          species={rows}
          rowIdPrefix={rowIdPrefix}
          backdropTargetId={backdropTargetId}
          onPick={handleClick}
        />
      ) : (
        <ul
          id="reverse-lookup-list"
          className="dist-list"
          style={{ maxHeight: "none" }}
        >
          {rows.map((entry) => (
            <EditableRow
              key={entry.chrooked_id}
              entry={entry}
              entityKind={entityKind}
              entityName={entityName}
              rowIdPrefix={rowIdPrefix}
              pending={pending.get(entry.chrooked_id) ?? null}
              isAdded={!presentIds.has(entry.chrooked_id)}
              backdropTargetId={backdropTargetId}
              onNavigate={() => handleClick(entry)}
              onChange={(change) => setPendingFor(entry.chrooked_id, change)}
            />
          ))}
        </ul>
      )}

      {failures.length > 0 && (
        <FormError
          key={failures.join("|")}
          message={`Some species could not be saved — ${failures.join("; ")}`}
          citing={null}
        />
      )}

      {!readOnly && dirtyCount > 0 && (
        <div className="dist-actions" id="dist-actions">
          <span className="dist-actions__dirty" id="dist-dirty" aria-live="polite">
            {dirtyCount} pending {dirtyCount === 1 ? "change" : "changes"}
          </span>
          <span className="editor-actions__spacer" />
          <button
            type="button"
            id="dist-discard"
            className="btn"
            disabled={isSaving}
            onClick={handleDiscard}
          >
            Discard
          </button>
          <button
            type="button"
            id="dist-save"
            className="btn btn--primary"
            disabled={isSaving}
            onClick={() => void handleSave()}
          >
            {isSaving ? "Saving…" : "Save"}
          </button>
        </div>
      )}
    </div>
  );
}

// --- The read-only (backdrop) list: the original navigate-only chips. --------- #

type ReadOnlyListProps = {
  species: DexEntry[];
  rowIdPrefix: string;
  backdropTargetId?: string | null;
  onPick: (entry: DexEntry) => void;
};

function ReadOnlyList({ species, rowIdPrefix, backdropTargetId, onPick }: ReadOnlyListProps) {
  return (
    <ul
      id="reverse-lookup-list"
      className="reverse-lookup__list"
      style={{ maxHeight: "none" }}
    >
      {species.map((entry) => (
        <li key={entry.chrooked_id}>
          <button
            type="button"
            id={`${rowIdPrefix}-${entry.chrooked_id}`}
            className="reverse-lookup__species-btn"
            onClick={() => onPick(entry)}
          >
            <DexSprite
              chrookedId={entry.chrooked_id}
              dex={entry.dex}
              name={entry.name}
              backdropTargetId={backdropTargetId}
              size={32}
            />
            {entry.name}
          </button>
        </li>
      ))}
    </ul>
  );
}

// --- One editable distribution row (level input or slot picker + remove). ----- #

type EditableRowProps = {
  entry: DexEntry;
  entityKind: "move" | "ability";
  entityName: string;
  rowIdPrefix: string;
  pending: Pending | null;
  isAdded: boolean;
  backdropTargetId?: string | null;
  onNavigate: () => void;
  onChange: (change: Pending | null) => void;
};

function EditableRow({
  entry,
  entityKind,
  entityName,
  rowIdPrefix,
  pending,
  isAdded,
  backdropTargetId,
  onNavigate,
  onChange,
}: EditableRowProps) {
  const isRemoved =
    pending !== null &&
    (("move" in pending && pending.move.type === "remove") ||
      ("ability" in pending && pending.ability.type === "remove"));
  const isDirty = pending !== null;

  return (
    <li
      id={`dist-row-${entry.chrooked_id}`}
      className="dist-row"
      data-dirty={isDirty ? "true" : undefined}
      data-removed={isRemoved ? "true" : undefined}
    >
      <button
        type="button"
        id={`${rowIdPrefix}-${entry.chrooked_id}`}
        className="dist-row__name"
        onClick={onNavigate}
        title={`Open ${entry.name}`}
      >
        <DexSprite
          chrookedId={entry.chrooked_id}
          dex={entry.dex}
          name={entry.name}
          backdropTargetId={backdropTargetId}
          size={28}
        />
        <span className="dist-row__name-text">{entry.name}</span>
        {isAdded && <span className="dist-row__badge">new</span>}
      </button>

      {entityKind === "move" ? (
        <MoveControls
          entry={entry}
          entityName={entityName}
          pending={pending}
          onChange={onChange}
        />
      ) : (
        <AbilityControls
          entry={entry}
          entityName={entityName}
          pending={pending}
          onChange={onChange}
        />
      )}
    </li>
  );
}

// --- Move row controls: a level number input + a remove toggle. --------------- #

type MoveControlsProps = {
  entry: DexEntry;
  entityName: string;
  pending: Pending | null;
  onChange: (change: Pending | null) => void;
};

function MoveControls({
  entry,
  entityName,
  pending,
  onChange,
}: MoveControlsProps) {
  const baseLevel = currentLevel(entry, entityName);
  const movePending = pending !== null && "move" in pending ? pending.move : null;
  const isRemoved = movePending?.type === "remove";
  const isNew = pending?.isNew ?? false;

  // The level shown: a staged level wins; otherwise the species' current level;
  // otherwise the default for a brand-new add.
  const shownLevel =
    movePending?.type === "level"
      ? movePending.level
      : (baseLevel ?? DEFAULT_LEVEL);

  function setLevel(value: number | "") {
    if (value === "") return;
    const level = Number(value);
    // Editing back to the species' current level on an existing row clears the
    // pending change (no-op); on a new add the staged level always stands.
    if (!isNew && baseLevel !== null && level === baseLevel) {
      onChange(null);
      return;
    }
    onChange({ isNew, move: { type: "level", level } });
  }

  return (
    <div className="dist-row__controls">
      <label className="sr-only" htmlFor={`dist-level-${entry.chrooked_id}`}>
        Learn level for {entry.name}
      </label>
      <span className="dist-row__lv-label" aria-hidden="true">
        Lv
      </span>
      <input
        id={`dist-level-${entry.chrooked_id}`}
        className="field__input mono dist-row__lv"
        type="number"
        inputMode="numeric"
        min={0}
        max={100}
        disabled={isRemoved}
        value={isRemoved ? "" : shownLevel}
        onChange={(e) => setLevel(e.target.value === "" ? "" : Number(e.target.value))}
      />
      <RemoveToggle
        id={`dist-remove-${entry.chrooked_id}`}
        name={entry.name}
        isRemoved={isRemoved}
        isNew={isNew}
        onRemove={() => onChange({ isNew, move: { type: "remove" } })}
        onUndo={() => onChange(null)}
      />
    </div>
  );
}

// --- Ability row controls: a slot picker (+ replacement note) + remove. ------- #

type AbilityControlsProps = {
  entry: DexEntry;
  entityName: string;
  pending: Pending | null;
  onChange: (change: Pending | null) => void;
};

function AbilityControls({
  entry,
  entityName,
  pending,
  onChange,
}: AbilityControlsProps) {
  const baseSlot = currentSlot(entry, entityName);
  const abilityPending =
    pending !== null && "ability" in pending ? pending.ability : null;
  const isRemoved = abilityPending?.type === "remove";
  const isNew = pending?.isNew ?? false;

  const shownSlot: AbilitySlot =
    abilityPending?.type === "slot"
      ? abilityPending.slot
      : (baseSlot ?? "primary");

  const replacement = replacementInSlot(entry, entityName, shownSlot);

  function setSlot(slot: AbilitySlot) {
    if (!isNew && baseSlot !== null && slot === baseSlot) {
      onChange(null);
      return;
    }
    onChange({ isNew, ability: { type: "slot", slot } });
  }

  // The slot picker + remove sit on the row's first line; the "replaces X" note
  // is a sibling so it wraps to its own full-width line (see .dist-row grid) and
  // never crushes the name or the controls.
  return (
    <>
      <div className="dist-row__controls">
        <label className="sr-only" htmlFor={`dist-slot-${entry.chrooked_id}`}>
          Ability slot for {entry.name}
        </label>
        <select
          id={`dist-slot-${entry.chrooked_id}`}
          className="field__select dist-row__slot"
          disabled={isRemoved}
          value={isRemoved ? "" : shownSlot}
          onChange={(e) => setSlot(e.target.value as AbilitySlot)}
        >
          {ABILITY_SLOTS.map((slot) => (
            <option key={slot} value={slot}>
              {slot}
            </option>
          ))}
        </select>
        <RemoveToggle
          id={`dist-remove-${entry.chrooked_id}`}
          name={entry.name}
          isRemoved={isRemoved}
          isNew={isNew}
          onRemove={() => onChange({ isNew, ability: { type: "remove" } })}
          onUndo={() => onChange(null)}
        />
      </div>
      {!isRemoved && replacement !== null && (
        <span
          className="dist-row__replace"
          id={`dist-replace-${entry.chrooked_id}`}
          title={`Replaces ${replacement} in the ${shownSlot} slot`}
        >
          replaces {replacement}
        </span>
      )}
    </>
  );
}

// --- Shared remove / undo toggle. --------------------------------------------- #

type RemoveToggleProps = {
  id: string;
  name: string;
  isRemoved: boolean;
  isNew: boolean;
  onRemove: () => void;
  onUndo: () => void;
};

function RemoveToggle({
  id,
  name,
  isRemoved,
  isNew,
  onRemove,
  onUndo,
}: RemoveToggleProps) {
  if (isRemoved) {
    return (
      <button
        type="button"
        id={`${id}-undo`}
        className="dist-row__undo"
        aria-label={`Keep ${name}`}
        onClick={onUndo}
      >
        undo
      </button>
    );
  }
  // A brand-new add's "remove" just drops the staged add entirely.
  return (
    <button
      type="button"
      id={id}
      className="dist-row__remove"
      aria-label={`Remove ${name}`}
      onClick={isNew ? onUndo : onRemove}
    >
      ×
    </button>
  );
}
