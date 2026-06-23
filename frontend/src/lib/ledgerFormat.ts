/* Pure formatting helpers for the Change Ledger view — kept out of the component
   so they can be unit-tested without a render harness. */

/** Render a ledger field value compactly: ∅ for empty, joined list, or string. */
export function renderLedgerValue(value: unknown): string {
  if (value === null || value === undefined) return "∅";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** "base" or "target" — the class of a ledger entry's scope string. */
export function scopeKind(scope: string): "base" | "target" {
  return scope.startsWith("target:") ? "target" : "base";
}

/** Compact an ISO timestamp: drop the "T", fractional seconds, and tz marker. */
export function formatLedgerTs(ts: string): string {
  return ts.replace("T", " ").replace(/\.\d+/, "").replace(/(\+00:00|Z)$/, "");
}
