import type { Fit } from "../../lib/teamFit";
import { TypeChip } from "../TypeChip";

type Props = { fit: Fit };

const MAX_TYPES = 2; // a chip shows two types, then +n (the Why panel lists all)

function Types({ types }: { types: readonly string[] }) {
  const shown = types.slice(0, MAX_TYPES);
  const more = types.length - shown.length;
  return (
    <>
      {shown.map((type) => (
        <TypeChip key={type} type={type} variant="code" />
      ))}
      {more > 0 && <span className="fit-chips__more mono">+{more}</span>}
    </>
  );
}

/**
 * The reasons a pool card ranks where it does (#119): what it patches, what it
 * opens, and the STAB it adds. One line under the card, so the sort explains
 * itself without a legend. The Why panel carries the full list.
 */
export function FitChips({ fit }: Props) {
  const hasReasons = fit.patched.length + fit.opened.length + fit.offense.length > 0;
  if (!hasReasons) return <div className="fit-chips fit-chips--none">no change</div>;
  return (
    <div className="fit-chips">
      {fit.patched.length > 0 && (
        <span className="fit-chips__chip" data-kind="patches" title={`Patches ${fit.patched.join(", ")}`}>
          <span className="fit-chips__label">patches</span>
          <Types types={fit.patched} />
        </span>
      )}
      {fit.opened.length > 0 && (
        <span className="fit-chips__chip" data-kind="opens" title={`Opens ${fit.opened.join(", ")}`}>
          <span className="fit-chips__label">opens</span>
          <Types types={fit.opened} />
        </span>
      )}
      {fit.patched.length === 0 && fit.offense.length > 0 && (
        <span className="fit-chips__chip" data-kind="stab" title={`New STAB vs ${fit.offense.join(", ")}`}>
          <span className="fit-chips__label">+STAB</span>
          <Types types={fit.offense} />
        </span>
      )}
    </div>
  );
}
