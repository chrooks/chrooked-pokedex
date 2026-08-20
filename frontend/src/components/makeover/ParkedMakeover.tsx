/* The parked-makeover dock: one pill per makeover dismissed with "← dex"/Esc
   rather than finished. Each workbench is still mounted behind the dex, so
   RESUME returns to the exact stage with any unlocked draft intact — and its
   suggest keeps processing while parked. The LED speaks the AutoTail's
   vocabulary: chrome pulse = proposing, amber = a proposal is ready to review,
   chrome solid = the propose failed. Discard (✕) is the only path that throws
   a draft away. */

import { activityLabel, type MakeoverActivity } from "../../lib/makeoverActivity";
import "./makeover.css";

export interface ParkedItem {
  id: string;
  name: string;
  activity: MakeoverActivity;
}

type Props = {
  items: readonly ParkedItem[];
  onResume: (id: string) => void;
  onDiscard: (id: string) => void;
};

export function ParkedMakeoverDock({ items, onResume, onDiscard }: Props) {
  if (items.length === 0) return null;
  return (
    <div className="mk-dock" id="makeover-dock" role="list" aria-label="Parked makeovers">
      {items.map((item) => {
        const status = activityLabel(item.activity);
        return (
          <div className="mk-parked" role="listitem" key={item.id} id={`parked-makeover-${item.id}`}>
            <button
              type="button"
              id={`parked-makeover-resume-${item.id}`}
              className="mk-parked__resume mono"
              onClick={() => onResume(item.id)}
              title={status ?? undefined}
              aria-label={`Resume the makeover for ${item.name}${status ? ` — ${status}` : ""}`}
            >
              <span
                className="mk-parked__led"
                data-activity={item.activity}
                aria-hidden="true"
              />
              <span>
                resume makeover · <strong>{item.name}</strong>
              </span>
              {status !== null && <span className="sr-only"> — {status}</span>}
            </button>
            <button
              type="button"
              id={`parked-makeover-discard-${item.id}`}
              className="mk-parked__discard"
              onClick={() => onDiscard(item.id)}
              title={`Discard the in-progress makeover for ${item.name}`}
              aria-label={`Discard the in-progress makeover for ${item.name}`}
            >
              ✕
            </button>
          </div>
        );
      })}
    </div>
  );
}
