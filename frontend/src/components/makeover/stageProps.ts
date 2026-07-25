/* The props every design stage shares. The workbench threads these down; each
   stage adds its own section-specific extras (type pool, ability options, move
   pool + rubric, the line's byId map for mirror-down). */

import type { RefObject } from "react";
import type { DexEntry } from "../../types";
import type { StageFacts } from "../../lib/makeoverApi";
import type { StageActions } from "./StagePanel";

export interface CommonStageProps {
  /** The anchor species being made over (live from the dex; reloads after locks). */
  entry: DexEntry;
  /** The direction carried from the direction stage — the first proposal's steer. */
  initialDirection: string;
  /** Lock gating from the stage machine (earlier stages must be locked first). */
  canLock: boolean;
  /** Shared redirect input ref so the workbench's `t` shortcut can focus it. */
  redirectRef: RefObject<HTMLTextAreaElement>;
  /** Register the stage's imperative actions for the workbench keyboard path. */
  registerActions: (actions: StageActions | null) => void;
  /** Called on a clean LOCK IN with the facts to land in the line strip + advance.
      `writtenIds` are the species this lock actually wrote (default: the anchor),
      so the read-back tail checks exactly what this session touched. */
  onLocked: (facts: StageFacts, writtenIds?: string[]) => void;
  /** Called on a re-roll with the composed redirect, so the session harvests it. */
  onRedirect: (text: string) => void;
}

/** The 18 canonical types — the picker pool for the typing stage. The backend
    still validates a locked typing against the real merged pool (the loader is
    the gate); offering the standard set keeps the picker offline + stable. */
export const TYPE_POOL: readonly string[] = [
  "Normal",
  "Fire",
  "Water",
  "Electric",
  "Grass",
  "Ice",
  "Fighting",
  "Poison",
  "Ground",
  "Flying",
  "Psychic",
  "Bug",
  "Rock",
  "Ghost",
  "Dragon",
  "Dark",
  "Steel",
  "Fairy",
];
