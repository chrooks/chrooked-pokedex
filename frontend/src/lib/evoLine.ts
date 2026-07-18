import type { DexEntry } from "../types";

/**
 * Expand each match to its whole evolution line, walking both directions from
 * the already-present `evolution.from` / `evolves_into` edges. Returns entries
 * in `all` order so dex ordering survives.
 */
export function expandEvoLines(matches: DexEntry[], all: DexEntry[]): DexEntry[] {
  const byId = new Map(all.map((entry) => [entry.chrooked_id, entry]));
  const keep = new Set<string>();

  function walk(entry: DexEntry): void {
    if (keep.has(entry.chrooked_id)) return;
    keep.add(entry.chrooked_id);
    const parent = entry.evolution?.from ? byId.get(entry.evolution.from) : undefined;
    if (parent) walk(parent);
    for (const edge of entry.evolves_into ?? []) {
      const child = byId.get(edge.to);
      if (child) walk(child);
    }
  }

  for (const match of matches) walk(match);
  return all.filter((entry) => keep.has(entry.chrooked_id));
}
