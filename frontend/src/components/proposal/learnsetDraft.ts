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

/** Append a (level, move) row, then autosort. Immutable; skips an exact
    (level, move) duplicate so re-adding the same row is a no-op. Mirrors
    removeRow — the pure half of the learnset stage's add-row control. */
export function addRow(
  draft: LearnsetDraft | null,
  row: { level: number; move: string },
): LearnsetDraft {
  const rows = draft?.learnset ?? [];
  const exists = rows.some(
    (r) => r.level === row.level && r.move.trim().toLowerCase() === row.move.trim().toLowerCase(),
  );
  if (exists || row.move.trim() === "") return { learnset: sortMoves(rows) };
  return { learnset: sortMoves([...rows, { level: row.level, move: row.move.trim() }]) };
}

/** Parse a free-text learnset alternative into a (level, move) row. The suggest
    Seam emits alternatives as strings like "Aqua Jet @ L24 — priority STAB
    option" (backend schema forces a string value), so a click can't swap a whole
    list — it adds the suggested move. Pass `moveOptions` to pin the move name to a
    real pool entry (the longest known name found in the text); falls back to the
    text before the first separator. Level pulled from an `@`/`L`/`level` marker,
    else the first bare number, else 0. Returns null when no move name is found. */
export function parseAltRow(
  text: string,
  moveOptions?: readonly string[],
): { level: number; move: string } | null {
  const marked = text.match(/(?:@|\bl|\blevel|\blvl)\s*(\d{1,3})/i);
  const bare = text.match(/\b(\d{1,3})\b/);
  const level = marked ? Number(marked[1]) : bare ? Number(bare[1]) : 0;

  let move: string | null = null;
  if (moveOptions && moveOptions.length > 0) {
    const lower = text.toLowerCase();
    const hits = moveOptions.filter((name) => lower.includes(name.toLowerCase()));
    move = hits.sort((a, b) => b.length - a.length)[0] ?? null;
  }
  if (move === null) {
    const head = text.split(/[@:—–-]/)[0]?.trim() ?? "";
    move = head || null;
  }
  if (move === null) return null;
  return { level: Math.min(LEARNSET_LEVEL_MAX, Math.max(LEARNSET_LEVEL_MIN, level)), move };
}

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

/** Apply an alternative into the draft, returning a NEW draft the UI re-derives
    from. Two shapes:
    - an array value (a whole runner-up learnset) replaces the list, sorted;
    - a string value (the shape the suggest Seam actually emits — a single
      suggested move like "Aqua Jet @ L24") is parsed and ADDED as a row.
    Falls back to the unchanged draft only when a string can't be parsed. */
export function applyAlternative(
  draft: LearnsetDraft | null,
  alt: ProposalAlternative,
  moveOptions?: readonly string[],
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
  if (typeof alt.value === "string") {
    const parsed = parseAltRow(alt.value, moveOptions);
    if (parsed !== null) return addRow(draft, parsed);
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
