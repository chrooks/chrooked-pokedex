import { useEffect, useRef, useState } from "react";
import { SavedTeams } from "./SavedTeams";

type Props = {
  encodedParty: string;
  canSave: boolean;
  onLoad: (encoded: string) => void;
};

/**
 * Saved teams behind one toolbar button: save/load/delete is a rare action, so
 * it leaves the page flow and opens as a popover. Escape or a click outside
 * closes it; the SavedTeams strip inside is unchanged. Loading a team closes
 * the popover so the result is visible straight away.
 */
export function SavedTeamsMenu({ encodedParty, canSave, onLoad }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setIsOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setIsOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isOpen]);

  return (
    <div className="saved-menu" ref={rootRef}>
      <button
        type="button"
        id="team-saved-toggle"
        className="team__new-types"
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        aria-controls="team-saved"
        onClick={() => setIsOpen((open) => !open)}
      >
        Saved teams ▾
      </button>
      {isOpen && (
        <div className="saved-menu__popover" id="team-saved" role="dialog" aria-label="Saved teams">
          <SavedTeams
            encodedParty={encodedParty}
            canSave={canSave}
            onLoad={(encoded) => {
              onLoad(encoded);
              setIsOpen(false);
            }}
          />
        </div>
      )}
    </div>
  );
}
