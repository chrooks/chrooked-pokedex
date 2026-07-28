/* Full-team replace flow (ac10). When the party is at 6/6 and a FRESH species is
   chosen — from the Team picker or the species detail's add button — the add
   surface no longer dead-ends. This dialog takes over: it names the incoming mon
   and lays out all six current members as sprite buttons, and picking one swaps
   it out at its party slot (incoming ability = null; the swap is done by the host
   via replacePartyMember). Duplicates never reach here — both surfaces keep them
   hard-disabled.

   A centered modal, portaled to <body> so it clears the detail ledger's own
   overlay when opened from there. Escape, the backdrop, and Cancel all close
   without touching the party; focus moves in on open, is trapped while open, and
   returns to the invoker on close — same idiom as EditorDialog/DetailLedger. */

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import type { DexEntry } from "../../types";
import { DexSprite } from "../DexSprite";
import { TypeChip } from "../TypeChip";
import "./team-tab.css";

/** One replaceable slot: the resolved party entry plus its true party index, so
    the swap targets the right slot even if an unresolved id sits earlier. */
export type ReplaceMember = { partyIndex: number; entry: DexEntry };

type Props = {
  /** The species being swapped in — named in the title so the trade is explicit. */
  incoming: DexEntry;
  /** The six current members, resolved to dex entries, in slot order. */
  members: readonly ReplaceMember[];
  /** Swap the incoming species in at this party slot index. */
  onReplace: (partyIndex: number) => void;
  /** Dismiss without changing the party (Escape / backdrop / Cancel). */
  onClose: () => void;
  backdropTargetId: string | null;
};

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function focusableWithin(root: HTMLElement | null): HTMLElement[] {
  if (root === null) return [];
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => el.offsetParent !== null || el === document.activeElement,
  );
}

export function ReplaceDialog({
  incoming,
  members,
  onReplace,
  onClose,
  backdropTargetId,
}: Props) {
  const panelRef = useRef<HTMLDivElement>(null);
  const firstMemberRef = useRef<HTMLButtonElement>(null);

  // Move focus onto the first swap target on open; return it to the opener (the
  // picker option or the detail add button) on close.
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    firstMemberRef.current?.focus();
    return () => opener?.focus?.();
  }, []);

  // Escape closes; Tab / Shift+Tab cycle within the panel (the trap).
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusables = focusableWithin(panelRef.current);
      if (focusables.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === panelRef.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [onClose]);

  return createPortal(
    <div className="replace-overlay" id="replace-dialog-overlay">
      <button
        type="button"
        className="replace-overlay__scrim"
        aria-label="Cancel swap"
        tabIndex={-1}
        onClick={onClose}
      />
      <div
        className="replace-dialog"
        id="replace-dialog"
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="replace-dialog-title"
        aria-describedby="replace-dialog-subtitle"
      >
        <header className="replace-dialog__head">
          <h2 className="replace-dialog__title" id="replace-dialog-title">
            Team is full — choose who to swap out
          </h2>
          <p className="replace-dialog__subtitle" id="replace-dialog-subtitle">
            <span className="replace-dialog__incoming">
              <DexSprite
                chrookedId={incoming.chrooked_id}
                dex={incoming.dex}
                name={incoming.name}
                backdropTargetId={backdropTargetId}
                size={28}
              />
              Swap in <strong>{incoming.name}</strong> for…
            </span>
          </p>
        </header>

        <ul className="replace-dialog__members" id="replace-dialog-members">
          {members.map((member, order) => (
            <li key={member.partyIndex} className="replace-dialog__member-item">
              <button
                type="button"
                ref={order === 0 ? firstMemberRef : undefined}
                id={`replace-member-${member.partyIndex}`}
                className="replace-dialog__member"
                onClick={() => onReplace(member.partyIndex)}
                title={`Swap out ${member.entry.name} for ${incoming.name}`}
                aria-label={`Swap out ${member.entry.name} for ${incoming.name}`}
              >
                <DexSprite
                  chrookedId={member.entry.chrooked_id}
                  dex={member.entry.dex}
                  name={member.entry.name}
                  backdropTargetId={backdropTargetId}
                  size={56}
                />
                <span className="replace-dialog__member-name">{member.entry.name}</span>
                <span className="replace-dialog__member-types">
                  {member.entry.types.map((type) => (
                    <TypeChip key={type} type={type} variant="code" />
                  ))}
                </span>
              </button>
            </li>
          ))}
        </ul>

        <footer className="replace-dialog__foot">
          <button
            type="button"
            id="replace-dialog-cancel"
            className="replace-dialog__cancel"
            onClick={onClose}
          >
            Cancel
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
