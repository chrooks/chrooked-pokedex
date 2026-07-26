/* The grouped-by-evolution-line distribution view shared by DistributePanel
   (ability → slot) and MoveDistributePanel (move → level). The controlling unit
   is the LINE: one include checkbox and one value control per evolution family,
   applied to every present member. The breadth slider is a pure client-side trim
   of the already-fetched proposal (top-K lines by rank) — it fires NO new LLM
   call. Presentational only; the panel owns the source-of-truth rows, the include
   set, and the per-line value map, and passes the value control in as a render
   prop (a slot <select> or a level <input>).

   ponytail: line-level only — no per-member override/expansion. Members of the
   same family share one slot/level. Upgrade path: add an expand-to-members row if
   a real case needs divergent per-member values. */

import type { ReactNode } from "react";
import type { DexEntry } from "../../types";
import type { LineGroup } from "./distributionLines";

interface Props {
  groups: readonly LineGroup[];
  byId: ReadonlyMap<string, DexEntry>;
  /** The set of included line ids. `included.size` IS the slider's K reading, so
      a slider move and a manual toggle stay in sync by construction. */
  included: ReadonlySet<string>;
  /** Slider → set included to the top-K lines by rank (pure trim, no LLM call). */
  onSlider: (k: number) => void;
  onToggleLine: (lineId: string) => void;
  onRemoveLine: (lineId: string) => void;
  onAll: () => void;
  onNone: () => void;
  /** id namespace ("mk-distribute" | "mk-move-distribute") for human-usable ids. */
  idPrefix: string;
  /** The per-line value control — a slot <select> or a level <input>. */
  renderValue: (group: LineGroup) => ReactNode;
  /** Per-member "what this would overwrite" line, shown under the group so the
      author sees the clobber before committing (ability: the current ability in
      the chosen slot; move: the current learn level). Recomputed each render, so
      it tracks the live slot/level. Omit → no detail line. */
  renderDetail?: (group: LineGroup) => ReactNode;
}

export function LineDistribution({
  groups,
  byId,
  included,
  onSlider,
  onToggleLine,
  onRemoveLine,
  onAll,
  onNone,
  idPrefix,
  renderValue,
  renderDetail,
}: Props) {
  const total = groups.length;
  const namesOf = (g: LineGroup) => g.members.map((m) => byId.get(m)?.name ?? m).join(" · ");

  return (
    <div className="mk-linedist" id={`${idPrefix}-lines`}>
      {total > 1 && (
        <div className="mk-linedist__trim">
          <label className="mk-linedist__slider-label mono" htmlFor={`${idPrefix}-breadth`}>
            lines: <span className="mk-linedist__k">{included.size}</span> / {total}
          </label>
          <input
            type="range"
            id={`${idPrefix}-breadth`}
            className="mk-linedist__slider"
            min={0}
            max={total}
            step={1}
            value={Math.min(included.size, total)}
            onChange={(event) => onSlider(Number(event.target.value))}
            aria-label={`Evolution lines included: ${included.size} of ${total}`}
          />
          <div className="mk-linedist__bulk">
            <button
              type="button"
              id={`${idPrefix}-all`}
              className="mk-linedist__bulk-btn mono"
              onClick={onAll}
            >
              all
            </button>
            <button
              type="button"
              id={`${idPrefix}-none`}
              className="mk-linedist__bulk-btn mono"
              onClick={onNone}
            >
              none
            </button>
          </div>
        </div>
      )}

      <ul className="mk-linedist__list">
        {groups.map((group) => {
          const isIncluded = included.has(group.lineId);
          const names = namesOf(group);
          return (
            <li
              key={group.lineId}
              id={`${idPrefix}-group-${group.lineId}`}
              className="mk-linedist__group"
              data-included={isIncluded}
            >
              <div className="mk-linedist__main">
                <input
                  type="checkbox"
                  className="mk-linedist__check"
                  id={`${idPrefix}-line-${group.lineId}`}
                  checked={isIncluded}
                  onChange={() => onToggleLine(group.lineId)}
                  aria-label={`Include the ${names} line`}
                />
                <label className="mk-linedist__names" htmlFor={`${idPrefix}-line-${group.lineId}`}>
                  {names}
                  <span className="mk-linedist__count mono" aria-hidden="true">
                    {group.members.length}
                  </span>
                </label>
                {renderValue(group)}
                <button
                  type="button"
                  className="mk-lrow__remove mk-linedist__remove mono"
                  aria-label={`Remove the ${names} line`}
                  title={`Remove the ${names} line`}
                  onClick={() => onRemoveLine(group.lineId)}
                >
                  ✕
                </button>
              </div>
              {renderDetail && (
                <div
                  className="mk-linedist__detail mono"
                  id={`${idPrefix}-detail-${group.lineId}`}
                >
                  {renderDetail(group)}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
