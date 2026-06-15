/* Compact dex-backdrop indicator that lives in the device header readout. When
   the dex is showing a Target's values (target ⊕ Ruleset) instead of the base
   canon, this chip names the fork and offers a one-click return to canon. It
   resolves the fork's label from the targets list so the user sees "Dreamstone",
   not a raw id. Replaces the old full-width BackdropBanner. */

import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import type { Target } from "../../types";
import "./backdrop-chip.css";

type Props = {
  targetId: string;
  onClear: () => void;
};

export function BackdropChip({ targetId, onClear }: Props) {
  const { data } = useResource<Target[]>(api.targets);
  const target = (data ?? []).find((t) => t.id === targetId) ?? null;
  const label = target?.label ?? targetId;

  return (
    <span className="backdrop-chip" id="dex-backdrop-chip" role="status">
      <span className="backdrop-chip__lamp" aria-hidden="true" />
      <span className="backdrop-chip__label">
        backdrop: <strong>{label}</strong>
        <span className="sr-only"> — showing this target&rsquo;s values ⊕ Ruleset</span>
      </span>
      <button
        type="button"
        id="dex-backdrop-clear"
        className="backdrop-chip__clear"
        onClick={onClear}
        aria-label={`Stop the ${label} backdrop and return to canon`}
      >
        ✕
      </button>
    </span>
  );
}
