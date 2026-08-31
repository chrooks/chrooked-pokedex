/* The ABILITIES design stage. Two modes (ac8): SWAP an existing ability (via the
   existing suggest Seam, current → proposed per slot, inline select) or CREATE a
   brand-new one (via the existing ability-create Seam — see AbilityCreatePanel).
   LOCK IN writes through the existing CRUD routes. Reuses the pure abilitiesDraft
   logic (merge, edit, alternatives) — the same machinery the ledger uses. */

import { useEffect, useState } from "react";
import type {
  AbilityDraft,
  AbilitySlots,
  DexEntry,
  LoreMode,
  LoreProvenance,
  ProposalAlternative,
} from "../../types";
import { api } from "../../api";
import {
  ABILITY_SLOTS,
  applyAlternative,
  currentSlot,
  editSlot,
  mergeDraft,
  proposedSlot,
  slotChanged,
  type AbilitySlot,
} from "../proposal/abilitiesDraft";
import { StagePanel } from "./StagePanel";
import { LoreControl } from "./LoreControl";
import { LoreProvenanceLine } from "./LoreProvenanceLine";
import { AbilityCreatePanel } from "./AbilityCreatePanel";
import { MoveCreatePanel } from "./MoveCreatePanel";
import { DistributePanel } from "./DistributePanel";
import { useMakeoverStage } from "./useMakeoverStage";
import type { CommonStageProps } from "./stageProps";

const SLOT_LABEL: Record<string, string> = {
  primary: "Primary",
  secondary: "Secondary",
  hidden: "Hidden",
};

interface Props extends CommonStageProps {
  abilityOptions: readonly string[];
  /** The whole dex by chrooked_id, for the create mode's distribution writes. */
  byId: ReadonlyMap<string, DexEntry>;
  /** The session's lore-lookup mode, owned by the workbench (survives stages). */
  loreMode: LoreMode;
  onLoreMode: (mode: LoreMode) => void;
  /** Report the open sub-surface to the overhead rail (ac11): the open panel's
      label ("create new" / "distribute" / "create move"), null on swap/close. */
  onSubSurface?: (label: string | null) => void;
  /** Refresh the dex after a side write (distribute / create move). */
  onSaved: () => void;
  /** Record session-created content so later suggest calls are steered to use it. */
  onCreated: (name: string, kind: "ability" | "move") => void;
}

type AbilityMode = "swap" | "create" | "distribute" | "create-move";

const MODES: { id: AbilityMode; label: string; btnId?: string }[] = [
  { id: "swap", label: "swap existing" },
  { id: "create", label: "create new", btnId: "mk-abilities-create-toggle" },
  { id: "distribute", label: "distribute", btnId: "mk-abilities-distribute-toggle" },
  { id: "create-move", label: "create move", btnId: "mk-abilities-move-toggle" },
];

const SUB_LABEL: Record<AbilityMode, string | null> = {
  swap: null,
  create: "create new",
  distribute: "distribute",
  "create-move": "create move",
};

