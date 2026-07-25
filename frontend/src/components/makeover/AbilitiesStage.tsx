/* The ABILITIES design stage. Two modes (ac8): SWAP an existing ability (via the
   existing suggest Seam, current → proposed per slot, inline select) or CREATE a
   brand-new one (via the existing ability-create Seam — see AbilityCreatePanel).
   LOCK IN writes through the existing CRUD routes. Reuses the pure abilitiesDraft
   logic (merge, edit, alternatives) — the same machinery the ledger uses. */

import { useEffect, useState } from "react";
import type { AbilityDraft, AbilitySlots, DexEntry, ProposalAlternative } from "../../types";
import { api } from "../../api";
import {
  ABILITY_SLOTS,
  applyAlternative,
  currentSlot,
  editSlot,
  mergeDraft,
  proposedSlot,
  slotChanged,
} from "../proposal/abilitiesDraft";
import { StagePanel } from "./StagePanel";
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
    abilityOptions,
    byId,
    onSubSurface,
    onSaved,
    onCreated,
  } = props;

  const [mode, setMode] = useState<AbilityMode>("swap");

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
    propose: async (id, direction) => {
      const result = await api.suggestAbility(id, { direction: direction || undefined });
      // The server may partially degrade: valid slots in `draft`, per-slot verbatim
      // `warnings` for a name it couldn't resolve (usually a move). Not in the
      // AbilityProposal type — read it off the runtime response.
      const partial = result as typeof result & { warnings?: string[] };
      return {
        draft: result.draft,
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
        applyAlternative={(alt, current) => applyAlternative(current, alt)}
        altLabel={(value) => (typeof value === "string" ? value : String(value))}
        current={
          <div className="mk-abilities">
            {ABILITY_SLOTS.map((slot) => (
              <div key={slot} className="mk-ability">
                <span className="mk-ability__label mono">{SLOT_LABEL[slot]}</span>
                <span className="mk-ability__now mono">{currentSlot(entry, slot) ?? "—"}</span>
              </div>
            ))}
          </div>
        }
      >
      <div className="mk-abilities">
        {ABILITY_SLOTS.map((slot) => {
          const value = proposedSlot(draft, slot) ?? currentSlot(entry, slot) ?? "";
          const changed = slotChanged(entry, draft, slot);
          return (
            <div key={slot} className="mk-ability" data-changed={changed || undefined}>
              <span className="mk-ability__label mono">{SLOT_LABEL[slot]}</span>
              <span className="mk-ability__now mono">{currentSlot(entry, slot) ?? "—"}</span>
              <select
                className="mk-select mono"
                aria-label={`${SLOT_LABEL[slot]} ability`}
                value={value}
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
      </StagePanel>
    </>
  );
}
