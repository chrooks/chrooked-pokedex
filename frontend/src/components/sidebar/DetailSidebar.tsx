/* Shared read-only detail sidebar shell for Move and Ability entries.
   Mirrors the DetailLedger pattern: a right-docked overlay with a tab strip,
   read-only content by default, and a pencil-edit button that swaps in the
   existing editor in place.

   Tab Seam: the `tabs` prop is a config array so downstream slices (e.g. #4)
   can append additional tabs (reverse lookups) without reworking this shell. */

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faPencil } from "@fortawesome/free-solid-svg-icons";
import "../detail-ledger.css";
import "../editors/editors.css";
import "./detail-sidebar.css";

export type SidebarTab = {
  id: string;
  label: string;
  render: () => ReactNode;
};

type Props = {
  /** Stable unique key for the open entity — drives the reset effect. */
  entityKey: string;
  /** Header title (move/ability name). */
  title: string;
  /** Whether the entity has Ruleset overrides — shows the Edited tag. */
  edited: boolean;
  /** Short label shown left of the title (e.g. "MOVE" / "ABILITY"). */
  kindLabel: string;
  /** Tab config. The first tab is the Detail tab; #4 appends more. */
  tabs: SidebarTab[];
  /** The existing editor rendered when the user clicks the pencil. */
  editView: ReactNode;
  onClose: () => void;
};

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function focusableWithin(root: HTMLElement | null): HTMLElement[] {
  if (root === null) return [];
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => el.offsetParent !== null || el === document.activeElement,
  );
}

export function DetailSidebar({
  entityKey,
  title,
  edited,
  kindLabel,
  tabs,
  editView,
  onClose,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [activeTab, setActiveTab] = useState(tabs[0]?.id ?? "");
  const panelRef = useRef<HTMLElement>(null);

  // Reset editing/tab/scroll when the open entity changes, and move focus into
  // the dialog — mirrors DetailLedger.tsx:41-45.
  useEffect(() => {
    setEditing(false);
    setActiveTab(tabs[0]?.id ?? "");
    if (panelRef.current) {
      panelRef.current.scrollTop = 0;
      panelRef.current.focus();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityKey]);

  // Escape closes; Tab/Shift+Tab cycle within the panel.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const focusables = focusableWithin(panelRef.current);
      if (focusables.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || active === panelRef.current)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const activeTabConfig = tabs.find((t) => t.id === activeTab);

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
        className="ledger detail-sidebar"
        id="detail-sidebar"
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-sidebar-title"
      >
        <header className="ledger__head">
          <div className="ledger__head-row">
            <span className="ledger__dex mono">{kindLabel}</span>
            <div className="ledger__head-actions">
              {edited && (
                <span className="detail-sidebar__edited-tag">Edited</span>
              )}
              {!editing && (
                <button
                  type="button"
                  id="detail-sidebar-edit"
                  className="ledger__edit detail-sidebar__pencil"
                  aria-label={`Edit ${title}`}
                  onClick={() => setEditing(true)}
                >
                  <FontAwesomeIcon icon={faPencil} aria-hidden="true" />
                </button>
              )}
              <button
                type="button"
                id="detail-sidebar-close"
                className="ledger__close"
                onClick={onClose}
              >
                Close <kbd className="mono">Esc</kbd>
              </button>
            </div>
          </div>

          <h2 className="ledger__name" id="detail-sidebar-title">
            {title}
          </h2>

          {!editing && tabs.length > 1 && (
            <div
              id="detail-sidebar-tabs"
              className="detail-sidebar__tablist"
              role="tablist"
              aria-label="Detail sections"
            >
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  id={`detail-sidebar-tab-${tab.id}`}
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  className="detail-sidebar__tab"
                  data-active={activeTab === tab.id}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          )}

          {!editing && tabs.length === 1 && (
            <div
              id="detail-sidebar-tabs"
              className="detail-sidebar__tablist"
              role="tablist"
              aria-label="Detail sections"
            >
              <button
                type="button"
                id={`detail-sidebar-tab-${tabs[0].id}`}
                role="tab"
                aria-selected={true}
                className="detail-sidebar__tab"
                data-active={true}
              >
                {tabs[0].label}
              </button>
            </div>
          )}
        </header>

        {editing ? (
          <div className="detail-sidebar__edit-view">{editView}</div>
        ) : (
          <div
            id={`detail-sidebar-panel-${activeTab}`}
            role="tabpanel"
            aria-labelledby={`detail-sidebar-tab-${activeTab}`}
          >
            {activeTabConfig?.render()}
          </div>
        )}
      </aside>
    </div>
  );
}
