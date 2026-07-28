/* The overhead rail (ac11) — a full-width second header row that shows WHERE in the
   makeover the author is, at a glance. A PASSIVE Signifier: position only, no click
   handlers — the left StageRail keeps all navigation. Each design stage reads
   locked (✓ + filled LED) / active (accent pill, + the sub-surface label when one
   is open, e.g. "ABILITIES · create new") / queued (dim) / KEPT (struck + dim). A
   compact APPLY · PROOF · LOG tail sits right-aligned for the auto stages. States
   render with the design tokens only — dim/struck stay above the 4.5:1 AA floor. */

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
  /** The active stage's open sub-surface, appended to the active pill (or null). */
  subLabel?: string | null;
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

type RowState = "locked" | "active" | "queued" | "kept";

function rowState(
  stage: DesignStage,
  selected: ReadonlySet<DesignStage>,
  sessionLocked: ReadonlySet<Stage>,
  active: Stage,
): RowState {
  if (sessionLocked.has(stage)) return "locked";
  if (stage === active) return "active";
  if (selected.has(stage)) return "queued";
  return "kept";
}

export function OverheadRail({ selected, sessionLocked, active, subLabel }: Props) {
  const inAuto = isAutoStage(active) || active === "mirror" || active === "done";

  return (
    <ol className="mk-overhead" id="mk-overhead-rail" aria-label="Makeover progress">
      {DESIGN_STAGES.map((stage) => {
        const state = rowState(stage, selected, sessionLocked, active);
        const label =
          state === "active" && subLabel ? `${LABELS[stage]} · ${subLabel}` : LABELS[stage];
        return (
          <li
            key={stage}
            className="mk-overhead__step"
            id={`mk-overhead-${stage}`}
            data-state={state}
            aria-current={stage === active ? "step" : undefined}
          >
            <span className="mk-overhead__mark" aria-hidden="true">
              {state === "locked" && <span className="mk-overhead__led" />}
              {state === "locked" ? "✓" : ""}
            </span>
            <span className="mk-overhead__label mono">{label}</span>
          </li>
        );
      })}
      <li className="mk-overhead__tail" data-open={inAuto || undefined} aria-hidden={!inAuto}>
        {(["mirror", ...AUTO_STAGES] as Stage[]).map((stage, index) => (
          <span
            key={stage}
            className="mk-overhead__auto mono"
            data-active={stage === active || undefined}
            aria-current={stage === active ? "step" : undefined}
          >
            {index > 0 && <span className="mk-overhead__auto-sep"> · </span>}
            {LABELS[stage]}
          </span>
        ))}
      </li>
    </ol>
  );
}
