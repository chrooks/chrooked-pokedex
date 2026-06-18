import type { Evolution, EvolvesInto } from "../../types";
import type { NavHandler } from "../DetailLedger";
import { spriteUrl } from "../../lib/sprites";
import "./ledger-rows.css";

type Props = {
  /** The backward edge (pre-evolution), base-derived or Ruleset-set. */
  evolution: Evolution | null;
  /** The forward edges (what this species evolves into). Base-derived. */
  evolvesInto: EvolvesInto[];
  /** Read-only cross-link out to another species' profile (#28). When absent
      (editing), the links render as plain text. */
  onNavigate?: NavHandler;
};

/** Both evolution directions as clickable species cross-links: "Evolves from"
    (the pre-evo) and "Evolves into" (forward targets, branching-safe). Each link
    carries the species sprite, name, and a readable method ("Level 26"). A
    standalone species (no pre-evo, no forward edge) renders a subtle em dash. A
    Ruleset evolution override has no `from_name`/method string, so its pre-evo
    falls back to the raw `from` id plus the structured method pairs. */
export function EvolutionSection({ evolution, evolvesInto, onNavigate }: Props) {
  const hasFrom = evolution !== null && evolution.from !== null;
  const hasInto = evolvesInto.length > 0;

  return (
    <section className="ledger__section" aria-label="Evolution">
      <h3 className="ledger__heading">Evolution</h3>
      {!hasFrom && !hasInto ? (
        <p className="ledger__evo-none" aria-label="No evolutions">
          —
        </p>
      ) : (
        <div className="ledger__evo">
          {hasFrom && <EvolvesFrom evolution={evolution} onNavigate={onNavigate} />}
          {hasInto && (
            <div className="ledger__evo-group">
              <span className="ledger__evo-dir">Evolves into</span>
              <ul className="ledger__evo-list">
                {evolvesInto.map((edge) => (
                  <li key={edge.to}>
                    <EvoLink
                      id={`ledger-evo-into-${edge.to}`}
                      chrookedId={edge.to}
                      name={edge.to_name}
                      dex={edge.to_dex}
                      method={edge.method}
                      onNavigate={onNavigate}
                    />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

type FromProps = {
  evolution: Evolution;
  onNavigate?: NavHandler;
};

/** The "Evolves from" row. With a base-derived `from_name` it renders a species
    cross-link; a Ruleset override (no `from_name`) falls back to the raw id and
    a structured method readout, preserving the pre-#31 behavior. */
function EvolvesFrom({ evolution, onNavigate }: FromProps) {
  const fromId = evolution.from as string;
  const readableMethod =
    typeof evolution.method === "string" ? evolution.method : null;

  if (evolution.from_name !== undefined) {
    return (
      <div className="ledger__evo-group">
        <span className="ledger__evo-dir">Evolves from</span>
        <ul className="ledger__evo-list">
          <li>
            <EvoLink
              id="ledger-evo-from"
              chrookedId={fromId}
              name={evolution.from_name}
              dex={evolution.from_dex ?? null}
              method={readableMethod}
              onNavigate={onNavigate}
            />
          </li>
        </ul>
      </div>
    );
  }

  // Ruleset override shape: no display name, a structured method dict.
  const methodEntries =
    typeof evolution.method === "object"
      ? Object.entries(evolution.method)
      : [];
  return (
    <div className="ledger__evo-group">
      <span className="ledger__evo-dir">Evolves from</span>
      <p className="ledger__evo-from">
        <strong>{fromId}</strong>
      </p>
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
  );
}

type LinkProps = {
  id: string;
  chrookedId: string;
  name: string;
  dex: number | null;
  method: string | null;
  onNavigate?: NavHandler;
};

/** One evolution cross-link: sprite + species name + method. The name is a
    button that navigates to that species' dex profile (#28) in read-only mode,
    or plain text while editing. */
function EvoLink({ id, chrookedId, name, dex, method, onNavigate }: LinkProps) {
  const sprite = spriteUrl(chrookedId, dex);
  const label = (
    <span className="ledger__evo-mon">
      {sprite !== null && (
        <img
          className="ledger__evo-sprite"
          src={sprite}
          alt=""
          width={40}
          height={40}
          loading="lazy"
          decoding="async"
        />
      )}
      <span className="ledger__evo-mon-name">{name}</span>
      {method !== null && (
        <span className="ledger__evo-mon-method mono">{method}</span>
      )}
    </span>
  );

  if (!onNavigate) {
    return <span className="ledger__evo-static">{label}</span>;
  }
  return (
    <button
      type="button"
      id={id}
      className="ledger__evo-link"
      aria-label={`Open ${name}${method !== null ? ` (${method})` : ""}`}
      onClick={() => onNavigate("dex", chrookedId)}
    >
      {label}
    </button>
  );
}
