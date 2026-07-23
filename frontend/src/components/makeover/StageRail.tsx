/* The left rail — the à la carte picker (ac8). The five design stages are each
   SELECTED (in the journey) or KEEP (skipped untouched). A row not yet locked this
   session is a TOGGLE (click or space flips SELECTED ⇄ KEEP); a row locked this
   session is a nav button (revisit). Below sits the AUTO block (MIRROR when it is
   the mirror-only journey, then APPLY → PROOF → LOG). States render with the
   design tokens only: --chrome marks the active rail position, --edited the locked
   ✓, --text-dim the rest. */

import {
  AUTO_STAGES,
  DESIGN_STAGES,
  isAutoStage,
  type DesignStage,
  type Stage,
} from "../../lib/makeoverStages";

interface Props {
  selected: ReadonlySet<DesignStage>;
  sessionLocked: ReadonlySet<Stage>;
  active: Stage;
  onNavigate: (stage: Stage) => void;
  onToggle: (stage: DesignStage) => void;
}

const LABELS: Record<Stage, string> = {
  direction: "DIRECTION",
  typing: "TYPING",
  stats: "STATS",
  abilities: "ABILITIES",
  learnset: "LEARNSET",
  mirror: "MIRROR",
  apply: "APPLY",
  proof: "PROOF",
  log: "LOG",
  done: "DONE",
};

type RowState = "locked" | "active" | "pending" | "keep";

function designRowState(
  stage: DesignStage,
  selected: ReadonlySet<DesignStage>,
  sessionLocked: ReadonlySet<Stage>,
  active: Stage,
): RowState {
  if (sessionLocked.has(stage)) return "locked";
  if (stage === active) return "active";
  if (selected.has(stage)) return "pending";
  return "keep";
}

const MARK: Record<RowState, string> = {
  locked: "✓",
  active: "▸",
  pending: "·",
  keep: "○",
};

export function StageRail({ selected, sessionLocked, active, onNavigate, onToggle }: Props) {
  const mirrorOnly = selected.size === 0;
  const autoStages: Stage[] = mirrorOnly ? ["mirror", ...AUTO_STAGES] : [...AUTO_STAGES];

  return (
    <nav className="mk-rail" aria-label="Makeover stages" id="mk-rail">
      <p className="mk-rail__hint mono">pick facets · space toggles</p>
      <ol className="mk-rail__list">
        {DESIGN_STAGES.map((stage) => {
          const state = designRowState(stage, selected, sessionLocked, active);
          const isLocked = state === "locked";
          return (
            <li key={stage}>
              <button
                type="button"
                className="mk-rail__row mono"
                id={`mk-rail-${stage}`}
                data-state={state}
                aria-current={stage === active ? "step" : undefined}
                aria-pressed={isLocked ? undefined : state !== "keep"}
                title={
                  isLocked
                    ? `Revisit ${LABELS[stage]}`
                    : state === "keep"
                      ? `KEEP — click to add ${LABELS[stage]} to the makeover`
                      : `Click to KEEP (skip) ${LABELS[stage]}`
                }
                onClick={() => (isLocked ? onNavigate(stage) : onToggle(stage))}
              >
                <span className="mk-rail__mark" aria-hidden="true">
                  {MARK[state]}
                </span>
                {LABELS[stage]}
                {state === "keep" && <span className="mk-rail__keep mono">keep</span>}
              </button>
            </li>
          );
        })}
      </ol>

      <div className="mk-rail__auto" data-open={isAutoStage(active) || active === "mirror" || active === "done" || undefined}>
        <p className="mk-rail__auto-head mono">AUTO</p>
        <ol className="mk-rail__list">
          {autoStages.map((stage) => (
            <li key={stage}>
              <span
                className="mk-rail__row mk-rail__row--auto mono"
                data-state={
                  sessionLocked.has(stage) ? "locked" : stage === active ? "active" : "pending"
                }
              >
                <span className="mk-rail__mark" aria-hidden="true">
                  {sessionLocked.has(stage) ? "✓" : stage === active ? "▸" : "·"}
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
