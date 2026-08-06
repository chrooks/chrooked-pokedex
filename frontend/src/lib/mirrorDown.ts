/* Mirror-down: the evolution-line copy the final lock performs. The anchor (the
   species being made over) gets its full kit; every pre-evo gets the anchor's
   typing + abilities and the anchor's learnset MINUS its L0 on-evolution rows
   (those are the evolved stage's reward — CLAUDE.md's Evolution-line default and
   ac5). Stats are the exception the same default carves out: they SCALE to each
   recipient's own canon BST instead of copying, so a pre-evo takes the anchor's
   role without its raw power. Pure so the whole-line preview and the write plan
   are unit-tested. Single
   linear lines (the production slice); a branch stops the backward walk. */

import type { AbilitySlots, DexEntry, LearnsetMove } from "../types";
import { STAT_ORDER } from "./format";

type Stats = Record<string, number>;

const MAX_STAT = 255;

const total = (stats: Stats): number =>
  STAT_ORDER.reduce((sum, key) => sum + (stats[key] ?? 0), 0);

/** A species' PRE-makeover spread. `base.stats` carries the canon values only
    when the Ruleset overrode stats; with no override the entry's own spread is
    already canon. The scale-down measures deltas against this, so re-running a
    mirror is idempotent instead of compounding. */
export function canonStats(entry: DexEntry): Stats {
  return entry.base?.stats ?? entry.stats;
}

/** The pre-evo spread the line default prescribes: `canon` grown by the same BST
    `delta` the anchor took, redistributed in `shape`'s proportions so the whole
    line reads as one role and the anchor's dump stat stays the dump stat
    (CLAUDE.md, Evolution-line default step 3).

    Every stat is FLOORED at canon — a pre-evo is being upgraded, so none of it
    should come out worse than it started. Without the floor a slow bulky final
    evo drags its pre-evo's speed under (Barboach 60 → 20). Stats that would sink
    are pinned at canon and the rest of the budget re-spreads over what's left,
    repeatedly, until nothing else sinks. Mirrors `scripts/preevo_stats.py::scale`
    — keep the two in step. */
export function scaleStats(canon: Stats, delta: number, shape: Stats): Stats {
  const target = total(canon) + delta;
  if (total(shape) === 0 || target <= total(canon)) return { ...canon };

  let free: string[] = [...STAT_ORDER];
  const pinned = new Map<string, number>();
  let alloc: Stats = {};
  while (free.length > 0) {
    const budget =
      target - [...pinned.values()].reduce((sum, value) => sum + value, 0);
    const weight = free.reduce((sum, key) => sum + (shape[key] ?? 0), 0);
    if (weight <= 0) break;
    alloc = Object.fromEntries(
      free.map((key) => [key, (budget * (shape[key] ?? 0)) / weight]),
    );
    const sinking = free.filter((key) => alloc[key] < canon[key]);
    if (sinking.length === 0) break;
    for (const key of sinking) pinned.set(key, canon[key]);
    free = free.filter((key) => !pinned.has(key));
  }

  const scaled: Stats = Object.fromEntries(
    STAT_ORDER.map((key) => [key, canon[key]]),
  );
  for (const key of free) {
    scaled[key] = Math.min(MAX_STAT, Math.max(canon[key], Math.round(alloc[key])));
  }

  // Rounding drift rides on stats that still have room above their own floor.
  const order = (free.length > 0 ? free : [...STAT_ORDER])
    .slice()
    .sort((a, b) => scaled[b] - scaled[a]);
  let drift = target - total(scaled);
  for (let i = 0; drift !== 0 && i < order.length * MAX_STAT; i += 1) {
    const key = order[i % order.length];
    if (drift > 0 && scaled[key] < MAX_STAT) {
      scaled[key] += 1;
      drift -= 1;
    } else if (drift < 0 && scaled[key] > canon[key]) {
      scaled[key] -= 1;
      drift += 1;
    }
  }
  return scaled;
}

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
    // A single distinct parent is taken VERBATIM — a form line stays on its
    // form (Goodra Hisui's parent is sliggoo--hisuianform, never sliggoo).
    // Only when several form-variants of one stem all feed this child do they
    // collapse to the base-stem entry (one logical pre-evo, mirrored onto the
    // base); fall back to the first edge if the base isn't in the dex.
    const distinct = new Set(ps);
    const parent =
      distinct.size === 1
        ? byId.get(ps[0])
        : (byId.get(stem) ?? byId.get(ps[0]));
    if (parent === undefined) break;
    chain.push(parent);
    seen.add(parent.chrooked_id);
    seen.add(stem);
    currentId = parent.chrooked_id;
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
    // Same verbatim-vs-collapse rule as preEvos: one distinct target keeps its
    // form (sliggoo--hisuianform evolves into goodra--hisuianform, not goodra).
    const targets = new Set(edges.map((edge) => edge.to));
    const child =
      targets.size === 1
        ? byId.get(edges[0].to)
        : (byId.get(stem) ?? byId.get(edges[0].to));
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

/** True when `member` also evolves into a species OUTSIDE `lineIds` — a
    branch-shared pre-evo (Goomy feeds both Sliggoo forms). Mirroring the
    anchor's kit onto one would desync it from its OTHER line, and the next
    makeover over there would clobber it back — so shared members start
    skipped in the mirror list and the author opts in per makeover. */
export function sharedOutsideLine(
  member: DexEntry,
  lineIds: ReadonlySet<string>,
): boolean {
  return (member.evolves_into ?? []).some(
    (edge) => edge.to && !lineIds.has(edge.to),
  );
}

/** The facets a mirror can copy. Stats is the odd one out: typing, abilities and
    the learnset are copied verbatim, stats are SCALED per recipient (see
    {@link scaleStats}) because a pre-evo keeps its own weight class. */
export type MirrorFacet = "types" | "stats" | "abilities" | "learnset";

export const MIRROR_FACETS: readonly MirrorFacet[] = [
  "types",
  "stats",
  "abilities",
  "learnset",
];

/** All four facets — the full Evolution-line default, stats included. */
export const DEFAULT_MIRROR_FACETS: ReadonlySet<MirrorFacet> = new Set(
  MIRROR_FACETS,
);

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

/** The locked anchor kit that mirrors down to the line. `stats` is the anchor's
    CURRENT spread; `baseStats` is its canon one, and the gap between them is the
    BST delta every recipient inherits. Omit `baseStats` and the anchor reads as
    unchanged, so recipients keep their own totals and only take its shape. */
export interface AnchorKit {
  types: string[];
  abilities: AbilitySlots;
  stats?: Stats;
  baseStats?: Stats;
  learnset: LearnsetMove[];
}

/** One row per recipient: the anchor's typing + abilities verbatim, its learnset
    minus L0, and — when the kit carries stats — a spread SCALED to that
    recipient's own canon BST rather than copied. */
export function mirrorRows(
  kit: AnchorKit,
  recipients: readonly DexEntry[],
): MirrorRow[] {
  const learnset = copyDownLearnset(kit.learnset);
  const strippedL0 = kit.learnset
    .filter((row) => row.level === 0)
    .map((row) => row.move);
  const shape = kit.stats;
  const delta = shape ? total(shape) - total(kit.baseStats ?? shape) : 0;
  return recipients.map((recipient) => ({
    chrooked_id: recipient.chrooked_id,
    name: recipient.name,
    dex: recipient.dex,
    types: kit.types,
    abilities: kit.abilities,
    stats: shape
      ? scaleStats(canonStats(recipient), delta, shape)
      : undefined,
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
