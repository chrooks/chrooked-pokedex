import "./ledger-rows.css";

type Props = {
  label: string;
  now: number | undefined;
  was?: number;
  showDiff: boolean;
};

const STAT_MAX = 255;

/** One stat: a mono figure + a proportional bar. A stat absent from the base
    data (some cosmetic forms carry no stat block) reads as an em dash, never 0.
    When the diff is on and this stat changed, it reads base → now with a delta. */
export function StatRow({ label, now, was, showDiff }: Props) {
  const hasValue = now !== undefined;
  const changed = hasValue && was !== undefined && was !== now;
  const delta = changed ? (now as number) - (was as number) : 0;

  return (
    <div className="lrow lrow--stat" data-changed={changed}>
      <span className="lrow__label mono">{label}</span>
      {showDiff && changed ? (
        <span
          className="lrow__diff mono"
          aria-label={`was ${was}, now ${now}, ${delta > 0 ? "+" : ""}${delta}`}
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
        <span className="lrow__value mono">
          {hasValue ? now : <span className="lrow__empty">—</span>}
          {changed && !showDiff && (
            <>
              <span className="lrow__dot" aria-hidden="true" />
              <span className="sr-only">(edited by the Ruleset)</span>
            </>
          )}
        </span>
      )}
      <span className="lrow__bar" aria-hidden="true">
        <span
          className="lrow__bar-fill"
          style={{ width: `${hasValue ? Math.min(100, (now / STAT_MAX) * 100) : 0}%` }}
          data-changed={changed}
        />
      </span>
    </div>
  );
}
