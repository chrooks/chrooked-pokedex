import type { Evolution } from "../../types";
import "./ledger-rows.css";

type Props = {
  evolution: Evolution | null;
};

/** Evolution, when the Ruleset sets one. The base snapshot carries no evolution
    to diff against, so this is shown as Ruleset-set rather than base → now. */
export function EvolutionSection({ evolution }: Props) {
  if (evolution === null) {
    return null;
  }
  const methodEntries = Object.entries(evolution.method);
  return (
    <section className="ledger__section" aria-label="Evolution">
      <h3 className="ledger__heading">Evolution</h3>
      <div className="ledger__evo">
        {evolution.from !== null && (
          <p className="ledger__evo-from">
            from <strong>{evolution.from}</strong>
          </p>
        )}
        {methodEntries.length > 0 && (
          <dl className="ledger__evo-method mono">
            {methodEntries.map(([key, value]) => (
              <div key={key} className="ledger__evo-pair">
                <dt>{key}</dt>
                <dd>{String(value)}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </section>
  );
}
