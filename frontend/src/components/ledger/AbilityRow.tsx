import type { NavHandler } from "../DetailLedger";
import "./ledger-rows.css";

type Props = {
  slot: "primary" | "secondary" | "hidden";
  now: string | null;
  was?: string | null;
  showDiff: boolean;
  /** When present (read-only mode), a filled slot is a link to that ability's
      detail (#28). */
  onNavigate?: NavHandler;
};

const SLOT_LABEL: Record<Props["slot"], string> = {
  primary: "Primary",
  secondary: "Secondary",
  hidden: "Hidden",
};

/** One ability slot. Empty slots render an em dash; a changed slot can read
    base → now under the diff. In read-only mode a filled ability name links to
    its detail sidebar. */
export function AbilityRow({ slot, now, was, showDiff, onNavigate }: Props) {
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
            <AbilityValue slot={slot} name={now} onNavigate={onNavigate} />
          </span>
        </span>
      ) : (
        <span className="lrow__value">
          <AbilityValue slot={slot} name={now} onNavigate={onNavigate} />
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

type ValueProps = {
  slot: Props["slot"];
  name: string | null;
  onNavigate?: NavHandler;
};

/** The ability name itself: a link to its detail in read-only mode, plain text
    while editing, an em dash when the slot is empty. */
function AbilityValue({ slot, name, onNavigate }: ValueProps) {
  if (name === null) return <span className="lrow__empty">—</span>;
  if (!onNavigate) return <>{name}</>;
  return (
    <button
      type="button"
      id={`ledger-ability-link-${slot}`}
      className="lrow__link"
      aria-label={`Open ${name} ability`}
      onClick={() => onNavigate("abilities", name)}
    >
      {name}
    </button>
  );
}
