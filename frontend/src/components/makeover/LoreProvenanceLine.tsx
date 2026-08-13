/* What the last proposal was actually built from: one dim mono line under the
   result, plus the source URLs as links so the author can go read them. Renders
   nothing when no lookup ran (an `off` call) — a line there would claim work the
   app never did. A miss renders LOUDLY as "no lore found", because that is
   exactly the case worth noticing: it means the rationale is reasoning from the
   data alone. The text rule itself lives in lib/loreProvenance.ts. */

import type { LoreProvenance } from "../../types";
import { loreProvenanceLine, sourceLabel } from "../../lib/loreProvenance";

interface Props {
  lore: LoreProvenance | null | undefined;
  /** Human-communicatable element id, e.g. "mk-abilities-lore-prov". */
  id: string;
}

export function LoreProvenanceLine({ lore, id }: Props) {
  const line = loreProvenanceLine(lore);
  if (line === null) return null;
  const sources = lore?.found === true ? (lore.sources ?? []) : [];
  return (
    <p className="mk-lore-prov mono" id={id}>
      <span className="mk-lore-prov__line">{line}</span>
      {sources.map((url) => (
        <a
          key={url}
          className="mk-lore-prov__source"
          href={url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {sourceLabel(url)}
        </a>
      ))}
    </p>
  );
}
