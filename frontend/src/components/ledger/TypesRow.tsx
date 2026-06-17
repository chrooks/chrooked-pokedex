import type { NavHandler } from "../DetailLedger";
import { TypeChip } from "../TypeChip";
import "./ledger-rows.css";

type Props = {
  now: string[];
  was?: string[];
  showDiff: boolean;
  /** When present (read-only mode), each current type is a link to the Type
      Chart breakdown (#28). Absent while the species editor is open. */
  onNavigate?: NavHandler;
};

/** The species' types. Under the diff (when changed), the base typing shows
    struck-through ahead of the current one. In read-only mode each current type
    is a keyboard-accessible link that opens its Type Chart breakdown. */
export function TypesRow({ now, was, showDiff, onNavigate }: Props) {
  const changed = was !== undefined && !sameTypes(was, now);
  return (
    <div className="lrow__types">
      {showDiff && changed && was !== undefined && (
        <span className="lrow__types-was">
          {was.map((type) => (
            <TypeChip key={type} type={type} />
          ))}
          <span className="lrow__arrow" aria-hidden="true">
            →
          </span>
        </span>
      )}
      {now.map((type) =>
        onNavigate ? (
          <button
            key={type}
            type="button"
            id={`ledger-type-link-${type.toLowerCase()}`}
            className="lrow__link lrow__link--chip"
            aria-label={`Open ${type} type`}
            onClick={() => onNavigate("type-chart", type)}
          >
            <TypeChip type={type} />
          </button>
        ) : (
          <TypeChip key={type} type={type} />
        ),
      )}
    </div>
  );
}

function sameTypes(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((type, i) => type === b[i]);
}
