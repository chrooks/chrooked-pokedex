/* A standing, calm note that species/moves/abilities are machine-owned: a
   re-seed regenerates them and overwrites edits. This is honest, Transparent
   Friction — it tells Chris the consequence without blocking him, and it sits
   in the rail's periphery rather than interrupting the work. Hidden on the
   Behaviors tab, which is the human-owned kind a re-seed never touches. */

import "./reseed-note.css";

export function ReseedNote() {
  return (
    <p className="reseed-note" id="reseed-note">
      <span className="reseed-note__mark" aria-hidden="true" />
      <span>
        <strong>Machine-owned.</strong> A re-seed overwrites species, move &amp;
        ability edits — commit what you want to keep.
      </span>
    </p>
  );
}
