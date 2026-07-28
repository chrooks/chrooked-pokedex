/* Mirror-down: the evolution-line copy the final lock performs. The anchor (the
   species being made over) gets its full kit; every pre-evo gets the anchor's
   typing + abilities and the anchor's learnset MINUS its L0 on-evolution rows
   (those are the evolved stage's reward — CLAUDE.md's Evolution-line default and
   ac5). Pure so the whole-line preview and the write plan are unit-tested. Single
   linear lines (the production slice); a branch stops the backward walk. */

import type { AbilitySlots, DexEntry, LearnsetMove } from "../types";

/** The base-form id of a chrooked_id: `joltik--riftform` → `joltik`. Form ids
    carry a `--<form>` suffix; a base form has none, so this is a no-op for it. */
const baseStem = (id: string): string => id.split("--")[0];

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
    // Collapse form variants of one species (`base--form`, e.g. joltik +
    // joltik--riftform) to their shared base stem: multiple such edges are ONE
    // logical pre-evo, not a branch. More than one DISTINCT stem is a genuine
    // multi-species branch (Eevee, Wurmple) — stop the linear walk there.
    const stems = new Set(ps.map(baseStem));
    if (stems.size !== 1) break;
    const stem = [...stems][0];
    if (seen.has(stem)) break;
    // Mirror onto the base form (forms mirror the base's kit), so prefer the
    // base-stem entry; fall back to the only edge if the base isn't in the dex.
    const parent = byId.get(stem) ?? byId.get(ps[0]);
    if (parent === undefined) break;
    chain.push(parent);
    seen.add(parent.chrooked_id);
    seen.add(stem);
    currentId = stem;
  }
  return chain.reverse();
}

/** The evolutions AFTER `anchor`, (anchor+1)→tip, by the same linear-walk rules
    as {@link preEvos}: form-stem collapse, a genuine branch or cycle stops the
    walk. Forward edges are reliable (`evolves_into[].to` is a chrooked_id). */
export function postEvos(
  anchor: DexEntry,
  byId: ReadonlyMap<string, DexEntry>,
): DexEntry[] {
  const chain: DexEntry[] = [];
  const seen = new Set<string>([baseStem(anchor.chrooked_id), anchor.chrooked_id]);
  let current = anchor;
  while (true) {
    const edges = (current.evolves_into ?? []).filter((edge) => edge.to);
    const stems = new Set(edges.map((edge) => baseStem(edge.to)));
    if (stems.size !== 1) break;
    const stem = [...stems][0];
    if (seen.has(stem)) break;
    const child = byId.get(stem) ?? byId.get(edges[0].to);
    if (child === undefined) break;
    chain.push(child);
    seen.add(child.chrooked_id);
    seen.add(stem);
    current = child;
  }
  return chain;
}

/** The whole linear line containing `entry`, base→tip (entry included). The
    mirror wizard's anchor/recipient pool. */
export function lineMembers(
  entry: DexEntry,
  byId: ReadonlyMap<string, DexEntry>,
): DexEntry[] {
  return [...preEvos(entry, byId), entry, ...postEvos(entry, byId)];
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

/** The facets a mirror can copy. Stats is the deliberate exception: the line
    default SCALES stats rather than copying them, so it is opt-in only. */
export type MirrorFacet = "types" | "stats" | "abilities" | "learnset";

export const MIRROR_FACETS: readonly MirrorFacet[] = [
  "types",
  "stats",
  "abilities",
  "learnset",
];

/** The classic mirror-down facets (stats excluded — it scales, not copies). */
export const DEFAULT_MIRROR_FACETS: ReadonlySet<MirrorFacet> = new Set([
  "types",
  "abilities",
  "learnset",
]);

/** What one recipient receives at the write. `strippedL0` lists the L0 moves
    left behind, for the preview's "minus L0" annotation. */
export interface MirrorRow {
  chrooked_id: string;
  name: string;
  dex: number | null;
  types: string[];
  abilities: AbilitySlots;
  stats?: Record<string, number>;
  learnset: LearnsetMove[];
  strippedL0: string[];
}

/** The locked anchor kit that mirrors down to the line. `stats` is only carried
    when the wizard offers the stats facet. */
export interface AnchorKit {
  types: string[];
  abilities: AbilitySlots;
  stats?: Record<string, number>;
  learnset: LearnsetMove[];
}

/** One row per recipient carrying the anchor kit: typing + abilities (+ stats
    when the kit carries them) and the copy-down learnset (anchor minus L0). */
export function mirrorRows(
  kit: AnchorKit,
  recipients: readonly DexEntry[],
): MirrorRow[] {
  const learnset = copyDownLearnset(kit.learnset);
  const strippedL0 = kit.learnset
    .filter((row) => row.level === 0)
    .map((row) => row.move);
  return recipients.map((recipient) => ({
    chrooked_id: recipient.chrooked_id,
    name: recipient.name,
    dex: recipient.dex,
    types: kit.types,
    abilities: kit.abilities,
    stats: kit.stats,
    learnset,
    strippedL0,
  }));
}

/** The whole-line mirror-down preview: one row per pre-evo carrying the anchor's
    kit. Rendered before any write so the author sees the entire line first (ac5). */
export function mirrorDownPreview(
  anchor: DexEntry,
  byId: ReadonlyMap<string, DexEntry>,
  kit: AnchorKit,
): MirrorRow[] {
  return mirrorRows(kit, preEvos(anchor, byId));
}
