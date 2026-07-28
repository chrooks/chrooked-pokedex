import { typeSlug } from "../../lib/format";
import {
  cellTooltip,
  isUnbalanced,
  multBucket,
  multGlyph,
  type DefenseRow,
  type OffenseRow,
} from "../../lib/teamMatchups";
import type { DexEntry } from "../../types";
import { DexSprite } from "../DexSprite";
import { TypeChip } from "../TypeChip";

type Column = { entry: DexEntry };

type Props = {
  id: string;
  variant: "defense" | "offense";
  title: string;
  /** Short caption under the title, e.g. what a bright cell means. */
  subtitle: string;
  columns: Column[];
  rows: DefenseRow[] | OffenseRow[];
  backdropTargetId: string | null;
};

type TotalSpec = { key: string; label: string; get: (row: DefenseRow & OffenseRow) => number };

const DEFENSE_TOTALS: TotalSpec[] = [
  { key: "weak", label: "Weak", get: (row) => row.weak },
  { key: "resist", label: "Resist", get: (row) => row.resist },
  { key: "immune", label: "Immune", get: (row) => row.immune },
];

const OFFENSE_TOTALS: TotalSpec[] = [
  { key: "super", label: "Super", get: (row) => row.strong },
  { key: "resist", label: "Resist", get: (row) => row.resist },
];

/**
 * The shared matchup grid, faithful to tectonic-tools' team-builder tables.
 * Rows are types (attacking types for defense, defending types for offense);
 * one column per party member headed by its sprite + type chips; per-cell the
 * combined dual-type × ability multiplier in tectonic's color/glyph language;
 * trailing count columns that blank at zero.
 */
export function MatchupTable({ id, variant, title, subtitle, columns, rows, backdropTargetId }: Props) {
  const totals = variant === "defense" ? DEFENSE_TOTALS : OFFENSE_TOTALS;
  const axisCaption = variant === "defense" ? "Attacking type" : "Defending type";

  return (
    <section className="matchup" id={id} aria-labelledby={`${id}-title`}>
      <header className="matchup__head">
        <h3 className="matchup__title" id={`${id}-title`}>
          {title}
        </h3>
        <p className="matchup__subtitle">{subtitle}</p>
      </header>

      <div className="matchup__scroll" role="region" aria-labelledby={`${id}-title`} tabIndex={0}>
        <table className="matchup__table">
          <thead>
            <tr>
              <th className="matchup__corner" scope="col">
                <span className="matchup__corner-label">{axisCaption}</span>
              </th>
              {columns.map(({ entry }, index) => (
                <th className="matchup__memberhead" scope="col" key={`${entry.chrooked_id}-${index}`}>
                  <DexSprite
                    chrookedId={entry.chrooked_id}
                    dex={entry.dex}
                    name={entry.name}
                    backdropTargetId={backdropTargetId}
                    size={44}
                  />
                  <span className="matchup__memberhead-name" title={entry.name}>
                    {entry.name}
                  </span>
                  <span className="matchup__memberhead-types">
                    {entry.types.map((type) => (
                      <TypeChip key={type} type={type} variant="code" />
                    ))}
                  </span>
                </th>
              ))}
              {totals.map((total) => (
                <th className="matchup__totalhead" scope="col" key={total.key} data-kind={total.key}>
                  {total.label}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {rows.map((row) => (
              <tr
                key={row.type}
                className="matchup__row"
                style={{ "--type": `var(--type-${typeSlug(row.type)}, var(--text-dim))` } as React.CSSProperties}
              >
                <th scope="row" className="matchup__rowhead">
                  <span className="matchup__rowhead-badge">{row.type}</span>
                </th>
                {row.cells.map((mult, memberIndex) => {
                  const memberName = columns[memberIndex]?.entry.name ?? "";
                  const atkLabel = variant === "defense" ? row.type : memberName;
                  const defLabel = variant === "defense" ? memberName : row.type;
                  return (
                    <MatchupCell
                      key={memberIndex}
                      mult={mult}
                      atkLabel={atkLabel}
                      defLabel={defLabel}
                    />
                  );
                })}
                {totals.map((total) => {
                  const value = total.get(row as DefenseRow & OffenseRow);
                  // Unbalanced-weakness emphasis (defense Weak column only):
                  // lights up when weaknesses outnumber the team's answers.
                  const unbalanced =
                    variant === "defense" &&
                    total.key === "weak" &&
                    isUnbalanced(row as DefenseRow);
                  const defRow = row as DefenseRow;
                  return (
                    <td
                      className="matchup__total"
                      key={total.key}
                      data-kind={total.key}
                      data-empty={value === 0}
                      data-unbalanced={unbalanced || undefined}
                      title={
                        unbalanced
                          ? `${defRow.weak} weak vs ${defRow.resist + defRow.immune} answers — unbalanced`
                          : undefined
                      }
                    >
                      {value > 0 ? value : ""}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

type CellProps = {
  mult: number | null;
  atkLabel: string;
  defLabel: string;
};

function MatchupCell({ mult, atkLabel, defLabel }: CellProps) {
  if (mult === null) {
    return (
      <td
        className="matchup__cell matchup__cell--nodata"
        aria-label={`${atkLabel} vs ${defLabel}: no data`}
      />
    );
  }
  const bucket = multBucket(mult);
  const glyph = multGlyph(mult);
  const title = cellTooltip(atkLabel, defLabel, mult);
  return (
    <td
      className="matchup__cell"
      data-bucket={bucket}
      data-neutral={mult === 1}
      data-mult={mult}
      title={title}
      aria-label={title}
    >
      <span className="matchup__cell-glyph" aria-hidden="true">
        {glyph}
      </span>
    </td>
  );
}
