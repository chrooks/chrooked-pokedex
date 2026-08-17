/* Read-only detail body for the Move detail sidebar.
   Renders the move's fields and (when edited) the base→now diff.
   No inputs, no Save/Delete. Reuses lrow / editor-section / ability-diff
   primitives from the existing editors. */

import type { Move, MoveField } from "../../types";
import { flagLabel, isMoveEdited, MOVE_FIELD_LABEL } from "../../lib/format";
import { TypeChip } from "../TypeChip";
import { CategoryChip } from "../CategoryChip";
import { TargetGlyph } from "../TargetGrid";
import { targetLabel } from "../../lib/moveTargets";
import "../editors/editors.css";
import "../ledger/ledger-rows.css";

type Props = {
  move: Move;
};

export function MoveDetail({ move }: Props) {
  const edited = isMoveEdited(move);

  const currentOf: Partial<Record<MoveField, string>> = {
    name: move.name,
    type: move.type,
    category: move.category,
    power: move.power !== null ? String(move.power) : "",
    accuracy: move.accuracy !== null ? String(move.accuracy) : "",
    pp: move.pp !== null ? String(move.pp) : "",
    description: move.description,
    effect: move.effect,
    argument: move.argument !== null ? JSON.stringify(move.argument) : "",
    additional_effects: move.additional_effects
      .map((ae) => `${ae.effect} (${ae.chance}%)`)
      .join(", "),
    flags: move.flags.map(flagLabel).join(", "),
    priority: String(move.priority),
    target: targetLabel(move.target),
  };

  const diffRows = edited
    ? move.overridden_fields.map((field) => ({
        field,
        was:
          field in move.base
            ? formatValue(move.base[field as keyof typeof move.base])
            : undefined,
        now: currentOf[field] ?? "",
      }))
    : [];

  return (
    <div id="move-detail">
      {edited && (
        <section
          id="move-detail-diff"
          className="ability-diff editor-section"
          aria-label="What the Ruleset changed"
        >
          {diffRows.map(({ field, was, now }) => (
            <div key={field} className="lrow lrow--ability" data-changed="true">
              <span className="lrow__label">{MOVE_FIELD_LABEL[field]}</span>
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
        id="move-detail-fields"
        className="editor-section"
        aria-label="Move fields"
      >
        <dl className="move-detail__dl">
          <div className="lrow">
            <dt className="lrow__label">Type</dt>
            <dd className="lrow__value">
              <TypeChip type={move.type} variant="code" />
            </dd>
          </div>
          <div className="lrow">
            <dt className="lrow__label">Category</dt>
            <dd className="lrow__value">
              {move.category ? <CategoryChip category={move.category} variant="full" /> : "—"}
            </dd>
          </div>
          <div className="lrow">
            <dt className="lrow__label">Power</dt>
            <dd className="lrow__value mono">
              {move.power !== null ? move.power : (
                <span className="lrow__empty">—</span>
              )}
            </dd>
          </div>
          <div className="lrow">
            <dt className="lrow__label">Accuracy</dt>
            <dd className="lrow__value mono">
              {move.accuracy !== null ? move.accuracy : (
                <span className="lrow__empty">—</span>
              )}
            </dd>
          </div>
          <div className="lrow">
            <dt className="lrow__label">PP</dt>
            <dd className="lrow__value mono">
              {move.pp !== null ? move.pp : (
                <span className="lrow__empty">—</span>
              )}
            </dd>
          </div>
          <div className="lrow">
            <dt className="lrow__label">Priority</dt>
            <dd className="lrow__value mono">{move.priority}</dd>
          </div>
          <div className="lrow">
            <dt className="lrow__label">Target</dt>
            <dd className="lrow__value move-detail__target">
              {move.target ? (
                <>
                  <TargetGlyph target={move.target} />
                  {targetLabel(move.target)}
                </>
              ) : (
                <span className="lrow__empty">—</span>
              )}
            </dd>
          </div>
        </dl>
      </section>

      {move.flags.length > 0 && (
        <section
          id="move-detail-flags"
          className="editor-section"
          aria-label="Move flags"
        >
          <h3 className="editor-section__heading">Flags</h3>
          <p className="move-detail__flags">{move.flags.map(flagLabel).join(", ")}</p>
        </section>
      )}

      {move.description && (
        <section
          id="move-detail-description"
          className="editor-section"
          aria-label="Description"
        >
          <h3 className="editor-section__heading">Description</h3>
          <p className="move-detail__desc">{move.description}</p>
        </section>
      )}
    </div>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) {
    return value
      .map((item) =>
        typeof item === "object" ? JSON.stringify(item) : String(item),
      )
      .join(", ");
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
