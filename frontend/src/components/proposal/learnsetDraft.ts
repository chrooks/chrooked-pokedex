/* Pure draft logic for the learnset section — no React, unit-tested in the node
   environment. Drives the learnset renderer's autosort, the aligned-by-level
   diff (added / changed / removed), inline edits, and the draft→Override merge. */

import type {
  DexEntry,
  LearnsetDraft,
  LearnsetDraftMove,
  LearnsetMove,
  ProposalAlternative,
  SpeciesOverride,
} from "../../types";

/** Sort proposed rows level-ascending, ties broken by move name so the order is
    stable across edits (no row-jitter on re-sort). */
export function sortMoves(
  moves: readonly LearnsetDraftMove[],
): LearnsetDraftMove[] {
  return [...moves].sort(
    (a, b) => a.level - b.level || a.move.localeCompare(b.move),
  );
}

/** Edit one proposed row's (level, move) by index, then autosort. Returns the
    next draft (immutable). */
export function editRow(
  draft: LearnsetDraft | null,
  index: number,
  patch: { level?: number; move?: string },
): LearnsetDraft {
  const rows = draft?.learnset ?? [];
  const next = rows.map((row, i) =>
    i === index ? { ...row, ...patch } : row,
  );
  return { learnset: sortMoves(next) };
}

/** Drop the proposed row at `index`, then autosort. Index-based (not move-keyed)
    so removing one row of a move that appears at both L0 and a level leaves the
    other intact. */
export function removeRow(
  draft: LearnsetDraft | null,
  index: number,
): LearnsetDraft {
  const rows = draft?.learnset ?? [];
  return { learnset: sortMoves(rows.filter((_, i) => i !== index)) };
}

const LEARNSET_LEVEL_MIN = 0;
const LEARNSET_LEVEL_MAX = 100;

/** Drop every proposed row whose move is in `moves`, then autosort. Used by the
    proposed-learnset bulk "Remove" action (selection is keyed by move name). */
export function removeSelectedMoves(
  draft: LearnsetDraft | null,
  moves: ReadonlySet<string>,
): LearnsetDraft {
  const rows = draft?.learnset ?? [];
  return { learnset: sortMoves(rows.filter((r) => !moves.has(r.move))) };
}

/** Nudge the level of every proposed row whose move is in `moves` by `delta`,
    clamped to [0, 100], then autosort. Keying on the move name (not level) lets a
    selection survive repeated ±1 nudges. */
export function adjustSelectedLevels(
  draft: LearnsetDraft | null,
  moves: ReadonlySet<string>,
  delta: number,
): LearnsetDraft {
  const rows = draft?.learnset ?? [];
  const next = rows.map((r) =>
    moves.has(r.move)
      ? {
          ...r,
          level: Math.min(
            LEARNSET_LEVEL_MAX,
            Math.max(LEARNSET_LEVEL_MIN, r.level + delta),
          ),
        }
      : r,
  );
  return { learnset: sortMoves(next) };
}

/** The cross-product diff status of one proposed row against the current list,
    matched by (level, move) — "added" = not in current, "kept" = present in
    both. ("changed"/"removed" are derived at render: a current row absent from
    the proposal is "removed"; the renderer pairs them by level.) */
export type RowStatus = "added" | "kept";

function moveKey(level: number, move: string): string {
  return `${level}::${move.trim().toLowerCase()}`;
}

/** Classify each proposed row as added (new vs current) or kept. */
export function classifyProposed(
  current: readonly LearnsetMove[],
  proposed: readonly LearnsetDraftMove[],
): { row: LearnsetDraftMove; status: RowStatus }[] {
  const currentKeys = new Set(current.map((m) => moveKey(m.level, m.move)));
  return sortMoves(proposed).map((row) => ({
    row,
    status: currentKeys.has(moveKey(row.level, row.move))
      ? ("kept" as const)
      : ("added" as const),
  }));
}

/** Current rows the proposal dropped (present in current, absent from proposed).
    Sorted level-ascending for the removed-row display. */
export function removedRows(
  current: readonly LearnsetMove[],
  proposed: readonly LearnsetDraftMove[],
): LearnsetMove[] {
  const proposedKeys = new Set(
    proposed.map((m) => moveKey(m.level, m.move)),
  );
  return [...current]
    .filter((m) => !proposedKeys.has(moveKey(m.level, m.move)))
    .sort((a, b) => a.level - b.level || a.move.localeCompare(b.move));
}

/** Whether the whole proposed list differs from current (drives the section's
    "changed" framing). Order-insensitive on the (level, move) set. */
export function learnsetChanged(
  current: readonly LearnsetMove[],
  proposed: readonly LearnsetDraftMove[],
): boolean {
  if (current.length !== proposed.length) return true;
  const currentKeys = new Set(current.map((m) => moveKey(m.level, m.move)));
  return proposed.some((m) => !currentKeys.has(moveKey(m.level, m.move)));
}

/** Swap an alternative into the draft. A learnset alternative is a whole
    proposed list (the model's runner-up learnset). */
export function applyAlternative(
  draft: LearnsetDraft | null,
  alt: ProposalAlternative,
): LearnsetDraft {
  if (Array.isArray(alt.value)) {
    const moves = (alt.value as unknown[])
      .filter(
        (m): m is { level: number; move: string; reasoning?: string } =>
          m !== null &&
          typeof m === "object" &&
          "move" in m &&
          "level" in m,
      )
      .map((m) => ({
        level: Number(m.level),
        move: String(m.move),
        reasoning: m.reasoning,
      }));
    return { learnset: sortMoves(moves) };
  }
  return draft ?? { learnset: [] };
}

/** Merge the curated learnset draft into the raw Override (read-merge-write).
    Learnset is a whole-list Override; only that field is touched. The reasoning
    is stripped — the Override stores only `(level, move)`. */
export function mergeDraft(
  raw: SpeciesOverride,
  draft: LearnsetDraft,
): SpeciesOverride {
  const learnset: LearnsetMove[] = sortMoves(draft.learnset)
    .filter((m) => m.move.trim() !== "")
    .map((m) => ({ level: m.level, move: m.move.trim() }));
  return { ...raw, learnset };
}

/** The current learnset for the current column. */
export function currentLearnset(entry: DexEntry): LearnsetMove[] {
  return entry.learnset;
}