export function AbilitiesStage(props: Props) {
  const {
    entry,
    initialDirection,
    canLock,
    redirectRef,
    registerActions,
    onLocked,
    onRedirect,
    onPhase,
    abilityOptions,
    byId,
    loreMode,
    onLoreMode,
    onSubSurface,
    onSaved,
    onCreated,
    backdropTargetId,
  } = props;

  const [mode, setMode] = useState<AbilityMode>("swap");
  // What the last proposal was built from — set from every propose response.
  const [lore, setLore] = useState<LoreProvenance | null>(null);
  // Slots the author has locked: PROPOSE leaves them unchanged (sent to the
  // server as a constraint AND stripped from the returned draft client-side).
  const [locked, setLocked] = useState<ReadonlySet<AbilitySlot>>(new Set());

  // Tell the overhead rail which sub-surface is open; reset on unmount so the pill
  // never keeps a stale label after the stage closes (ac11).
  useEffect(() => {
    onSubSurface?.(SUB_LABEL[mode]);
    return () => onSubSurface?.(null);
  }, [mode, onSubSurface]);

  const hook = useMakeoverStage<AbilityDraft>({
    section: "abilities",
    entry,
    initialDirection,
    onPhase,
    propose: async (id, direction) => {
      const result = await api.suggestAbility(id, {
        direction: direction || undefined,
        locked: locked.size > 0 ? [...locked] : undefined,
        lore: loreMode,
        target: backdropTargetId ?? undefined,
      });
      setLore(result.lore ?? null);
      // The server may partially degrade: valid slots in `draft`, per-slot verbatim
      // `warnings` for a name it couldn't resolve (usually a move). Not in the
      // AbilityProposal type — read it off the runtime response.
      const partial = result as typeof result & { warnings?: string[] };
      // The server also strips locked slots; filter again so a locked slot can
      // never show a proposed change even against a stale server.
      const abilities = Object.fromEntries(
        Object.entries(result.draft.abilities).filter(
          ([slot]) => !locked.has(slot as AbilitySlot),
        ),
      );
      return {
        draft: { abilities },
        rationale: result.rationale ?? {},
        alternatives: (result.alternatives ?? []) as ProposalAlternative[],
        warnings: partial.warnings,
      };
    },
    merge: (raw, draft) => mergeDraft(raw, draft, entry),
    onLocked: (draft) => {
      const merged: AbilitySlots = {
        primary: draft.abilities.primary ?? currentSlot(entry, "primary"),
        secondary: draft.abilities.secondary ?? currentSlot(entry, "secondary"),
        hidden: draft.abilities.hidden ?? currentSlot(entry, "hidden"),
      };
      onLocked({ abilities: merged });
    },
    onRedirect,
  });

  const draft = hook.draft;

  const toggleLock = (slot: AbilitySlot) => {
    const nowLocked = !locked.has(slot);
    setLocked((prev) => {
      const next = new Set(prev);
      if (nowLocked) next.add(slot);
      else next.delete(slot);
      return next;
    });
    // Locking a slot with a pending proposed change reverts it to current.
    if (nowLocked && draft) hook.editDraft(editSlot(draft, slot, ""));
  };

  const modeToggle = (
    <div className="mk-mode" role="group" aria-label="Abilities mode" id="mk-abilities-mode">
      {MODES.map((m) => (
        <button
          key={m.id}
          type="button"
          id={m.btnId}
          className="mk-mode__btn mono"
          data-active={mode === m.id}
          aria-pressed={mode === m.id}
          onClick={() => setMode(m.id)}
        >
          {m.label}
        </button>
      ))}
    </div>
  );

  if (mode === "create") {
    return (
      <div className="mk-stage" id="mk-stage-abilities">
        {modeToggle}
        <AbilityCreatePanel
          entry={entry}
          byId={byId}
          redirectRef={redirectRef}
          registerActions={registerActions}
          onLocked={onLocked}
          onCreated={onCreated}
          loreMode={loreMode}
          onLoreMode={onLoreMode}
        />
      </div>
    );
  }

  if (mode === "distribute") {
    return (
      <div className="mk-stage" id="mk-stage-abilities">
        {modeToggle}
        <DistributePanel
          byId={byId}
          abilityOptions={abilityOptions}
          registerActions={registerActions}
          onSaved={onSaved}
          onClose={() => setMode("swap")}
        />
      </div>
    );
  }

  if (mode === "create-move") {
    return (
      <div className="mk-stage" id="mk-stage-abilities">
        {modeToggle}
        <MoveCreatePanel
          redirectRef={redirectRef}
          registerActions={registerActions}
          onCreated={onCreated}
          onClose={() => setMode("swap")}
        />
      </div>
    );
  }

  return (
    <>
      {modeToggle}
      <StagePanel
        stageLabel="ABILITIES"
        hook={hook}
        canLock={canLock}
        placeholder="steer the abilities (e.g. lean into the trapper role)…"
        redirectRef={redirectRef}
        registerActions={registerActions}
        // The stage's own mode buttons live ABOVE the panel (they swap the whole
        // surface); extraControl is free, so the lore switch rides beside PROPOSE
        // — the button whose call it shapes.
        extraControl={
          <LoreControl
            mode={loreMode}
            onChange={onLoreMode}
            disabled={hook.phase === "proposing"}
          />
        }
        applyAlternative={(alt, current) => {
          // An alternative can never land on a locked slot.
          const next = applyAlternative(current, alt);
          return {
            abilities: Object.fromEntries(
              Object.entries(next.abilities).filter(
                ([slot]) => !locked.has(slot as AbilitySlot),
              ),
            ),
          };
        }}
        altLabel={(value) => (typeof value === "string" ? value : String(value))}
        current={
          <div className="mk-abilities">
            {ABILITY_SLOTS.map((slot) => {
              const isLocked = locked.has(slot);
              return (
                <div key={slot} className="mk-ability" data-locked={isLocked || undefined}>
                  <span className="mk-ability__label mono">{SLOT_LABEL[slot]}</span>
                  <span className="mk-ability__now mono">{currentSlot(entry, slot) ?? "—"}</span>
                  <button
                    type="button"
                    id={`mk-ability-lock-${slot}`}
                    className="mk-ability__lock mono"
                    aria-pressed={isLocked}
                    aria-label={`${isLocked ? "Unlock" : "Lock"} ${SLOT_LABEL[slot]} ability`}
                    title={
                      isLocked
                        ? "locked — proposals keep this slot as-is"
                        : "unlocked — proposals may change this slot"
                    }
                    onClick={() => toggleLock(slot)}
                  >
                    {isLocked ? "🔒" : "🔓"}
                  </button>
                </div>
              );
            })}
          </div>
        }
      >
      <>
      <div className="mk-abilities">
        {ABILITY_SLOTS.map((slot) => {
          const value = proposedSlot(draft, slot) ?? currentSlot(entry, slot) ?? "";
          const changed = slotChanged(entry, draft, slot);
          const isLocked = locked.has(slot);
          return (
            <div
              key={slot}
              className="mk-ability"
              data-changed={changed || undefined}
              data-locked={isLocked || undefined}
            >
              <span className="mk-ability__label mono">{SLOT_LABEL[slot]}</span>
              <span className="mk-ability__now mono">{currentSlot(entry, slot) ?? "—"}</span>
              <button
                type="button"
                id={`mk-ability-lock-${slot}`}
                className="mk-ability__lock mono"
                aria-pressed={isLocked}
                aria-label={`${isLocked ? "Unlock" : "Lock"} ${SLOT_LABEL[slot]} ability`}
                title={
                  isLocked
                    ? "locked — proposals keep this slot as-is"
                    : "unlocked — proposals may change this slot"
                }
                onClick={() => toggleLock(slot)}
              >
                {isLocked ? "🔒" : "🔓"}
              </button>
              <select
                className="mk-select mono"
                aria-label={`${SLOT_LABEL[slot]} ability`}
                value={value}
                disabled={isLocked}
                onChange={(event) => hook.editDraft(editSlot(draft, slot, event.target.value))}
              >
                <option value="">—</option>
                {abilityOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
              {changed && <span className="mk-ability__marker mono">→ changed</span>}
            </div>
          );
        })}
        {hook.warnings.length > 0 && (
          <ul className="mk-slot-warnings" id="mk-abilities-warnings">
            {hook.warnings.map((warning, i) => (
              <li key={i} className="mk-stage__error" role="alert">
                <span className="mk-stage__error-tag mono" aria-hidden="true">
                  no fill
                </span>
                {warning}
              </li>
            ))}
          </ul>
        )}
      </div>
      <LoreProvenanceLine id="mk-abilities-lore-prov" lore={lore} />
      </>
      </StagePanel>
    </>
  );
}
