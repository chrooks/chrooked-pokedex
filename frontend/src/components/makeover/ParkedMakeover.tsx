/* The parked-makeover pill: shown over the dex when a makeover was dismissed
   with "← dex"/Esc rather than finished. The workbench is still mounted behind
   the dex, so RESUME returns to the exact stage with any unlocked draft intact.
   Discard (✕) is the only path that throws the draft away. */

import "./makeover.css";

type Props = {
  name: string;
  onResume: () => void;
  onDiscard: () => void;
};

export function ParkedMakeover({ name, onResume, onDiscard }: Props) {
  return (
    <div className="mk-parked" id="parked-makeover">
      <button
        type="button"
        id="parked-makeover-resume"
        className="mk-parked__resume mono"
        onClick={onResume}
      >
        resume makeover · <strong>{name}</strong>
      </button>
      <button
        type="button"
        id="parked-makeover-discard"
        className="mk-parked__discard"
        onClick={onDiscard}
        title={`Discard the in-progress makeover for ${name}`}
        aria-label={`Discard the in-progress makeover for ${name}`}
      >
        ✕
      </button>
    </div>
  );
}
