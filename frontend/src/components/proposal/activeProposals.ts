/* The ledger AUTO-EXPANDS when any section has an active proposal (ac8 / P1).
   Each ProposedColumn reports its active/idle state by section id; the ledger
   keeps the set of currently-active ids and widens when it is non-empty. The
   set logic is pure so the "panel is wide when a proposal is active" invariant
   is provable without a DOM (mirrors the project's pure-logic test convention).

   A section is "active" once it leaves idle (input / loading / proposed /
   applying / error) and goes idle again on reset (Discard) or after the
   applied → Done reset. */

/** Add or remove a section id from the active set, returning a NEW set (no
    mutation). Idempotent: re-adding an active id, or removing an absent id, is
    a no-op that still returns a fresh set. */
export function updateActiveSet(
  current: ReadonlySet<string>,
  sectionId: string,
  isActive: boolean,
): Set<string> {
  const next = new Set(current);
  if (isActive) {
    next.add(sectionId);
  } else {
    next.delete(sectionId);
  }
  return next;
}

/** The ledger should widen when at least one section has an active proposal AND
    the author has not manually collapsed it. Manual collapse always wins so the
    control is honest (the author can reclaim the narrow layout mid-proposal). */
export function shouldExpandLedger(
  activeIds: ReadonlySet<string>,
  manuallyCollapsed: boolean,
): boolean {
  return activeIds.size > 0 && !manuallyCollapsed;
}
