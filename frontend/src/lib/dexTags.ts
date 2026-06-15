/* The Class filter's data source. `tags.json` is keyed by national dex number
   (string) -> a one-element array holding a lowercase tag. Forms share their
   species' dex number, so a form inherits its species' class for free. Pure. */

import rawTags from "../data/tags.json";

/** The display values the Class filter offers, in order. */
export const CLASS_VALUES = [
  "Legendary",
  "Mythical",
  "Starter",
  "Fossil",
  "Eevee Line",
  "Pseudo-Legendary",
  "Mega",
] as const;

export type ClassValue = (typeof CLASS_VALUES)[number];

const TAG_TO_CLASS: Record<string, ClassValue> = {
  legendary: "Legendary",
  mythical: "Mythical",
  starter: "Starter",
  fossil: "Fossil",
  eevee: "Eevee Line",
  pseudo: "Pseudo-Legendary",
};

const TAGS = rawTags as Record<string, string[]>;

// A Mega form is named "<Species> Mega[ X|Y|Z]". The word boundary keeps base
// species whose name merely contains the letters (Yanmega, Meganium) out — the
// match is case-sensitive on the capital "Mega" token, so lowercase "mega" in a
// slug never trips it.
const MEGA_NAME = /\bMega\b/;

/** True when an entry is a Mega-evolution form (not its base species). Mega is a
    *form* class, so it's keyed on the name, not the national dex number a form
    shares with its base. */
export function isMega(name: string): boolean {
  return MEGA_NAME.test(name);
}

/** The dex-number class of a species (Legendary/Starter/…), or null when it has
    none (or no dex number — e.g. a non-canon species). Form-based classes like
    Mega are not covered here; use {@link classesOf} for the full set. */
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

/** Every class an entry belongs to: its dex-number class (if any) plus Mega when
    the entry is a Mega form. An entry can hold both — Charizard Mega X is a
    Starter (dex 6) and a Mega. */
export function classesOf(entry: { dex: number | null; name: string }): ClassValue[] {
  const classes: ClassValue[] = [];
  const dexClass = classOf(entry.dex);
  if (dexClass !== null) {
    classes.push(dexClass);
  }
  if (isMega(entry.name)) {
    classes.push("Mega");
  }
  return classes;
}
