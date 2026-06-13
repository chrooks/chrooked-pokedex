import { TypeChip } from "../TypeChip";
import "./ledger-rows.css";

type Props = {
  now: string[];
  was?: string[];
  showDiff: boolean;
};

/** The species' types. Under the diff (when changed), the base typing shows
    struck-through ahead of the current one. */
export function TypesRow({ now, was, showDiff }: Props) {
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
      {now.map((type) => (
        <TypeChip key={type} type={type} />
      ))}
    </div>
  );
}

function sameTypes(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((type, i) => type === b[i]);
}
