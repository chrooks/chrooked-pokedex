/* A read-only ENGINE · VERSION mono readout for a registered Target.

   Fetches /api/targets/{id}/dialect once on mount and renders a two-part label:
   - engine segment in --text-dim (always shown)
   - version segment in --text (when a dialect label is available)

   States:
   - loading  → dim skeleton e.g. "ESSENTIALS · ⋯" (no spinner)
   - detected → "ESSENTIALS · 16.2" or "POKEEMERALD"
   - essentials + dialect null → muted "ESSENTIALS · UNKNOWN" (--text-dim)
   - pokeemerald → engine segment only, no version shown

   The outer span is non-focusable (aria-hidden, tabIndex omitted) — it is a
   read-only Signifier, never a control. */

import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import type { EngineKey } from "../../types";

const ENGINE_DISPLAY: Record<EngineKey, string> = {
  pokeemerald: "POKEEMERALD",
  essentials: "ESSENTIALS",
  rejuv: "REJUVENATION",
};

type Props = {
  id: string;
  engine: EngineKey;
  /** Optional extra className on the wrapping span. */
  className?: string;
};

export function EngineVersionReadout({ id, engine, className }: Props) {
  const [label, setLabel] = useState<string | null | "loading">("loading");

  const engineDisplay = ENGINE_DISPLAY[engine] ?? engine.toUpperCase();
  const isEssentials = engine === "essentials";

  const fetcher = useCallback(
    (signal: AbortSignal) => api.targetDialect(id, signal),
    [id],
  );

  useEffect(() => {
    const controller = new AbortController();
    fetcher(controller.signal)
      .then((dialect) => {
        if (!controller.signal.aborted) {
          setLabel(dialect.label);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          // On fetch error fall back to null (renders as UNKNOWN for essentials)
          setLabel(null);
        }
      });
    return () => controller.abort();
  }, [fetcher]);

  // pokeemerald: engine label only, no version segment
  if (!isEssentials) {
    return (
      <span
        className={className}
        aria-hidden="true"
        style={{ color: "var(--text-dim)", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}
      >
        {engineDisplay}
      </span>
    );
  }

  // loading skeleton
  if (label === "loading") {
    return (
      <span
        className={className}
        aria-hidden="true"
        style={{ color: "var(--text-dim)", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}
      >
        {engineDisplay} &middot; <span style={{ opacity: 0.5 }}>⋯</span>
      </span>
    );
  }

  // null means undetected — render dim UNKNOWN
  if (label === null) {
    return (
      <span
        className={className}
        aria-hidden="true"
        style={{ color: "var(--text-dim)", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}
      >
        {engineDisplay} &middot; UNKNOWN
      </span>
    );
  }

  // detected version
  return (
    <span
      className={className}
      aria-hidden="true"
      style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}
    >
      <span style={{ color: "var(--text-dim)" }}>{engineDisplay} &middot; </span>
      <span style={{ color: "var(--text)" }}>{label}</span>
    </span>
  );
}
