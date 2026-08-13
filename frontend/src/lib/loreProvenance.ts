/* The lore-provenance readout, as pure text. Turns the `lore` object a suggest
   response carries into the one dim mono line shown under the proposal — what
   the model actually read before it answered.

   Kept out of the component so the honest cases are directly testable: a miss
   must READ as a miss (the case the author most needs to notice), and an `off`
   call must render nothing at all rather than a line implying a lookup ran. */

import type { LoreProvenance } from "../types";

/** The provenance summary line, or null when there is nothing honest to say.

   Returns null for `off` and for a missing object: no lookup ran, so any line
   would be a false Signifier. Source URLs are NOT in the string — the component
   renders them as links beside it. */
export function loreProvenanceLine(lore: LoreProvenance | null | undefined): string | null {
  if (!lore || lore.mode === "off") return null;
  const head = `lore · ${lore.mode}`;
  // A dead network is not the same claim as "this species has no lore".
  if (lore.error) return `${head} · lookup failed`;
  if (lore.found !== true) return `${head} · no lore found`;
  const count = lore.sources?.length ?? 0;
  const chars = (lore.chars ?? 0).toLocaleString("en-US");
  const base = lore.base_species ? ` · base species: ${lore.base_species}` : "";
  return `${head} · ${count} source${count === 1 ? "" : "s"} · ${chars} chars${base}`;
}

/** A short label for a source link — the host, minus the `www.` noise. An
    unparseable value falls back to itself rather than vanishing. */
export function sourceLabel(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
