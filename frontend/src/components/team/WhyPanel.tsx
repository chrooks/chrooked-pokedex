import type { Fit } from "../../lib/teamFit";
import type { DexEntry } from "../../types";
import { TypeChip } from "../TypeChip";

type Props = {
  entry: DexEntry | null;
  fit: Fit | null;
};

function Line({ label, types, kind }: { label: string; types: readonly string[]; kind: string }) {
  if (types.length === 0) return null;
  return (
    <li className="why__line" data-kind={kind}>
      <span className="why__label">{label}</span>
      <span className="why__types">
        {types.map((type) => (
          <TypeChip key={type} type={type} variant="code" />
        ))}
      </span>
    </li>
  );
}

/**
 * The full reasons for the hovered or focused pool card (#119), beside the
 * Holes panel so "what is wrong" and "what this pick does about it" read
 * together. Empty until a card is pointed at.
 */
export function WhyPanel({ entry, fit }: Props) {
  return (
    <section className="why" id="team-why" aria-labelledby="team-why-title" aria-live="polite">
      <h3 className="why__title" id="team-why-title">
        Why{entry && fit ? ` · ${entry.name}` : ""}
        {fit && <span className="why__score mono">{fit.score > 0 ? `+${fit.score}` : fit.score}</span>}
      </h3>
      {entry && fit ? (
        <ul className="why__list">
          <Line label="Fixes" types={fit.fixed} kind="fixed" />
          <Line label="Patches" types={fit.patched} kind="patches" />
          <Line label="First answer to" types={fit.covered} kind="covered" />
          <Line label="Opens" types={fit.opened} kind="opens" />
          <Line label="New STAB vs" types={fit.offense} kind="stab" />
          {fit.fixed.length + fit.patched.length + fit.covered.length + fit.opened.length + fit.offense.length === 0 && (
            <li className="why__line why__none">Changes nothing on this team.</li>
          )}
        </ul>
      ) : (
        <p className="why__empty">Hover a species to see why it fits.</p>
      )}
    </section>
  );
}
