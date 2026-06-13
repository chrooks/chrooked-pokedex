import type { LearnsetMove } from "../../types";
import "./ledger-rows.css";

type Props = {
  now: LearnsetMove[];
  was?: LearnsetMove[];
  showDiff: boolean;
};

/** The level-up learnset. It is a whole-list override, so the diff can't read
    field-by-field; instead it states plainly that the Ruleset replaced the base
    list, with the before/after counts. New moves (absent from base) are marked. */
export function LearnsetSection({ now, was, showDiff }: Props) {
  const replaced = was !== undefined;
  const baseMoves = new Set((was ?? []).map((m) => m.move.toLowerCase()));

  return (
    <section className="ledger__section" aria-label="Learnset">
      <div className="ledger__heading-row">
        <h3 className="ledger__heading">Learnset</h3>
        {replaced && (
          <span className="ledger__note mono" data-on={showDiff}>
            replaced · {was?.length ?? 0} → {now.length}
          </span>
        )}
      </div>
      {now.length === 0 ? (
        <p className="lrow__empty">No level-up moves.</p>
      ) : (
        <ol className="ledger__learnset">
          {now.map((entry, index) => {
            const isNew = replaced && !baseMoves.has(entry.move.toLowerCase());
            return (
              <li
                key={`${entry.level}-${entry.move}-${index}`}
                className="ledger__move"
                data-new={showDiff && isNew}
              >
                <span className="ledger__move-lv mono">
                  {entry.level === 0 ? "—" : `L${entry.level}`}
                </span>
                <span className="ledger__move-name">{entry.move}</span>
                {showDiff && isNew && (
                  <span className="ledger__move-new mono">new</span>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
