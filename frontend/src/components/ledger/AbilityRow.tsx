import "./ledger-rows.css";

type Props = {
  slot: "primary" | "secondary" | "hidden";
  now: string | null;
  was?: string | null;
  showDiff: boolean;
};

const SLOT_LABEL: Record<Props["slot"], string> = {
  primary: "Primary",
  secondary: "Secondary",
  hidden: "Hidden",
};

/** One ability slot. Empty slots render an em dash; a changed slot can read
    base → now under the diff. */
export function AbilityRow({ slot, now, was, showDiff }: Props) {
  const changed = was !== undefined && was !== now;
  return (
    <div className="lrow lrow--ability" data-changed={changed}>
      <span className="lrow__label">{SLOT_LABEL[slot]}</span>
      {showDiff && changed ? (
        <span className="lrow__diff" aria-label={`was ${was ?? "none"}, now ${now ?? "none"}`}>
          <span className="lrow__was" aria-hidden="true">
            {was ?? "—"}
          </span>
          <span className="lrow__arrow" aria-hidden="true">
            →
          </span>
          <span className="lrow__now" aria-hidden="true">
            {now ?? "—"}
          </span>
        </span>
      ) : (
        <span className="lrow__value">
          {now ?? <span className="lrow__empty">—</span>}
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
