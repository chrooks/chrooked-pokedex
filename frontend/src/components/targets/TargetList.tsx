/* The registered Targets, one selectable row each, with a remove affordance.
   Presentational: selection + removal are lifted to the container. The selected
   row carries the Preview / Apply workspace in the panel beside it. */

import type { Target } from "../../types";
import { engineLabel } from "../../lib/targets";
import { EngineVersionReadout } from "./EngineVersionReadout";

type Props = {
  targets: Target[];
  selectedId: string | null;
  removingId: string | null;
  onSelect: (id: string) => void;
  onRemove: (id: string) => void;
};

export function TargetList({
  targets,
  selectedId,
  removingId,
  onSelect,
  onRemove,
}: Props) {
  return (
    <ul className="target-list" id="target-list">
      {targets.map((target) => {
        const isSelected = target.id === selectedId;
        return (
          <li key={target.id} className="target-list__item">
            <button
              type="button"
              className="target-card"
              data-selected={isSelected}
              aria-pressed={isSelected}
              id={`target-row-${target.id}`}
              onClick={() => onSelect(target.id)}
            >
              <span className="target-card__lamp" aria-hidden="true" />
              <span className="target-card__main">
                <span className="target-card__label">{target.label}</span>
                <span className="target-card__path mono">{target.path}</span>
                <EngineVersionReadout id={target.id} engine={target.engine} />
              </span>
              <span className="target-card__engine mono">
                {engineLabel(target.engine)}
              </span>
            </button>
            <button
              type="button"
              className="target-card__remove"
              id={`target-remove-${target.id}`}
              aria-label={`Remove ${target.label}`}
              disabled={removingId === target.id}
              onClick={() => onRemove(target.id)}
            >
              {removingId === target.id ? "…" : "Remove"}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
