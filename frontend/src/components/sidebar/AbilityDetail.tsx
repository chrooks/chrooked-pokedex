/* Read-only detail body for the Ability detail sidebar.
   Renders the ability's fields and (when edited) the base→now diff.
   No inputs, no Save/Delete. Reuses lrow / editor-section / ability-diff
   primitives from the existing editors. */

import type { Ability, AbilityField } from "../../types";
import { isAbilityEdited, ABILITY_FIELD_LABEL } from "../../lib/format";
import "../editors/editors.css";
import "../ledger/ledger-rows.css";

type Props = {
  ability: Ability;
};

export function AbilityDetail({ ability }: Props) {
  const edited = isAbilityEdited(ability);

  const currentOf: Record<AbilityField, string> = {
    name: ability.name,
    description: ability.description,
  };

  const diffRows = edited
    ? ability.overridden_fields.map((field) => ({
        field,
        was: ability.base[field],
        now: currentOf[field],
      }))
    : [];

  return (
    <div id="ability-detail">
      {edited && (
        <section
          id="ability-detail-diff"
          className="ability-diff editor-section"
          aria-label="What the Ruleset changed"
        >
          {diffRows.map(({ field, was, now }) => (
            <div key={field} className="lrow lrow--ability" data-changed="true">
              <span className="lrow__label">{ABILITY_FIELD_LABEL[field]}</span>
              {was !== undefined ? (
                <span
                  className="lrow__diff"
                  aria-label={`was ${was || "none"}, now ${now || "none"}`}
                >
                  <span className="lrow__was" aria-hidden="true">
                    {was || "—"}
                  </span>
                  <span className="lrow__arrow" aria-hidden="true">
                    →
                  </span>
                  <span className="lrow__now" aria-hidden="true">
                    {now || "—"}
                  </span>
                </span>
              ) : (
                <span className="lrow__value">
                  {now || <span className="lrow__empty">—</span>}
                  <span className="ability-diff__new">new</span>
                </span>
              )}
            </div>
          ))}
        </section>
      )}

      <section
        id="ability-detail-description"
        className="editor-section"
        aria-label="Description"
      >
        <h3 className="editor-section__heading">Description</h3>
        {ability.description ? (
          <p className="ability-detail__desc">{ability.description}</p>
        ) : (
          <p className="lrow__empty">No description.</p>
        )}
      </section>
    </div>
  );
}
