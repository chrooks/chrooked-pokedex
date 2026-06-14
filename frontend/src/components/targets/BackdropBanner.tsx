/* The dex backdrop indicator. When the dex is showing a Target's values (target
   ⊕ Ruleset) instead of the base canon, this banner names the fork and offers a
   one-click return to canon. It resolves the fork's label from the targets list
   so the user sees "Dreamstone", not a raw id. */

import { api } from "../../api";
import { useResource } from "../../hooks/useResource";
import type { Target } from "../../types";

type Props = {
  targetId: string;
  onClear: () => void;
};

export function BackdropBanner({ targetId, onClear }: Props) {
  const { data } = useResource<Target[]>(api.targets);
  const target = (data ?? []).find((t) => t.id === targetId) ?? null;
  const label = target?.label ?? targetId;

  return (
    <div className="backdrop-banner" id="dex-backdrop-banner" role="status">
      <span className="backdrop-banner__lamp" aria-hidden="true" />
      <span className="backdrop-banner__text">
        Dex backdrop: <strong>{label}</strong>
        <span className="backdrop-banner__note">
          {" "}
          — showing this target&rsquo;s values ⊕ Ruleset
        </span>
      </span>
      <button
        type="button"
        id="dex-backdrop-clear"
        className="backdrop-banner__clear"
        onClick={onClear}
      >
        Back to canon
      </button>
    </div>
  );
}
