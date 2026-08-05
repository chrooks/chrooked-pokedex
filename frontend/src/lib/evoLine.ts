import type { DexEntry } from "../types";

/**
 * Expand each match to its whole evolution line, walking both directions from
 * the already-present `evolution.from` / `evolves_into` edges. Returns entries
 * in `all` order so dex ordering survives.
 */
export function expandEvoLines(matches: DexEntry[], all: DexEntry[]): DexEntry[] {
  const byId = new Map(all.map((entry) => [entry.chrooked_id, entry]));
  // A Ruleset-override evolution stores its pre-evo as the display NAME
  // ("Rufflet"), while a base evolution stores the chrooked_id ("rufflet").
  // Resolve either — without the name fallback, every override-evolution line
  // silently dropped its pre-evo from the whole-evo-line expansion.
  const byName = new Map(all.map((entry) => [entry.name, entry]));
  const keep = new Set<string>();

  function walk(entry: DexEntry): void {
    if (keep.has(entry.chrooked_id)) return;
    keep.add(entry.chrooked_id);
    const from = entry.evolution?.from;
    const parent = from ? byId.get(from) ?? byName.get(from) : undefined;
    if (parent) walk(parent);
    for (const edge of entry.evolves_into ?? []) {
      const child = byId.get(edge.to);
      if (child) walk(child);
    }
  }

  for (const match of matches) walk(match);
  return all.filter((entry) => keep.has(entry.chrooked_id));
}

/**
 * One species' whole evolution family — every transitive pre-evo and evo (both
 * `evolves_into` forward and `evolution.from` backward), the species itself
 * included, deduped, in `byId` insertion order. A thin wrapper over
 * {@link expandEvoLines} for callers that hold a `byId` Map (the distribute
 * panels' "＋ line" control).
 */
export function evoLine(
  entry: DexEntry,
  byId: ReadonlyMap<string, DexEntry>,
): DexEntry[] {
  return expandEvoLines([entry], [...byId.values()]);
}
