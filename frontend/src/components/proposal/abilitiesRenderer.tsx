/* The abilities section renderer (#6). Three fixed slots (primary / secondary /
   hidden), current │ proposed. A proposed slot is a SELECT from the existing
   ability pool — existing-only; new abilities are #8's separate flow. A changed
   slot reads in provisional amber with a `→ changed` marker (never color-alone).

   This file is a thin React shell over the pure logic in abilitiesDraft.ts —
   the shell stays section-agnostic; all the abilities knowledge lives here. */

import { useState } from "react";
import type { AbilityDraft, DexEntry } from "../../types";
import type { CellRenderArgs, SectionRenderer } from "./renderer";
import {
  ABILITY_SLOTS,
  type AbilitySlot,
  applyAlternative,
  currentSlot,
  editSlot,
  mergeDraft,
  proposedSlot,
  slotChanged,
} from "./abilitiesDraft";

const SLOT_LABEL: Record<AbilitySlot, string> = {
  primary: "Primary",
  secondary: "Secondary",
  hidden: "Hidden",
};

/** Build the abilities renderer. Bound to the known ability pool (the select
    options = merged base + Ruleset-owned names) and the entry (the merge fills
    untouched slots from the current values). This is what DetailLedger mounts. */
export function abilitiesRenderer(
  abilityOptions: readonly string[],
  entry: DexEntry,
): SectionRenderer<AbilityDraft> {
  return {
    id: "abilities",
    title: "Abilities",
    suggestLabel: "Suggest abilities with the LLM",
    placeholder: "how would you like to change the abilities?",
    renderCells: (args) => (
      <AbilitiesCells {...args} abilityOptions={abilityOptions} />
    ),
    applyAlternative,
    mergeDraft: (raw, draft) => mergeDraft(raw, draft, entry),
  };
}

interface CellsProps extends CellRenderArgs<AbilityDraft> {
  abilityOptions: readonly string[];
}

function AbilitiesCells({
  entry,
  draft,
  rationale,
  onEdit,
  abilityOptions,
}: CellsProps) {
  // Reasoning is Progressive Disclosure — slots stay one line so the diff is
  // scannable; the "why" reveals on demand (keyboard-reachable + hover via CSS).
  const [openReason, setOpenReason] = useState<AbilitySlot | null>(null);
  return (
    <>
      <div className="proposal__col">
        <p className="proposal__col-head">Current</p>
        <div className="ledger__abilities">
          {ABILITY_SLOTS.map((slot) => (
            <div key={slot} className="lrow lrow--ability">
              <span className="lrow__label">{SLOT_LABEL[slot]}</span>
              <span className="lrow__value">
                {currentSlot(entry, slot) ?? "—"}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="proposal__col">
        <p className="proposal__col-head">Proposed</p>
        <div className="ledger__abilities">
          {ABILITY_SLOTS.map((slot) => {
            const value =
              proposedSlot(draft, slot) ?? currentSlot(entry, slot) ?? "";
            const changed = slotChanged(entry, draft, slot);
            const reason = rationale[slot];
            const reasonOpen = openReason === slot;
            const reasonId = `proposal-abilities-why-${slot}`;
            return (
              <div
                key={slot}
                className={`lrow lrow--ability${changed ? " proposal-cell--changed" : ""}`}
              >
                <span className="lrow__label">
                  <label htmlFor={`proposal-abilities-${slot}`}>
                    {SLOT_LABEL[slot]}
                  </label>
                </span>
                <span className="lrow__value">
                  <select
                    id={`proposal-abilities-${slot}`}
                    className="proposal__slot-select mono"
                    value={value}
                    onChange={(e) => onEdit(editSlot(draft, slot, e.target.value))}
                  >
                    <option value="">—</option>
                    {abilityOptions.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                  {changed && (
                    <span className="proposal-cell__marker mono">
                      → changed
                    </span>
                  )}
                  {reason && (
                    <button
                      type="button"
                      className="proposal__why"
                      aria-expanded={reasonOpen}
                      aria-controls={reasonId}
                      title={`Why this ${SLOT_LABEL[slot].toLowerCase()} ability?`}
                      onClick={() => setOpenReason(reasonOpen ? null : slot)}
                    >
                      why
                    </button>
                  )}
                </span>
                {reason && (
                  <p
                    id={reasonId}
                    className="proposal-cell__rationale proposal__prow-why"
                    hidden={!reasonOpen}
                  >
                    {reason}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
