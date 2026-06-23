/* Pure formatting helpers for the Change Ledger view — kept out of the component
   so they can be unit-tested without a render harness. */

/** Render a ledger field value readably: ∅ for empty, and a recursive,
    shape-aware render for arrays and objects (so a learnset doesn't come out as
    "[object Object], [object Object], …"). */
export function renderLedgerValue(value: unknown): string {
  if (value === null || value === undefined) return "∅";
  if (Array.isArray(value)) {
    if (value.length === 0) return "∅";
    return value.map(renderLedgerValue).join(", ");
  }
  if (typeof value === "object") {
    const o = value as Record<string, unknown>;
    // A learnset move: { level, move } → "L5 Ice Beam".
    if ("move" in o && "level" in o) return `L${o.level} ${o.move}`;
    // A type-chart cell: { attacker, defender, multiplier } → "Ice→Dragon ×2".
    if ("attacker" in o && "defender" in o) {
      return `${o.attacker}→${o.defender} ×${o.multiplier}`;
    }
    // Generic object (e.g. ability slots): "primary: Thick Fat, hidden: Ice Body".
    const parts = Object.entries(o)
      .filter(([, v]) => v !== null && v !== undefined)
      .map(([k, v]) => `${k}: ${renderLedgerValue(v)}`);
    return parts.length ? parts.join(", ") : "∅";
  }
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
