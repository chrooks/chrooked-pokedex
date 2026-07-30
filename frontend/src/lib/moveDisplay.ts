/* Shared move-name presentation: type tint, STAB bold, best-offense italic.
   One place so the profile learnset (LearnsetSection) and the makeover learnset
   stage (LearnsetStage) render moves identically. */

import type { CSSProperties } from "react";
import { typeSlug } from "./format";

/** Move name (lowercased) → its type + category, for tint / STAB / italic. */
export type MoveMeta = ReadonlyMap<string, { type: string; category: string }>;

/** The mon's stronger attacking side (the italic target): "physical" if Atk beats
    SpA, "special" if SpA beats Atk, null on a tie (no clear side to italicize). */
export function attackCategory(stats: Record<string, number>): "physical" | "special" | null {
  if (stats.atk > stats.spa) return "physical";
  if (stats.spa > stats.atk) return "special";
  return null;
}

/** Presentational props to spread onto a move-name element: the type color via an
    inline `--type` var, plus `data-typed` / `data-stab` / `data-offense` flags the
    CSS keys off. An untyped move (not in the pool) gets `{}` — plain text.
    `stab` is a set of the mon's type slugs; `attack` is its best-offense category. */
export function moveNameProps(
  move: string,
  moveMeta: MoveMeta | undefined,
  stab: ReadonlySet<string>,
  attack: "physical" | "special" | null,
): {
  style?: CSSProperties;
  "data-typed"?: true;
  "data-stab"?: true;
  "data-offense"?: true;
} {
  const meta = moveMeta?.get(move.toLowerCase());
  if (!meta?.type) return {};
  const slug = typeSlug(meta.type);
  return {
    style: { "--type": `var(--type-${slug})` } as CSSProperties,
    "data-typed": true,
    "data-stab": stab.has(slug) || undefined,
    "data-offense": (!!attack && meta.category === attack) || undefined,
  };
}
