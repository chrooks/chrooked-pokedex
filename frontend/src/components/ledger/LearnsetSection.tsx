import type { LearnsetMove } from "../../types";
import type { NavHandler } from "../DetailLedger";
import { typeSlug } from "../../lib/format";
import { moveNameProps, type MoveMeta } from "../../lib/moveDisplay";
import { MoveHover } from "../EntityHover";
import "./ledger-rows.css";

type Props = {
  now: LearnsetMove[];
  was?: LearnsetMove[];
  showDiff: boolean;
  /** When present (read-only mode), each move name links to its detail (#28). */
  onNavigate?: NavHandler;
  /** Move name (lowercased) → type + category, for type color / STAB / italic. */
  moveMeta?: MoveMeta;
  /** The species' own types — a move matching one is STAB and renders bold. */
  speciesTypes?: readonly string[];
  /** The mon's attacking category — matching moves render italic (its best offense). */
  attackCategory?: "physical" | "special" | null;
  /** Drop the own `<section>` + heading and render only the list body. The
      proposal shell owns the single section heading; this avoids a duplicate. */
  bare?: boolean;
};

/** The level-up learnset. It is a whole-list override, so the diff can't read
    field-by-field; instead it states plainly that the Ruleset replaced the base
    list, with the before/after counts. New moves (absent from base) are marked. */
export function LearnsetSection({
  now,
  was,
  showDiff,
  onNavigate,
  moveMeta,
  speciesTypes,
  attackCategory,
  bare = false,
}: Props) {
  const replaced = was !== undefined;
  const baseMoves = new Set((was ?? []).map((m) => m.move.toLowerCase()));
  const stab = new Set((speciesTypes ?? []).map(typeSlug));

  const body = (
    <>
      {replaced && (
        <span className="ledger__note mono" data-on={showDiff}>
          replaced · {was?.length ?? 0} → {now.length}
        </span>
      )}
      {now.length === 0 ? (
        <p className="lrow__empty">No level-up moves.</p>
      ) : (
        <ol className="ledger__learnset">
          {now.map((entry, index) => {
            const isNew = replaced && !baseMoves.has(entry.move.toLowerCase());
            const nameProps = moveNameProps(entry.move, moveMeta, stab, attackCategory ?? null);
            const isStab = nameProps["data-stab"] === true;
            return (
              <li
                key={`${entry.level}-${entry.move}-${index}`}
                className="ledger__move"
                data-new={showDiff && isNew}
              >
                <span className="ledger__move-lv mono">
                  {entry.level === 0 ? "—" : `L${entry.level}`}
                </span>
                <MoveHover name={entry.move}>
                  {onNavigate ? (
                    <button
                      type="button"
                      id={`ledger-move-link-${index}`}
                      className="lrow__link ledger__move-name"
                      {...nameProps}
                      aria-label={`Open ${entry.move}${isStab ? " (STAB)" : ""}`}
                      onClick={() => onNavigate("moves", entry.move)}
                    >
                      {entry.move}
                    </button>
                  ) : (
                    <span className="ledger__move-name" {...nameProps}>
                      {entry.move}
                    </span>
                  )}
                </MoveHover>
                {showDiff && isNew && (
                  <span className="ledger__move-new mono">new</span>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </>
  );

  if (bare) return body;

  return (
    <section className="ledger__section" aria-label="Learnset">
      <div className="ledger__heading-row">
        <h3 className="ledger__heading">Learnset</h3>
      </div>
      {body}
    </section>
  );
}
