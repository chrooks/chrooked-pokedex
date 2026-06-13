/* The overlay shell for the move / ability editors. Mirrors the detail
   ledger's right-docked dialog: scrim (click to dismiss), Escape to close, and
   a self-contained focus trap — focus moves into the panel on open, Tab/Shift+Tab
   cycle within it, and focus returns to the trigger on close. (The M1 detail
   ledger gets its trap from an `inert` background in App; these dialogs render
   inside a tab, so they trap their own focus.) Presentational otherwise — the
   form lives in `children`. */

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import "../detail-ledger.css";
import "./editors.css";

type Props = {
  id: string;
  titleId: string;
  onClose: () => void;
  children: ReactNode;
};

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function focusablewithin(root: HTMLElement | null): HTMLElement[] {
  if (root === null) return [];
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => el.offsetParent !== null || el === document.activeElement,
  );
}

export function EditorDialog({ id, titleId, onClose, children }: Props) {
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  // Move focus into the panel on open; return it to the opener on close.
  useEffect(() => {
    triggerRef.current = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    return () => triggerRef.current?.focus?.();
  }, []);

  // Escape closes; Tab/Shift+Tab cycle within the panel (the trap).
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusables = focusablewithin(panelRef.current);
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
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="ledger-overlay">
      <button
        type="button"
        className="ledger-overlay__scrim"
        aria-label="Close editor"
        tabIndex={-1}
        onClick={onClose}
      />
      <div
        className="editor-dialog__panel"
        id={id}
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        {children}
      </div>
    </div>
  );
}
