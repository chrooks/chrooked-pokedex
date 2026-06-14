/* The Class filter's data source. `tags.json` is keyed by national dex number
   (string) -> a one-element array holding a lowercase tag. Forms share their
   species' dex number, so a form inherits its species' class for free. Pure. */

import rawTags from "../data/tags.json";

/** The display values the Class filter offers, in order. */
export const CLASS_VALUES = ["Legendary", "Mythical", "Starter"] as const;

export type ClassValue = (typeof CLASS_VALUES)[number];

const TAG_TO_CLASS: Record<string, ClassValue> = {
  legendary: "Legendary",
  mythical: "Mythical",
  starter: "Starter",
};

const TAGS = rawTags as Record<string, string[]>;

/** The class of a species by national dex number, or null when it has none
    (or no dex number — e.g. a non-canon species). */
export function classOf(dex: number | null): ClassValue | null {
  if (dex === null) {
    return null;
  }
  const tags = TAGS[String(dex)];
  if (!tags || tags.length === 0) {
    return null;
  }
  return TAG_TO_CLASS[tags[0]] ?? null;
}
