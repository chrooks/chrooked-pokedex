/* Mirror-down: the evolution-line copy the final lock performs. The anchor (the
   species being made over) gets its full kit; every pre-evo gets the anchor's
   typing + abilities and the anchor's learnset MINUS its L0 on-evolution rows
   (those are the evolved stage's reward — CLAUDE.md's Evolution-line default and
   ac5). Pure so the whole-line preview and the write plan are unit-tested. Single
   linear lines (the production slice); a branch stops the backward walk. */

import type { AbilitySlots, DexEntry, LearnsetMove } from "../types";

/** The pre-evolutions of `anchor`, base→(anchor-1). Resolved from the reliable
    FORWARD graph (`evolves_into[].to` is always a chrooked_id) rather than
    `evolution.from`, which stores a DISPLAY NAME on an override edge (e.g. a
    reworked Venusaur whose `evolution.from` is "Ivysaur", not "ivysaur"). A member
    with a branch (more than one parent) or a cycle ends the walk. */
export function preEvos(
  anchor: DexEntry,
  byId: ReadonlyMap<string, DexEntry>,
): DexEntry[] {
  // Parent adjacency from forward edges across the whole dex.
  const parents = new Map<string, string[]>();
  for (const entry of byId.values()) {
    for (const edge of entry.evolves_into ?? []) {
      if (!edge.to) continue;
      const list = parents.get(edge.to) ?? [];
      list.push(entry.chrooked_id);
      parents.set(edge.to, list);
    }
  }

  const chain: DexEntry[] = [];
  const seen = new Set<string>([anchor.chrooked_id]);
  let currentId = anchor.chrooked_id;
  while (true) {
    const ps = parents.get(currentId) ?? [];
    if (ps.length !== 1 || seen.has(ps[0])) break;
    const parent = byId.get(ps[0]);
    if (parent === undefined) break;
    chain.push(parent);
    seen.add(parent.chrooked_id);
    currentId = parent.chrooked_id;
  }
  return chain.reverse();
}

/** The learnset a pre-evo inherits: the anchor's rows with every L0 row dropped
    (the L0 on-evolution reward stays on the evolved stage only). Levels are
    otherwise untouched; sorted level-ascending for a stable preview/write. */
export function copyDownLearnset(anchorLearnset: readonly LearnsetMove[]): LearnsetMove[] {
  return anchorLearnset
    .filter((row) => row.level !== 0)
    .map((row) => ({ level: row.level, move: row.move }))
    .sort((a, b) => a.level - b.level || a.move.localeCompare(b.move));
}

/** What one pre-evo receives at the final lock. `strippedL0` lists the L0 moves
    left behind, for the preview's "minus L0" annotation. */
export interface MirrorRow {
  chrooked_id: string;
  name: string;
  dex: number | null;
  types: string[];
  abilities: AbilitySlots;
  learnset: LearnsetMove[];
  strippedL0: string[];
}

/** The locked anchor kit that mirrors down to the line. */
export interface AnchorKit {
  types: string[];
  abilities: AbilitySlots;
  learnset: LearnsetMove[];
}

/** The whole-line mirror-down preview: one row per pre-evo carrying the anchor's
    typing + abilities and the copy-down learnset (anchor minus L0). Rendered
    before any write so the author sees the entire line first (ac5). */
export function mirrorDownPreview(
  anchor: DexEntry,
  byId: ReadonlyMap<string, DexEntry>,
  kit: AnchorKit,
): MirrorRow[] {
  const learnset = copyDownLearnset(kit.learnset);
  const strippedL0 = kit.learnset
    .filter((row) => row.level === 0)
    .map((row) => row.move);
  return preEvos(anchor, byId).map((pre) => ({
    chrooked_id: pre.chrooked_id,
    name: pre.name,
    dex: pre.dex,
    types: kit.types,
    abilities: kit.abilities,
    learnset,
    strippedL0,
  }));
}
