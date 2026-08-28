/* The STATS design stage. Proposes a six-stat spread via the existing suggest
   Seam, renders current → proposed per stat with the BST delta, and lets the
   author retune any stat inline (a mono number input). LOCK IN writes the
   anchor's stats through the existing CRUD route. */

import type { ProposalAlternative } from "../../types";
import { STAT_ORDER, STAT_LABEL, bst } from "../../lib/format";
import { makeoverApi } from "../../lib/makeoverApi";
import type { StatsDraft } from "../../lib/makeoverTweak";
import { StagePanel } from "./StagePanel";
import { useMakeoverStage } from "./useMakeoverStage";
import type { CommonStageProps } from "./stageProps";

const STAT_MIN = 1;
const STAT_MAX = 255;

export function StatsStage(props: CommonStageProps) {
  const { entry, initialDirection, canLock, redirectRef, registerActions, onLocked, onRedirect, onPhase, backdropTargetId } =
    props;

  const hook = useMakeoverStage<StatsDraft>({
    section: "stats",
    entry,
    initialDirection,
    onPhase,
    propose: async (id, direction) => {
      const result = await makeoverApi.suggestStats(
        id,
        direction || undefined,
        backdropTargetId ?? undefined,
      );
      return {
        draft: { stats: result.draft.stats },
        rationale: result.rationale,
        alternatives: result.alternatives as ProposalAlternative[],
      };
    },
    merge: (raw, draft) => ({ ...raw, stats: draft.stats }),
    onLocked: (draft) => onLocked({ stats: draft.stats }),
    onRedirect,
  });

  const proposed = hook.draft?.stats ?? null;

  function setStat(key: string, raw: string) {
    if (proposed === null) return;
    const value = Number(raw);
    const clamped = Number.isFinite(value)
      ? Math.min(STAT_MAX, Math.max(STAT_MIN, Math.round(value)))
      : (proposed[key] ?? 0);
    hook.editDraft({ stats: { ...proposed, [key]: clamped } });
  }

  const proposedBst = proposed ? bst(proposed) ?? 0 : null;
  const currentBst = bst(entry.stats) ?? 0;

  return (
    <StagePanel
      stageLabel="STATS"
      hook={hook}
      canLock={canLock}
      placeholder="steer the spread (e.g. faster special attacker)…"
      redirectRef={redirectRef}
      registerActions={registerActions}
      current={
        <table className="mk-stats">
          <thead>
            <tr>
              <th className="mono" scope="col">stat</th>
              <th className="mono" scope="col">now</th>
            </tr>
          </thead>
          <tbody>
            {STAT_ORDER.map((key) => (
              <tr key={key}>
                <th className="mono mk-stats__label" scope="row">
                  {STAT_LABEL[key]}
                </th>
                <td className="mono mk-stats__now">{entry.stats[key] ?? 0}</td>
              </tr>
            ))}
            <tr className="mk-stats__bst">
              <th className="mono" scope="row">BST</th>
              <td className="mono">{currentBst}</td>
            </tr>
          </tbody>
        </table>
      }
    >
      <table className="mk-stats" id="mk-stats-table">
        <thead>
          <tr>
            <th className="mono" scope="col">stat</th>
            <th className="mono" scope="col">now</th>
            <th className="mono" scope="col">proposed</th>
          </tr>
        </thead>
        <tbody>
          {STAT_ORDER.map((key) => {
            const now = entry.stats[key] ?? 0;
            const next = proposed?.[key] ?? now;
            const changed = proposed !== null && next !== now;
            return (
              <tr key={key} data-changed={changed || undefined}>
                <th className="mono mk-stats__label" scope="row">
                  {STAT_LABEL[key]}
                </th>
                <td className="mono mk-stats__now">{now}</td>
                <td className="mk-stats__proposed">
                  <input
                    className="mk-stats__input mono"
                    type="number"
                    min={STAT_MIN}
                    max={STAT_MAX}
                    aria-label={`${STAT_LABEL[key]} proposed`}
                    value={proposed ? next : ""}
                    onChange={(event) => setStat(key, event.target.value)}
                  />
                </td>
              </tr>
            );
          })}
          <tr className="mk-stats__bst">
            <th className="mono" scope="row">BST</th>
            <td className="mono">{currentBst}</td>
            <td className="mono">
              {proposedBst}
              {proposedBst !== null && proposedBst !== currentBst && (
                <span className="mk-stats__delta mono">
                  {proposedBst > currentBst ? " +" : " "}
                  {proposedBst - currentBst}
                </span>
              )}
            </td>
          </tr>
        </tbody>
      </table>
    </StagePanel>
  );
}
