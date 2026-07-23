/* The ABILITIES design stage. Proposes existing abilities via the existing
   suggest Seam, renders current → proposed per slot, and lets the author swap any
   slot inline (a mono select over the ability pool). LOCK IN writes the anchor's
   abilities through the existing CRUD route. Reuses the pure abilitiesDraft logic
   (merge, edit, alternatives) — the same machinery the ledger's proposer uses. */

import type { AbilityDraft, AbilitySlots, ProposalAlternative } from "../../types";
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
import { useMakeoverStage } from "./useMakeoverStage";
import type { CommonStageProps } from "./stageProps";

const SLOT_LABEL: Record<string, string> = {
  primary: "Primary",
  secondary: "Secondary",
  hidden: "Hidden",
};

interface Props extends CommonStageProps {
  abilityOptions: readonly string[];
}

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
  } = props;

  const hook = useMakeoverStage<AbilityDraft>({
    section: "abilities",
    entry,
    initialDirection,
    propose: async (id, direction) => {
      const result = await api.suggestAbility(id, { direction: direction || undefined });
      return {
        draft: result.draft,
        rationale: result.rationale ?? {},
        alternatives: (result.alternatives ?? []) as ProposalAlternative[],
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

  return (
    <StagePanel
      stageLabel="ABILITIES"
      hook={hook}
      canLock={canLock}
      placeholder="steer the abilities (e.g. lean into the trapper role)…"
      redirectRef={redirectRef}
      registerActions={registerActions}
      applyAlternative={(alt, current) => applyAlternative(current, alt)}
      altLabel={(value) => (typeof value === "string" ? value : String(value))}
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
      </div>
    </StagePanel>
  );
}
