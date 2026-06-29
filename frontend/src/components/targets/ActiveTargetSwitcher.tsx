/* The active-target switcher — the single high-hierarchy control that picks
   which game the app is working against. It lives in the device header because
   the choice drives data across every dex tab (the backdrop: target ⊕ Ruleset).

   Selecting a target sets the backdrop globally; "Canon" clears it. Preview /
   Apply open the PatchDrawer for the active target. Empty registry → a route to
   the Targets tab to add one. Native <select> on purpose: the platform control
   is keyboard-accessible and familiar (no bespoke dropdown). */

import type { RefObject } from "react";
import type { Target } from "../../types";
import "./active-target-switcher.css";

const CANON = "";

type Props = {
  targets: Target[];
  /** The active target id (the backdrop), or null for Canon. */
  activeId: string | null;
  onSetActive: (id: string | null) => void;
  onPreview: () => void;
  onApply: () => void;
  /** Jump to the Targets tab to register a game. */
  onManage: () => void;
  /** Drawer open / a run in flight — disables the action buttons. */
  busy?: boolean;
  selectRef?: RefObject<HTMLSelectElement>;
};

export function ActiveTargetSwitcher({
  targets,
  activeId,
  onSetActive,
  onPreview,
  onApply,
  onManage,
  busy = false,
  selectRef,
}: Props) {
  if (targets.length === 0) {
    return (
      <div className="target-switcher" id="active-target-switcher">
        <button
          type="button"
          id="active-target-add"
          className="target-switcher__empty"
          onClick={onManage}
        >
          + add a target
        </button>
      </div>
    );
  }

  const active = activeId !== null;
  return (
    <div className="target-switcher" id="active-target-switcher">
      <div className="target-switcher__field" data-on={active}>
        <span className="target-switcher__lamp" aria-hidden="true" />
        <span className="target-switcher__caption mono">TARGET</span>
        <select
          id="active-target-select"
          ref={selectRef}
          className="target-switcher__select"
          value={activeId ?? CANON}
          onChange={(event) => onSetActive(event.target.value || null)}
          aria-label="Active patch target — drives the dex backdrop across every tab"
        >
          <option value={CANON}>Canon · base ⊕ Ruleset</option>
          {targets.map((target) => (
            <option key={target.id} value={target.id}>
              {target.label}
            </option>
          ))}
        </select>
      </div>

      {active && (
        <div className="target-switcher__actions" role="group" aria-label="Patch actions">
          <button
            type="button"
            id="header-preview-button"
            className="target-switcher__btn"
            disabled={busy}
            onClick={onPreview}
          >
            Preview
          </button>
          <button
            type="button"
            id="header-apply-button"
            className="target-switcher__btn target-switcher__btn--danger"
            disabled={busy}
            onClick={onApply}
          >
            Apply…
          </button>
        </div>
      )}
    </div>
  );
}
