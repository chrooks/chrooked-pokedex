import "./ledger-rows.css";

type Props = {
  now: number | undefined;
  was?: number;
  showDiff: boolean;
};

/** The base stat total — a summary row under the six stats. No bar (the scale
    differs from a single stat); reads base → now with a delta when the total
    changed and the diff is on. Renders an em dash when stats are incomplete. */
export function BstRow({ now, was, showDiff }: Props) {
  const hasValue = now !== undefined;
  const changed = hasValue && was !== undefined && was !== now;
  const delta = changed ? (now as number) - (was as number) : 0;

  return (
    <div className="lrow lrow--bst" data-changed={changed}>
      <span className="lrow__label mono">BST</span>
      {showDiff && changed ? (
        <span
          className="lrow__diff mono"
          aria-label={`base stat total was ${was}, now ${now}, ${delta > 0 ? "+" : ""}${delta}`}
        >
          <span className="lrow__was" aria-hidden="true">
            {was}
          </span>
          <span className="lrow__arrow" aria-hidden="true">
            →
          </span>
          <span className="lrow__now" aria-hidden="true">
            {now}
          </span>
          <span
            className="lrow__delta"
            data-dir={delta > 0 ? "up" : "down"}
            aria-hidden="true"
          >
            {delta > 0 ? `+${delta}` : delta}
          </span>
        </span>
      ) : (
        <span className="lrow__value lrow__value--bst mono">
          {hasValue ? now : <span className="lrow__empty">—</span>}
          {changed && !showDiff && (
            <>
              <span className="lrow__dot" aria-hidden="true" />
              <span className="sr-only">(edited by the Ruleset)</span>
            </>
          )}
        </span>
      )}
    </div>
  );
}
