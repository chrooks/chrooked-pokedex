/* The TYPING design stage. Proposes 1-2 types via the existing suggest Seam,
   renders the current → proposed typing as chips, and lets the author swap either
   slot inline (a mono type select). LOCK IN writes the anchor's types through the
   existing CRUD route. */

import { TypeChip } from "../TypeChip";
import type { ProposalAlternative } from "../../types";
import { makeoverApi } from "../../lib/makeoverApi";
import type { TypingDraft } from "../../lib/makeoverTweak";
import { StagePanel } from "./StagePanel";
import { useMakeoverStage } from "./useMakeoverStage";
import { TYPE_POOL, type CommonStageProps } from "./stageProps";

function typingAltLabel(value: unknown): string {
  return typeof value === "string" ? value : String(value);
}

/** Swap an alternative typing ("Water/Dragon" or "Dragon") into the draft. */
function applyTypingAlt(alt: ProposalAlternative): TypingDraft {
  if (typeof alt.value === "string") {
    return { types: alt.value.split("/").map((t) => t.trim()).filter(Boolean).slice(0, 2) };
  }
  return { types: [] };
}

export function TypingStage(props: CommonStageProps) {
  const { entry, initialDirection, canLock, redirectRef, registerActions, onLocked, onRedirect } =
    props;

  const hook = useMakeoverStage<TypingDraft>({
    section: "typing",
    entry,
    initialDirection,
    propose: async (id, direction) => {
      const result = await makeoverApi.suggestTyping(id, direction || undefined);
      return {
        draft: { types: result.draft.types },
        rationale: result.rationale,
        alternatives: result.alternatives as ProposalAlternative[],
      };
    },
    merge: (raw, draft) => ({ ...raw, types: draft.types }),
    onLocked: (draft) => onLocked({ types: draft.types }),
    onRedirect,
  });

  const proposed = hook.draft?.types ?? [];

  function setSlot(index: number, value: string) {
    const next = [...proposed];
    if (value === "") next.splice(index, 1);
    else next[index] = value;
    hook.editDraft({ types: next.filter(Boolean).slice(0, 2) });
  }

  return (
    <StagePanel
      stageLabel="TYPING"
      hook={hook}
      canLock={canLock}
      placeholder="steer the typing (e.g. lean more defensive)…"
      redirectRef={redirectRef}
      registerActions={registerActions}
      applyAlternative={(alt) => applyTypingAlt(alt)}
      altLabel={typingAltLabel}
      current={
        <div className="mk-cols">
          <div className="mk-col">
            <p className="mk-col__head mono">current</p>
            <div className="mk-chips">
              {entry.types.map((t) => (
                <TypeChip key={t} type={t} />
              ))}
            </div>
          </div>
        </div>
      }
    >
      <div className="mk-cols">
        <div className="mk-col">
          <p className="mk-col__head mono">current</p>
          <div className="mk-chips">
            {entry.types.map((t) => (
              <TypeChip key={t} type={t} />
            ))}
          </div>
        </div>
        <div className="mk-col">
          <p className="mk-col__head mono">proposed</p>
          <div className="mk-chips">
            {proposed.map((t) => (
              <TypeChip key={t} type={t} />
            ))}
            {proposed.length === 0 && <span className="mk-empty mono">—</span>}
          </div>
          <div className="mk-typing__editors">
            {[0, 1].map((index) => (
              <select
                key={index}
                className="mk-select mono"
                aria-label={`Type ${index + 1}`}
                value={proposed[index] ?? ""}
                onChange={(event) => setSlot(index, event.target.value)}
              >
                <option value="">{index === 0 ? "— (required)" : "— (none)"}</option>
                {TYPE_POOL.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            ))}
          </div>
        </div>
      </div>
    </StagePanel>
  );
}
