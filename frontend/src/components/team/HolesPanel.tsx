import type { Hole } from "../../lib/teamFit";
import { multGlyph } from "../../lib/teamMatchups";
import { TypeChip } from "../TypeChip";

type Props = {
  holes: readonly Hole[];
  /** Party-order member names, so a ×4 row can say who takes it. */
  memberNames: readonly string[];
};

const HIGHLIGHT_MS = 1200;

/** Scroll the defense grid to a type's row and flash it, so a hole read in
    words is one click from its cells. */
function focusGridRow(type: string) {
  const tr = document.querySelector<HTMLElement>(`#team-defense tr[data-type="${CSS.escape(type)}"]`);
  if (!tr) return;
  tr.scrollIntoView({ block: "nearest", behavior: "smooth" });
  tr.dataset.flash = "true";
  window.setTimeout(() => delete tr.dataset.flash, HIGHLIGHT_MS);
}

/**
 * The defense grid in words (#118): every attacking type the team is weak to,
 * unbalanced rows first. Reading "Ghost ×2 — unbalanced" is faster than
 * scanning 18 rows for the lit Weak total, and each row jumps to its grid row.
 */
export function HolesPanel({ holes, memberNames }: Props) {
  // Unbalanced rows and ×4 hits get a full line; a weakness the team already
  // answers collapses into one chip so the panel stays short and the grid
  // stays above the fold. Every weak row is still listed and clickable.
  const urgent = holes.filter((hole) => hole.isUnbalanced || hole.worst >= 4);
  const covered = holes.filter((hole) => !hole.isUnbalanced && hole.worst < 4);
  return (
    <section className="holes" id="team-holes" aria-labelledby="team-holes-title">
      <h3 className="holes__title" id="team-holes-title">
        Holes
      </h3>
      {holes.length === 0 ? (
        <p className="holes__empty">No weaknesses on this team.</p>
      ) : (
        <ul className="holes__list">
          {urgent.map((hole) => (
            <li key={hole.type}>
              <button
                type="button"
                className="holes__row"
                data-type={hole.type}
                data-unbalanced={hole.isUnbalanced}
                title={`Show ${hole.type} in the defense grid`}
                onClick={() => focusGridRow(hole.type)}
              >
                <TypeChip type={hole.type} variant="code" />
                <span className="holes__count mono">×{hole.weak}</span>
                {hole.isUnbalanced && <span className="holes__badge">unbalanced</span>}
                <span className="holes__detail">
                  {hole.weak} weak, {hole.answers} {hole.answers === 1 ? "answer" : "answers"}
                  {hole.worst >= 4 &&
                    ` · ${multGlyph(hole.worst)}× on ${memberNames[hole.worstIndex] ?? "?"}`}
                </span>
              </button>
            </li>
          ))}
          {covered.length > 0 && (
            <li className="holes__covered">
              <span className="holes__covered-label">Covered</span>
              {covered.map((hole) => (
                <button
                  key={hole.type}
                  type="button"
                  className="holes__chip"
                  data-type={hole.type}
                  title={`${hole.type}: ${hole.weak} weak, ${hole.answers} ${hole.answers === 1 ? "answer" : "answers"} — show in the defense grid`}
                  onClick={() => focusGridRow(hole.type)}
                >
                  <TypeChip type={hole.type} variant="code" />
                </button>
              ))}
            </li>
          )}
        </ul>
      )}
    </section>
  );
}
