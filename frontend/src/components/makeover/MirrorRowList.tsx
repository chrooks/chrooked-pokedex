/* The mirror recipient list, shared by the LEARNSET stage's whole-line preview
   and the MIRROR wizard. Each recipient carries a mirror/skip toggle so the
   author can exclude one from the copy (e.g. a pre-evo that should keep its own
   kit). Excluded rows render dimmed and are dropped from the write. The summary
   line reflects only the facets that will actually write. */

import type { MirrorFacet, MirrorRow } from "../../lib/mirrorDown";
import { bst } from "../../lib/format";

interface Props {
  rows: readonly MirrorRow[];
  /** chrooked_ids the author has opted OUT of mirroring to. */
  excluded: ReadonlySet<string>;
  onToggle: (chrookedId: string) => void;
  /** The facets being mirrored; omitted = the classic types+abilities+learnset. */
  facets?: ReadonlySet<MirrorFacet>;
  id?: string;
}

function summary(row: MirrorRow, facets?: ReadonlySet<MirrorFacet>): string {
  const parts: string[] = [];
  if (!facets || facets.has("types")) parts.push(row.types.join("/"));
  if (facets?.has("stats") && row.stats) parts.push(`${bst(row.stats)} bst`);
  if (!facets || facets.has("learnset")) {
    parts.push(`${row.learnset.length} moves`);
    if (row.strippedL0.length > 0) parts.push(`−L0: ${row.strippedL0.join(", ")}`);
  }
  return parts.join(" · ");
}

export function MirrorRowList({ rows, excluded, onToggle, facets, id }: Props) {
  return (
    <ul className="mk-mirror__list" id={id}>
      {rows.map((row) => {
        const skipped = excluded.has(row.chrooked_id);
        return (
          <li
            key={row.chrooked_id}
            className="mk-mirror__row"
            data-skipped={skipped || undefined}
          >
            <button
              type="button"
              className="mk-mirror__toggle mono"
              role="switch"
              aria-checked={!skipped}
              aria-label={`${skipped ? "Mirror to" : "Skip"} ${row.name}`}
              onClick={() => onToggle(row.chrooked_id)}
            >
              {skipped ? "skip" : "mirror"}
            </button>
            <span className="mk-mirror__name">{row.name}</span>
            <span className="mono mk-mirror__count">{summary(row, facets)}</span>
          </li>
        );
      })}
    </ul>
  );
}
