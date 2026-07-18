import { useMemo, useState } from "react";
import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import { hasTypeModifier } from "../../lib/abilityTypeModifiers";
import { speciesMatchups } from "../../lib/speciesMatchups";
import type { SpeciesMatchupMember } from "../../lib/speciesMatchups";
import type { AbilitySlots } from "../../types";
import { TypeChip } from "../TypeChip";
import { PokeballSpinner } from "../PokeballSpinner";
import "../tabs/type-chart.css";
import "./type-matchups.css";

type Props = {
  types: string[];
  abilities: AbilitySlots;
};

/** One (slot, name) ability option for the toggle, deduped by name — Marill's
    primary and secondary both read "Huge Power", so that pair collapses to one
    button rather than two identical ones. */
function abilityOptions(abilities: AbilitySlots): string[] {
  const seen = new Set<string>();
  const options: string[] = [];
  for (const name of [abilities.primary, abilities.secondary, abilities.hidden]) {
    if (name && !seen.has(name)) {
      seen.add(name);
      options.push(name);
    }
  }
  return options;
}

/** The species' combined type matchups (both types multiplied together for
    defense, best-of for offense), with a toggle to fold in each of the
    species' abilities that actually changes a matchup (e.g. Sap Sipper making
    Grass ×0). Mirrors the Type Chart tab's breakdown-panel layout so the two
    surfaces read as one visual language. */
export function TypeMatchupsSection({ types, abilities }: Props) {
  const { data: cells, isLoading } = useResource(api.typeChart);
  const options = useMemo(() => abilityOptions(abilities), [abilities]);
  const toggleable = useMemo(() => options.filter(hasTypeModifier), [options]);
  const [selected, setSelected] = useState<string | null>(toggleable[0] ?? null);

  const activeAbility = toggleable.includes(selected ?? "") ? selected : null;

  const matchups = useMemo(
    () => speciesMatchups(types, cells ?? [], activeAbility),
    [types, cells, activeAbility],
  );

  if (isLoading) {
    return (
      <section className="ledger__section" aria-label="Type matchups">
        <h3 className="ledger__heading">Type matchups</h3>
        <PokeballSpinner size={24} />
      </section>
    );
  }

  return (
    <section className="ledger__section" aria-label="Type matchups">
      <h3 className="ledger__heading">Type matchups</h3>
      {toggleable.length > 0 && (
        <div className="tm-toggle" role="group" aria-label="Ability affecting matchups">
          <button
            type="button"
            className="tm-toggle__chip"
            data-active={activeAbility === null}
            onClick={() => setSelected(null)}
          >
            Base typing
          </button>
          {toggleable.map((name) => (
            <button
              key={name}
              type="button"
              className="tm-toggle__chip"
              data-active={activeAbility === name}
              onClick={() => setSelected(name)}
            >
              {name}
            </button>
          ))}
        </div>
      )}

      <div className="tm-breakdown">
        <div className="tm-breakdown__col">
          <h4 className="tc-breakdown__section-title">Defending</h4>
          <MatchupBucket label="Weak to" members={matchups.defense.weak} hue="red" />
          <MatchupBucket label="Resists" members={matchups.defense.resist} hue="green" />
          <MatchupBucket label="Immune to" members={matchups.defense.immune} hue="blue" />
          <MatchupBucket
            label="Neutral"
            members={matchups.defense.neutral}
            hue="grey"
            tone="quiet"
          />
        </div>
        <div className="tm-breakdown__col">
          <h4 className="tc-breakdown__section-title">Attacking</h4>
          <MatchupBucket label="Strong against" members={matchups.offense.strong} hue="green" />
          <MatchupBucket label="Resisted by" members={matchups.offense.resisted} hue="red" />
          <MatchupBucket label="No effect on" members={matchups.offense.noEffect} hue="ink" />
          <MatchupBucket
            label="Neutral"
            members={matchups.offense.neutral}
            hue="grey"
            tone="quiet"
          />
        </div>
      </div>
    </section>
  );
}

type BucketHue = "red" | "green" | "blue" | "grey" | "ink";

function MatchupBucket({
  label,
  members,
  hue,
  tone = "loud",
}: {
  label: string;
  members: SpeciesMatchupMember[];
  hue: BucketHue;
  tone?: "loud" | "quiet";
}) {
  return (
    <div className="tc-bucket" data-tone={tone} data-hue={hue} data-empty={members.length === 0}>
      <div className="tc-bucket__head">
        <span className="tc-bucket__label">{label}</span>
        <span className="tc-bucket__count" aria-label={`${members.length} types`}>
          {members.length}
        </span>
      </div>
      {members.length === 0 ? (
        <p className="tc-bucket__empty" aria-hidden="true">
          —
        </p>
      ) : (
        <ul className="tc-bucket__chips">
          {members.map((member) => (
            <li key={member.type}>
              <TypeChip type={member.type} variant="code" />
              {!isStandard(member.value) && (
                <span className="tm-multiplier">×{member.value}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The usual single-type steps — anything else (a dual-type ×4/×0.25, or an
    ability's flat multiplier) gets its exact value called out on the chip. */
function isStandard(value: number): boolean {
  return value === 0 || value === 0.5 || value === 1 || value === 2;
}
