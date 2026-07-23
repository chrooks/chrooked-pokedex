/* The left rail: a mono checklist of the five design stages, then a collapsed
   AUTO block (APPLY → PROOF → LOG). Each row shows its state — locked (✓), active
   (chrome rail position), or pending (dim). A navigable stage is a button; a
   future design stage is disabled (you cannot skip work). */

import {
  AUTO_STAGES,
  DESIGN_STAGES,
  canNavigate,
  isAutoStage,
  type DesignStage,
  type Stage,
} from "../../lib/makeoverStages";

interface Props {
  locked: ReadonlySet<DesignStage>;
  active: Stage;
  onNavigate: (stage: Stage) => void;
}

const LABELS: Record<Stage, string> = {
  direction: "DIRECTION",
  typing: "TYPING",
  stats: "STATS",
  abilities: "ABILITIES",
  learnset: "LEARNSET",
  apply: "APPLY",
  proof: "PROOF",
  log: "LOG",
  done: "DONE",
};

function rowState(stage: Stage, locked: ReadonlySet<DesignStage>, active: Stage): string {
  if (stage === active) return "active";
  if (!isAutoStage(stage) && locked.has(stage as DesignStage)) return "locked";
  return "pending";
}

export function StageRail({ locked, active, onNavigate }: Props) {
  const inTail = isAutoStage(active) || active === "done";
  return (
    <nav className="mk-rail" aria-label="Makeover stages" id="mk-rail">
      <ol className="mk-rail__list">
        {DESIGN_STAGES.map((stage) => {
          const state = rowState(stage, locked, active);
          const navigable = canNavigate(stage, locked, active);
          return (
            <li key={stage}>
              <button
                type="button"
                className="mk-rail__row mono"
                id={`mk-rail-${stage}`}
                data-state={state}
                aria-current={stage === active ? "step" : undefined}
                disabled={!navigable}
                onClick={() => onNavigate(stage)}
              >
                <span className="mk-rail__mark" aria-hidden="true">
                  {state === "locked" ? "✓" : state === "active" ? "▸" : "·"}
                </span>
                {LABELS[stage]}
              </button>
            </li>
          );
        })}
      </ol>

      <div className="mk-rail__auto" data-open={inTail || undefined}>
        <p className="mk-rail__auto-head mono">AUTO</p>
        <ol className="mk-rail__list">
          {AUTO_STAGES.map((stage) => (
            <li key={stage}>
              <span
                className="mk-rail__row mk-rail__row--auto mono"
                data-state={rowState(stage, locked, active)}
              >
                <span className="mk-rail__mark" aria-hidden="true">
                  {rowState(stage, locked, active) === "active" ? "▸" : "·"}
                </span>
                {LABELS[stage]}
              </span>
            </li>
          ))}
        </ol>
      </div>
    </nav>
  );
}
