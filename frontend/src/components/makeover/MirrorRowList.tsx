/* The mirror-down pre-evo list, shared by the LEARNSET stage's whole-line preview
   and the mirror-only MIRROR stage. Each pre-evo carries a mirror/skip toggle so
   the author can exclude a pre-evo from the copy-down (e.g. a pre-evo that should
   keep its own kit). Excluded rows render dimmed and are dropped from the write. */

import type { MirrorRow } from "../../lib/mirrorDown";

interface Props {
  rows: readonly MirrorRow[];
  /** chrooked_ids the author has opted OUT of mirroring to. */
  excluded: ReadonlySet<string>;
  onToggle: (chrookedId: string) => void;
  id?: string;
}

export function MirrorRowList({ rows, excluded, onToggle, id }: Props) {
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
            <span className="mono mk-mirror__count">
              {row.types.join("/")} · {row.learnset.length} moves
              {row.strippedL0.length > 0 && ` · −L0: ${row.strippedL0.join(", ")}`}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
